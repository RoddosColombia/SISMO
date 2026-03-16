"""alegra_webhooks.py — Webhook receiver + payment-sync cron for Alegra.

Endpoints:
  POST /api/webhooks/alegra       — Receiver (responds <1s, processes in background)
  POST /api/webhooks/setup        — Subscribe 12 events in Alegra
  GET  /api/webhooks/status       — List active subscriptions + cron status
"""
import logging
import os
import re
import httpx
from datetime import datetime, timezone

from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request

from database import db
from dependencies import get_current_user

# VIN patterns for Auteco/TVS motos
_VIN_RE = re.compile(r'9FL[A-Z0-9]{14,17}', re.IGNORECASE)
_MOTOR_RE = re.compile(r'(BF3[A-Z0-9]{6,12}|RF5[A-Z0-9]{6,12})', re.IGNORECASE)

router = APIRouter(prefix="/webhooks", tags=["webhooks-alegra"])
logger = logging.getLogger(__name__)

ALEGRA_BASE = "https://app.alegra.com/api/r1"
ALEGRA_API_V1 = "https://api.alegra.com/api/v1"
ALEGRA_USER = os.environ.get("ALEGRA_USER", "")
ALEGRA_TOKEN = os.environ.get("ALEGRA_TOKEN", "")
WEBHOOK_SECRET = os.environ.get("ALEGRA_WEBHOOK_SECRET", "roddos-webhook-2026")
APP_URL = os.environ.get("APP_URL", "")


# ── Webhook receiver ──────────────────────────────────────────────────────────

@router.post("/alegra")
async def recibir_webhook_alegra(
    request: Request,
    background_tasks: BackgroundTasks,
    x_api_key: str = Header(None, alias="x-api-key"),
):
    """Receive Alegra webhook. MUST respond < 5 s → background processing."""
    if x_api_key != WEBHOOK_SECRET:
        logger.warning("[Webhook] Invalid api-key: %s", x_api_key)
        raise HTTPException(status_code=401, detail="Unauthorized")

    payload = await request.json()
    evento = payload.get("event", "unknown")
    logger.info("[Webhook] Received event: %s", evento)

    background_tasks.add_task(procesar_evento_webhook, payload)
    return {"status": "ok"}


# ── Event dispatcher ──────────────────────────────────────────────────────────

async def procesar_evento_webhook(payload: dict):
    evento = payload.get("event", "")
    datos = payload.get("data", {})

    handlers = {
        "new-invoice":    _nueva_factura,
        "edit-invoice":   _editar_factura,
        "delete-invoice": _eliminar_factura,
        "new-bill":       _nueva_compra,
        "edit-bill":      _editar_compra,
        "delete-bill":    _eliminar_compra,
        "new-client":     _nuevo_cliente,
        "edit-client":    _editar_cliente,
        "delete-client":  _eliminar_cliente,
        "new-item":       _nuevo_item,
        "edit-item":      _editar_item,
        "delete-item":    _eliminar_item,
    }

    handler = handlers.get(evento)
    processed = False
    if handler:
        try:
            await handler(datos)
            processed = True
        except Exception as exc:
            logger.error("[Webhook] Handler %s error: %s", evento, exc)

    await db.roddos_events.insert_one({
        "event_type":    f"alegra.webhook.{evento}",
        "source":        "alegra_webhook",
        "payload":       datos,
        "timestamp":     datetime.now(timezone.utc).isoformat(),
        "alegra_synced": True,
        "processed":     processed,
    })


# ── Handlers ──────────────────────────────────────────────────────────────────

