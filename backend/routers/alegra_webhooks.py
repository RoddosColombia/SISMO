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
        # Update inventory
        moto = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0, "id": 1, "estado": 1})
        if moto:
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
        raise HTTPException(status_code=400, detail="ALEGRA_USER / ALEGRA_TOKEN no configurados")

    webhook_url = f"{APP_URL}/api/webhooks/alegra"
    resultados = []

    async with httpx.AsyncClient(timeout=15) as client:
        for evento in EVENTOS_WEBHOOK:
            try:
                r = await client.post(
                    "https://api.alegra.com/api/v1/webhooks/subscriptions",
                    json={
                        "event": evento,
                        "url": webhook_url,
                        "headers": {"x-api-key": WEBHOOK_SECRET},
                    },
                    auth=(ALEGRA_USER, ALEGRA_TOKEN),
                )
                resultados.append({"evento": evento, "status": r.status_code, "ok": r.status_code in (200, 201)})
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
    return {"registradas": total_ok, "total": len(resultados), "resultados": resultados}


@router.get("/status")
async def webhook_status(current_user=Depends(get_current_user)):
    """List subscription status + payment cron info."""
    subs = await db.webhook_subscriptions.find({}, {"_id": 0}).to_list(20)
    cfg = await db.cfo_configuracion.find_one({}, {"_id": 0, "ultimo_payment_id_sync": 1}) or {}
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
    return {
        "suscripciones": subs,
        "total_activas": sum(1 for s in subs if s.get("ok")),
        "cron_intervalo": "cada 5 minutos",
        "pagos_sincronizados_hoy": pagos_hoy,
        "ultimo_sync_pago": (ultimo_pago or {}).get("fecha", "nunca"),
        "ultimo_payment_id": cfg.get("ultimo_payment_id_sync", 0),
    }


@router.post("/sync-pagos-ahora")
async def sync_pagos_ahora(current_user=Depends(get_current_user)):
    """Trigger payment sync manually from UI."""
    procesados = await sincronizar_pagos_externos()
    return {"procesados": procesados, "message": f"{procesados} pagos nuevos sincronizados"}