async def _nueva_factura(datos: dict):
    """Process new invoice: detect VIN, update inventory + loanbook, or flag for review."""
    factura_id = str(datos.get("id", ""))
    cliente = datos.get("client", {}) or {}
    items = datos.get("items", []) or []
    fecha = datos.get("date", "")
    total = float(datos.get("total", 0) or 0)

    # Build search text: anotation + item names + descriptions
    anotation = str(datos.get("anotation", "") or "").upper()
    items_text = " ".join(
        str(it.get("name", "")) + " " + str(it.get("description", "")) + " " + str(it.get("observations", ""))
        for it in items
    ).upper()
    full_text = anotation + " " + items_text

    # Detect VIN and motor
    vin_m = _VIN_RE.search(full_text)
    motor_m = _MOTOR_RE.search(full_text)
    chasis = vin_m.group().strip() if vin_m else None
    motor_val = motor_m.group().strip() if motor_m else None

    # Detect modelo
    modelo_val = None
    for modelo_key in ["RAIDER 125", "SPORT 100"]:
        if modelo_key in full_text:
            modelo_val = modelo_key.title()
            break

    if chasis:
        # Update inventory — only if currently Disponible (don't downgrade from Entregada)
        moto = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0, "id": 1, "estado": 1})
        if moto:
            if moto.get("estado") not in ("Vendida", "Entregada"):
                await db.inventario_motos.update_one(
                    {"chasis": chasis},
                    {"$set": {
                        "estado": "Vendida",
                        "factura_alegra_id": factura_id,
                        "fecha_venta": fecha,
                        "propietario": cliente.get("name", ""),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }},
                )
                logger.info("[Webhook] Moto VIN=%s marcada como Vendida (factura %s)", chasis, factura_id)
            else:
                logger.info("[Webhook] Moto VIN=%s ya estaba %s (factura %s) — sin cambios", chasis, moto.get("estado"), factura_id)

        # Update loanbook with VIN + motor
        loanbook = await db.loanbook.find_one(
            {"$or": [
                {"factura_alegra_id": factura_id},
                {"cliente_nombre": {"$regex": re.escape(cliente.get("name", "")), "$options": "i"}},
            ]},
            {"_id": 0, "id": 1, "codigo": 1},
        )
        if loanbook:
            await db.loanbook.update_one(
                {"id": loanbook["id"]},
                {"$set": {
                    "moto_chasis": chasis,
                    "motor": motor_val,
                    "modelo_moto": modelo_val,
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            logger.info("[Webhook] Loanbook %s actualizado con VIN=%s", loanbook.get("codigo"), chasis)

        await db.roddos_events.insert_one({
            "event_type": "moto.vendida.webhook",
            "source": "alegra_webhook",
            "factura_id": factura_id,
            "alegra_invoice_id": factura_id,
            "chasis": chasis,
            "motor": motor_val,
            "cliente": cliente.get("name", ""),
            "total": total,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "accion_ejecutada": "inventario+loanbook actualizados",
        })
    else:
        # No VIN detected — flag for review
        await db.roddos_events.insert_one({
            "event_type": "factura.externa.sin_vin",
            "source": "alegra_webhook",
            "factura_id": factura_id,
            "alegra_invoice_id": factura_id,
            "cliente": cliente.get("name", ""),
            "total": total,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "requiere_revision": True,
            "nota": "Factura sin VIN detectado — revisar manualmente",
        })
        await db.notifications.insert_one({
            "type": "alegra_factura_sin_vin",
            "message": f"Factura {datos.get('number', factura_id)} registrada sin VIN — requiere revisión manual",
            "data": {"factura_id": factura_id, "cliente": cliente.get("name", "")},
            "read": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })


async def _editar_factura(datos: dict):
    factura_id = str(datos.get("id", ""))
    await db.roddos_events.insert_one({
        "event_type": "factura.editada",
        "source": "alegra_webhook",
        "payload": datos,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "factura_id": factura_id,
    })


async def _eliminar_factura(datos: dict):
    """CRITICAL: revert inventory when invoice is deleted in Alegra."""
    factura_id = str(datos.get("id", ""))
    if not factura_id:
        return

    moto = await db.inventario_motos.find_one({"factura_alegra_id": factura_id}, {"_id": 0, "id": 1, "marca": 1, "version": 1})
    if moto:
        await db.inventario_motos.update_one(
            {"factura_alegra_id": factura_id},
            {"$set": {
                "estado": "Disponible",
                "factura_alegra_id": None,
                "fecha_venta": None,
                "cliente_nombre": None,
            }},
        )
        await db.loanbook.update_one(
            {"factura_alegra_id": factura_id},
            {"$set": {"estado": "anulado"}},
        )
        logger.info("[Webhook] Factura %s eliminada → moto %s revertida a Disponible", factura_id, moto.get("id"))
        await db.notifications.insert_one({
            "type": "factura_eliminada_reversion",
            "message": f"Factura {factura_id} eliminada en Alegra → moto {moto.get('marca','')} {moto.get('version','')} revertida a Disponible",
            "data": {"factura_id": factura_id, "moto_id": moto.get("id")},
            "read": False,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
    else:
        logger.info("[Webhook] Factura %s eliminada — no hay moto vinculada", factura_id)


async def _nueva_compra(datos: dict):
    await db.roddos_events.insert_one({
        "event_type":        "compra.externa.detectada",
        "source":            "alegra_webhook",
        "payload":           datos,
        "timestamp":         datetime.now(timezone.utc).isoformat(),
        "requiere_revision": True,
    })


async def _editar_compra(datos: dict):
    await db.roddos_events.insert_one({
        "event_type": "compra.editada",
        "source": "alegra_webhook",
        "payload": datos,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _eliminar_compra(datos: dict):
    await db.roddos_events.insert_one({
        "event_type": "compra.eliminada",
        "source": "alegra_webhook",
        "payload": datos,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _nuevo_cliente(datos: dict):
    """Sync new Alegra client to contactos collection."""
    cliente_id = str(datos.get("id", ""))
    if not cliente_id:
        return
    existente = await db.contactos.find_one({"alegra_id": cliente_id})
    if not existente:
        identificacion = datos.get("identification") or {}
        await db.contactos.insert_one({
            "alegra_id":       cliente_id,
            "nombre":          datos.get("name", ""),
            "identificacion":  identificacion.get("number", "") if isinstance(identificacion, dict) else str(identificacion),
            "telefono":        datos.get("phonePrimary", ""),
            "email":           datos.get("email", ""),
            "fuente":          "alegra_webhook",
            "fecha_sync":      datetime.now(timezone.utc).isoformat(),
        })
        logger.info("[Webhook] Nuevo cliente sincronizado: %s (%s)", datos.get("name"), cliente_id)


async def _editar_cliente(datos: dict):
    cliente_id = str(datos.get("id", ""))
    if not cliente_id:
        return
    identificacion = datos.get("identification") or {}
    await db.contactos.update_one(
        {"alegra_id": cliente_id},
        {"$set": {
            "nombre":         datos.get("name", ""),
            "identificacion": identificacion.get("number", "") if isinstance(identificacion, dict) else str(identificacion),
            "telefono":       datos.get("phonePrimary", ""),
            "email":          datos.get("email", ""),
            "fecha_sync":     datetime.now(timezone.utc).isoformat(),
        }},
    )


async def _eliminar_cliente(datos: dict):
    cliente_id = str(datos.get("id", ""))
    if cliente_id:
        await db.contactos.delete_one({"alegra_id": cliente_id})


async def _nuevo_item(datos: dict):
    nombre = (datos.get("name") or "").lower()
    marcas_moto = ["honda", "yamaha", "auteco", "kawasaki", "bajaj", "tvs", "hero", "cb", "fz"]
    es_moto = any(m in nombre for m in marcas_moto)
    if es_moto:
        await db.roddos_events.insert_one({
            "event_type": "item.moto.sync",
            "payload":    datos,
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        })


async def _editar_item(datos: dict):
    await db.roddos_events.insert_one({
        "event_type": "item.editado",
        "source": "alegra_webhook",
        "payload": datos,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


async def _eliminar_item(datos: dict):
    await db.roddos_events.insert_one({
        "event_type": "item.eliminado",
        "source": "alegra_webhook",
        "payload": datos,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })


# ── Payment sync cron (called from scheduler.py every 5 min) ─────────────────

async def sincronizar_pagos_externos():
    """Pull recent Alegra payments and apply to loanbook if not already processed."""
    if not ALEGRA_USER or not ALEGRA_TOKEN:
        return 0
    try:
        config = await db.cfo_configuracion.find_one({}, {"ultimo_payment_id_sync": 1, "_id": 0}) or {}
        ultimo_id = int(config.get("ultimo_payment_id_sync", 0) or 0)

        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{ALEGRA_BASE}/payments",
                params={"order_direction": "DESC", "order_field": "id", "limit": 20},
                auth=(ALEGRA_USER, ALEGRA_TOKEN),
            )
        if resp.status_code != 200:
            logger.warning("[PaymentSync] Alegra returned %s", resp.status_code)
            return 0

        pagos = resp.json()
        if not isinstance(pagos, list):
            return 0

        nuevos = [p for p in pagos if int(p.get("id", 0) or 0) > ultimo_id]
        procesados = 0

        for pago in reversed(nuevos):
            ya = await db.cartera_pagos.find_one({"alegra_payment_id": str(pago.get("id"))})
            if ya:
                continue

            invoices = pago.get("invoices") or []
            factura_id = str(invoices[0].get("id", "")) if invoices else ""
            if not factura_id:
                continue

            loan = await db.loanbook.find_one({"factura_alegra_id": factura_id}, {"_id": 0})
            if not loan:
                continue

            monto = float(pago.get("amount", 0) or 0)
            cuotas = loan.get("cuotas", [])
            for i, cuota in enumerate(cuotas):
                if cuota.get("estado") == "pendiente":
                    await db.loanbook.update_one(
                        {"factura_alegra_id": factura_id},
                        {"$set": {
                            f"cuotas.{i}.estado":     "pagada",
                            f"cuotas.{i}.fecha_pago": datetime.now(timezone.utc).isoformat(),
                            f"cuotas.{i}.valor_pagado": monto,
                            f"cuotas.{i}.comprobante": f"alegra-pago-{pago.get('id')}",
                            "saldo_pendiente": max(0, float(loan.get("saldo_pendiente", 0) or 0) - monto),
                        }},
                    )
                    await db.cartera_pagos.insert_one({
                        "loanbook_id":       loan.get("id", ""),
                        "cliente_nombre":    loan.get("cliente_nombre", ""),
                        "monto":             monto,
                        "fecha":             datetime.now(timezone.utc).isoformat(),
                        "fuente":            "alegra_sync_cron",
                        "alegra_payment_id": str(pago.get("id")),
                        "numero_cuota":      cuota.get("numero", i + 1),
                    })

                    # WhatsApp Template 4 — confirm payment
                    try:
                        from routers.mercately import enviar_template_4_confirmacion_pago
                        tel = loan.get("cliente_telefono", "")
                        if tel:
                            await enviar_template_4_confirmacion_pago(
                                nombre_cliente=loan.get("cliente_nombre", ""),
                                telefono=tel,
                                monto=monto,
                                numero_cuota=cuota.get("numero", i + 1),
                                saldo_pendiente=max(0, float(loan.get("saldo_pendiente", 0) or 0) - monto),
                                cedula=loan.get("cliente_nit", ""),
                            )
                    except Exception as wa_err:
                        logger.debug("[PaymentSync] WA T4 error: %s", wa_err)

                    procesados += 1
                    break

        if nuevos:
            nuevo_max = int(nuevos[0].get("id", 0) or 0)
            await db.cfo_configuracion.update_one(
                {},
                {"$set": {"ultimo_payment_id_sync": nuevo_max}},
                upsert=True,
            )

        if procesados:
            logger.info("[PaymentSync] %d nuevos pagos procesados (último id=%s)", procesados, nuevo_max if nuevos else "?")
        return procesados

    except Exception as exc:
        logger.error("[PaymentSync] Error: %s", exc)
        return 0


# ── Invoice sync cron (called from scheduler.py every 5 min) ─────────────────

async def _get_alegra_auth() -> tuple[str, str]:
    """Return (email, token) from DB credentials."""
    creds = await db.alegra_credentials.find_one({}, {"_id": 0, "email": 1, "token": 1}) or {}
    return creds.get("email", ""), creds.get("token", "")


async def sincronizar_facturas_recientes(fecha_desde: str = None) -> int:
    """
    Pull recent Alegra invoices and process new ones via _nueva_factura handler.
    Deduplicates by alegra_invoice_id in roddos_events.
    Uses ultima_factura_id_sync in cfo_configuracion to avoid reprocessing.

    Args:
        fecha_desde: Optional ISO date string (e.g. "2026-03-16T00:00:00"). Overrides
                     the rolling 24h window when provided.
    """
    try:
        email, token = await _get_alegra_auth()
        if not email or not token:
            logger.warning("[InvoiceSync] Sin credenciales Alegra en DB")
            return 0

        import base64 as _b64
        auth_str = _b64.b64encode(f"{email}:{token}".encode()).decode()

        # Determine starting invoice ID to avoid full re-scan
        cfg = await db.cfo_configuracion.find_one({}, {"_id": 0, "ultima_factura_id_sync": 1}) or {}
        ultimo_id = int(cfg.get("ultima_factura_id_sync") or 0)

        params: dict = {"order_direction": "DESC", "order_field": "id", "limit": 20}
        if fecha_desde:
            # When a specific date is provided, fetch more (max allowed by Alegra is 30)
            params["limit"] = 30

        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{ALEGRA_API_V1}/invoices",
                headers={"Authorization": f"Basic {auth_str}", "Content-Type": "application/json"},
                params=params,
            )

        if resp.status_code != 200:
            logger.warning("[InvoiceSync] Alegra returned %s: %s", resp.status_code, resp.text[:200])
            return 0

        facturas = resp.json()
        if not isinstance(facturas, list):
            logger.warning("[InvoiceSync] Unexpected Alegra response: %s", str(facturas)[:200])
            return 0

        # Filter: only invoices newer than ultimo_id (or from fecha_desde)
        if fecha_desde:
            fecha_dt = fecha_desde[:10]  # YYYY-MM-DD
            nuevas = [f for f in facturas if f.get("date", "") >= fecha_dt]
        else:
            nuevas = [f for f in facturas if int(f.get("id", 0) or 0) > ultimo_id]

        procesadas = 0
        max_id = ultimo_id

        for factura in reversed(nuevas):
            fid = str(factura.get("id", ""))
            fid_int = int(fid or 0)

            # Deduplication: skip if already processed
            ya_procesada = await db.roddos_events.find_one(
                {"$or": [
                    {"alegra_invoice_id": fid},
                    {"factura_id": fid, "event_type": {"$in": ["moto.vendida.webhook", "moto.vendida.polling", "moto.vendida.retroactivo"]}},
                ]},
                {"_id": 0, "event_type": 1},
            )
            if ya_procesada:
                if fid_int > max_id:
                    max_id = fid_int
                continue

            # Process invoice using the same handler as webhook
            try:
                await _nueva_factura(factura)
                # Mark as processed with source=polling
                await db.roddos_events.update_one(
                    {"factura_id": fid, "event_type": "factura.externa.sin_vin"},
                    {"$set": {"source": "polling"}},
                )
                # Log the polling event
                await db.roddos_events.insert_one({
                    "event_type": "alegra.invoice.polling",
                    "alegra_invoice_id": fid,
                    "source": "invoice_polling_cron",
                    "cliente": (factura.get("client") or {}).get("name", ""),
                    "fecha_factura": factura.get("date", ""),
                    "total": float(factura.get("total", 0) or 0),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                procesadas += 1
                logger.info("[InvoiceSync] Factura %s procesada via polling", fid)
            except Exception as exc:
                logger.error("[InvoiceSync] Error procesando factura %s: %s", fid, exc)

            if fid_int > max_id:
                max_id = fid_int

        # Update watermark only if we processed new invoices or advanced
        if max_id > ultimo_id:
            await db.cfo_configuracion.update_one(
                {},
                {"$set": {"ultima_factura_id_sync": max_id}},
                upsert=True,
            )

        if procesadas:
            logger.info("[InvoiceSync] %d facturas procesadas (último id=%s)", procesadas, max_id)
        return procesadas

    except Exception as exc:
        logger.error("[InvoiceSync] Error general: %s", exc)
        return 0


# ── Setup subscriptions ───────────────────────────────────────────────────────

EVENTOS_WEBHOOK = [
    "new-invoice", "edit-invoice", "delete-invoice",
    "new-bill",    "edit-bill",    "delete-bill",
    "new-client",  "edit-client",  "delete-client",
    "new-item",    "edit-item",    "delete-item",
]


@router.post("/setup")
async def setup_webhooks():
    """Subscribe all 12 Alegra events. Run once after deploy."""
    if not APP_URL:
        raise HTTPException(status_code=400, detail="APP_URL no configurada en .env")
    if not ALEGRA_USER or not ALEGRA_TOKEN:
        # Try DB credentials
        email, token = await _get_alegra_auth()
        if not email or not token:
            raise HTTPException(status_code=400, detail="ALEGRA_USER / ALEGRA_TOKEN no configurados")
        auth = (email, token)
    else:
        auth = (ALEGRA_USER, ALEGRA_TOKEN)

    webhook_url = f"{APP_URL}/api/webhooks/alegra"
    resultados = []

    # NOTE: Alegra v1 API rejects URLs with "https://" or "http://" prefix.
    # This is a known API bug. We attempt registration and capture the error.
    async with httpx.AsyncClient(timeout=15) as client:
        for evento in EVENTOS_WEBHOOK:
            try:
                r = await client.post(
                    f"{ALEGRA_API_V1}/webhooks/subscriptions",
                    json={
                        "event": evento,
                        "url": webhook_url,
                        "headers": {"x-api-key": WEBHOOK_SECRET},
                    },
                    auth=auth,
                )
                ok = r.status_code in (200, 201)
                err_msg = None
                if not ok:
                    err_body = r.json() if r.content else {}
                    err_msg = err_body.get("error", r.text[:200])
                resultados.append({"evento": evento, "status": r.status_code, "ok": ok, "error": err_msg})
            except Exception as exc:
                resultados.append({"evento": evento, "status": 0, "ok": False, "error": str(exc)})

    # Persist result
    await db.webhook_subscriptions.delete_many({})
    await db.webhook_subscriptions.insert_many([
        {**r, "webhook_url": webhook_url, "registrado_en": datetime.now(timezone.utc).isoformat()}
        for r in resultados
    ])

    total_ok = sum(1 for r in resultados if r["ok"])
    logger.info("[WebhookSetup] %d/%d suscripciones registradas", total_ok, len(resultados))

    # Check if all failed due to URL protocol issue
    first_error = next((r.get("error", "") for r in resultados if not r["ok"]), "")
    nota = None
    if "http" in str(first_error).lower() and ("https" in str(first_error).lower() or "url" in str(first_error).lower()):
        nota = (
            "Alegra API rechaza URLs con 'https://' o 'http://'. "
            "El polling automático cada 5min está activo como fallback. "
            "Para activar webhooks reales, regístralos manualmente en app.alegra.com → Integraciones → Webhooks "
            f"con URL: {webhook_url}"
        )

    return {
        "registradas": total_ok,
        "total": len(resultados),
        "resultados": resultados,
        "nota_alegra_bug": nota,
        "polling_activo": True,
        "polling_intervalo": "cada 5 minutos",
    }


@router.get("/status")
async def webhook_status(current_user=Depends(get_current_user)):
    """List subscription status + payment cron info + invoice polling info."""
    subs = await db.webhook_subscriptions.find({}, {"_id": 0}).to_list(20)
    cfg = await db.cfo_configuracion.find_one({}, {"_id": 0, "ultimo_payment_id_sync": 1, "ultima_factura_id_sync": 1}) or {}
    # Count recent payments synced via cron (today)
    hoy = datetime.now(timezone.utc).date().isoformat()
    pagos_hoy = await db.cartera_pagos.count_documents({
        "fuente": "alegra_sync_cron",
        "fecha": {"$regex": f"^{hoy}"},
    })
    ultimo_pago = await db.cartera_pagos.find_one(
        {"fuente": "alegra_sync_cron"},
        {"_id": 0, "fecha": 1},
        sort=[("fecha", -1)],
    )
    # Invoice polling stats
    facturas_hoy = await db.roddos_events.count_documents({
        "event_type": "alegra.invoice.polling",
        "timestamp": {"$regex": f"^{hoy}"},
    })
    ultimo_polling = await db.roddos_events.find_one(
        {"event_type": "alegra.invoice.polling"},
        {"_id": 0, "timestamp": 1, "alegra_invoice_id": 1},
        sort=[("timestamp", -1)],
    )
    return {
        "suscripciones": subs,
        "total_activas": sum(1 for s in subs if s.get("ok")),
        "cron_intervalo": "cada 5 minutos",
        "pagos_sincronizados_hoy": pagos_hoy,
        "ultimo_sync_pago": (ultimo_pago or {}).get("fecha", "nunca"),
        "ultimo_payment_id": cfg.get("ultimo_payment_id_sync", 0),
        "polling_facturas_activo": True,
        "polling_facturas_intervalo": "cada 5 minutos",
        "facturas_procesadas_hoy": facturas_hoy,
        "ultima_factura_procesada_id": cfg.get("ultima_factura_id_sync", 0),
        "ultimo_polling_timestamp": (ultimo_polling or {}).get("timestamp", "nunca"),
        "nota": "Alegra webhooks API no acepta URLs con https:// (bug conocido). Polling es el mecanismo principal.",
    }


@router.post("/sync-pagos-ahora")
async def sync_pagos_ahora(current_user=Depends(get_current_user)):
    """Trigger payment sync manually from UI."""
    procesados = await sincronizar_pagos_externos()
    return {"procesados": procesados, "message": f"{procesados} pagos nuevos sincronizados"}


@router.post("/sync-facturas-ahora")
async def sync_facturas_ahora(body: dict = None, current_user=Depends(get_current_user)):
    """Trigger invoice sync manually from UI. Accepts optional fecha_desde (ISO string)."""
    body = body or {}
    fecha_desde = body.get("fecha_desde")
    procesadas = await sincronizar_facturas_recientes(fecha_desde=fecha_desde)
    return {"procesadas": procesadas, "message": f"{procesadas} facturas nuevas procesadas"}
