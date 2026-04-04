"""global66.py — BUILD 25 — Global66 Webhook Receiver (refactorizado)

Endpoints:
  POST /api/global66/webhook   — Recibe notificaciones Global66 en tiempo real
  GET  /api/global66/sync      — Resumen de transacciones del día

DOCUMENTACIÓN REAL GLOBAL66 B2B (confirmada 4 abr 2026):
  - Autenticación: header x-api-key (NO HMAC-SHA256)
  - La x-api-key la genera Global66 al crear el webhook
  - Dos eventos soportados:
    1. "WALLET - Founding status"  → dinero RECIBIDO en cuenta (INGRESO)
    2. "RMT - Transaction"         → remesa ENVIADA a terceros (EGRESO)
  - Global66 NO reintenta si hay error → GUARDAR PRIMERO en MongoDB

CRITICAL RULES (from CLAUDE.md / SISMO error catalog):
  - NEVER /journal-entries — always /journals
  - Fallback cuenta ALWAYS 5493, NEVER 5495
  - Date format yyyy-MM-dd STRICT, NEVER ISO-8601 with timezone
  - Anti-dup via MD5(transaction_id) in global66_transacciones_procesadas
"""
import os
import hmac
import hashlib
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request
from database import db
from dependencies import get_current_user
from alegra_service import AlegraService

router = APIRouter(prefix="/global66", tags=["global66"])
logger = logging.getLogger(__name__)

# ── Cuenta Global66 en Alegra
GLOBAL66_BANK_ACCOUNT_ID = 11100507
# ── Fallback contable: Gastos Generales — NUNCA 5495
FALLBACK_CUENTA_ID = 5493


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _verificar_api_key(received_key: str, secret: str) -> bool:
    """Verifica x-api-key de Global66 (timing-safe para evitar timing attacks)."""
    if not secret:
        return True  # Sin secret configurado: modo desarrollo / prueba de Global66
    return hmac.compare_digest(received_key, secret)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/webhook")
async def procesar_webhook_global66(request: Request):
    """
    Recibe notificaciones de Global66 en tiempo real.

    Autenticación: header x-api-key generado por Global66 al crear el webhook.

    Soporta dos eventos reales (documentación Global66 B2B):
      - WALLET - Founding status: dinero recibido en cuenta (INGRESO para RODDOS)
      - RMT - Transaction: cambio de estado de remesa enviada (EGRESO)

    Patrón GUARDAR PRIMERO: Global66 no reintenta ante errores.
    El evento se persiste en MongoDB antes de intentar cualquier operación Alegra.
    El job _recuperar_global66_pendientes() (scheduler cada 10 min) reintenta los fallidos.
    """
    # ── 1. LEER BODY ───────────────────────────────────────────────────────
    raw_body = await request.body()

    # ── 2. VALIDAR x-api-key ───────────────────────────────────────────────
    webhook_secret = os.environ.get("GLOBAL66_WEBHOOK_SECRET", "")
    received_key = request.headers.get("x-api-key", "")

    if not _verificar_api_key(received_key, webhook_secret):
        logger.warning("[Global66] x-api-key inválida recibida — posible request no autorizado")
        raise HTTPException(status_code=401, detail="x-api-key inválida")

    # ── 3. BODY VACÍO = REQUEST DE PRUEBA DE GLOBAL66 ──────────────────────
    # Cuando Global66 valida el endpoint al crear el webhook, envía body vacío
    if not raw_body or raw_body.strip() in (b"", b"{}"):
        logger.info("[Global66] Request de prueba recibido — respondiendo 200 OK")
        return {"success": True, "procesado": False, "motivo": "prueba_conexion"}

    # ── 4. PARSE JSON ──────────────────────────────────────────────────────
    try:
        import json
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Body no es JSON válido")

    # ── 5. DETECTAR TIPO DE EVENTO ─────────────────────────────────────────
    event_type = payload.get("event", "")
    is_wallet = event_type == "WALLET - Founding status"
    is_remittance = event_type == "RMT - Transaction"

    if is_wallet:
        # Dinero RECIBIDO en cuenta Global66
        data = payload.get("data", {})
        transaction_id = str(data.get("transactionId", ""))
        monto = float(data.get("originAmount", 0.0))
        descripcion = (
            f"Global66 recibido de {data.get('thirdPartyClientName', 'Desconocido')} "
            f"via {data.get('remitterBankName', '')}"
        )
        tipo = "INGRESO"
        fecha = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        estado_g66 = data.get("status", "")

    elif is_remittance:
        # Remesa ENVIADA desde RODDOS a terceros
        data = payload.get("payload", {})
        transaction_id = str(data.get("transactionId", ""))
        monto = float(data.get("originAmount", 0.0))
        descripcion = (
            f"Global66 remesa: {data.get('purpose', '')} "
            f"-> {data.get('destinyCurrencyCode', '')}"
        )
        tipo = "EGRESO"
        raw_fecha = data.get("createdAt") or datetime.now(timezone.utc).isoformat()
        fecha = raw_fecha[:10]  # Solo YYYY-MM-DD
        estado_g66 = data.get("status", "")

    else:
        # Evento desconocido — guardar para auditoría y responder 200
        logger.warning("[Global66] Evento desconocido: %s", event_type)
        await db.global66_eventos_desconocidos.insert_one({
            "event_type": event_type,
            "payload": payload,
            "recibido_at": datetime.now(timezone.utc).isoformat(),
        })
        return {"success": True, "procesado": False, "motivo": "evento_desconocido"}

    if not transaction_id:
        logger.warning("[Global66] Evento %s sin transactionId", event_type)
        return {"success": True, "procesado": False, "motivo": "sin_transaction_id"}

    # ── 6. GUARDAR PRIMERO (Global66 no reintenta ante errores) ───────────
    # Usar $setOnInsert para no sobreescribir si ya existe (idempotencia)
    await db.global66_eventos_recibidos.update_one(
        {"transaction_id": transaction_id},
        {"$setOnInsert": {
            "transaction_id": transaction_id,
            "event_type": event_type,
            "tipo": tipo,
            "monto": monto,
            "descripcion": descripcion,
            "fecha": fecha,
            "estado_global66": estado_g66,
            "payload_completo": payload,
            "recibido_at": datetime.now(timezone.utc).isoformat(),
            "procesado": False,
            "intentos_alegra": 0,
        }},
        upsert=True,
    )

    # ── 7. SOLO PROCESAR ESTADOS EXITOSOS ──────────────────────────────────
    if estado_g66.upper() not in ("SUCCESSFUL", "COMPLETED", ""):
        logger.info(
            "[Global66] Evento %s con estado '%s' guardado — no causado en Alegra",
            transaction_id, estado_g66
        )
        return {"success": True, "procesado": False, "motivo": f"estado_{estado_g66}"}

    # ── 8. ANTI-DUP ────────────────────────────────────────────────────────
    hash_tx = hashlib.md5(transaction_id.encode()).hexdigest()
    existing = await db.global66_transacciones_procesadas.find_one({"hash_tx": hash_tx})
    if existing:
        logger.warning("[Global66] Duplicado: transaction_id=%s ya procesado", transaction_id)
        return {
            "success": True,
            "procesado": False,
            "motivo": "duplicado",
            "transaction_id": transaction_id,
        }

    # ── 9. CLASIFICAR CON MOTOR MATRICIAL ──────────────────────────────────
    from services.accounting_engine import clasificar_movimiento
    clasificacion = clasificar_movimiento(
        descripcion=descripcion,
        proveedor="",
        monto=monto,
        banco_origen=GLOBAL66_BANK_ACCOUNT_ID,
    )

    if clasificacion.es_transferencia_interna:
        await db.global66_eventos_recibidos.update_one(
            {"transaction_id": transaction_id},
            {"$set": {"procesado": True, "motivo": "traslado_interno"}}
        )
        return {"success": True, "procesado": False, "motivo": "traslado_interno"}

    # Determinar cuentas según tipo de movimiento
    if tipo == "INGRESO":
        cuenta_debito = GLOBAL66_BANK_ACCOUNT_ID
        cuenta_credito = clasificacion.cuenta_credito or FALLBACK_CUENTA_ID
    else:
        cuenta_debito = clasificacion.cuenta_debito or FALLBACK_CUENTA_ID
        cuenta_credito = GLOBAL66_BANK_ACCOUNT_ID

    confianza = clasificacion.confianza

    logger.info(
        "[Global66] %s %s: monto=%.0f confianza=%.0f%% debito=%s credito=%s",
        tipo, transaction_id, monto, confianza * 100, cuenta_debito, cuenta_credito
    )

    # ── 10a. ALTA CONFIANZA → Alegra /journals ─────────────────────────────
    if confianza >= 0.70:
        service = AlegraService(db)

        try:
            datetime.strptime(fecha, "%Y-%m-%d")
            fecha_journal = fecha
        except ValueError:
            fecha_journal = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        journal_payload = {
            "date": fecha_journal,
            "observations": f"{descripcion} | Tx: {transaction_id}",
            "entries": [
                {"id": cuenta_debito, "debit": int(monto), "credit": 0},
                {"id": cuenta_credito, "debit": 0, "credit": int(monto)},
            ],
        }

        try:
            journal_response = await service.request_with_verify(
                "journals", "POST", journal_payload
            )
        except Exception as e:
            logger.error("[Global66] POST /journals falló para %s: %s", transaction_id, e)
            await db.global66_eventos_recibidos.update_one(
                {"transaction_id": transaction_id},
                {"$inc": {"intentos_alegra": 1}, "$set": {"ultimo_error": str(e)}}
            )
            # Guardar en transacciones_procesadas como error para tracking
            await db.global66_transacciones_procesadas.insert_one({
                "hash_tx": hash_tx,
                "transaction_id": transaction_id,
                "tipo": tipo,
                "monto": monto,
                "descripcion": descripcion,
                "fecha": fecha_journal,
                "confianza": confianza,
                "estado": "error_alegra",
                "error": str(e),
                "fecha_registro": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
            # Responder 200 de todas formas (Global66 no debe reintentar)
            return {
                "success": True,
                "procesado": False,
                "transaction_id": transaction_id,
                "motivo": "error_alegra_guardado_para_reintento",
            }

        verificado = journal_response.get("_verificado", False)
        alegra_journal_id = journal_response.get("id")
        estado = "procesado" if verificado else "error_verificacion"

        await db.global66_transacciones_procesadas.insert_one({
            "hash_tx": hash_tx,
            "transaction_id": transaction_id,
            "tipo": tipo,
            "monto": monto,
            "descripcion": descripcion,
            "fecha": fecha_journal,
            "confianza": confianza,
            "alegra_journal_id": alegra_journal_id,
            "estado": estado,
            "fecha_registro": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        })

        await db.global66_eventos_recibidos.update_one(
            {"transaction_id": transaction_id},
            {"$set": {"procesado": True, "alegra_journal_id": str(alegra_journal_id)}}
        )

        logger.info(
            "[Global66] Journal %s creado — verificado=%s estado=%s",
            alegra_journal_id, verificado, estado
        )

        return {
            "success": True,
            "procesado": True,
            "transaction_id": transaction_id,
            "alegra_journal_id": alegra_journal_id,
            "_verificado": verificado,
            "confianza": confianza,
            "estado": estado,
        }

    # ── 10b. BAJA CONFIANZA → Backlog para revisión manual ─────────────────
    else:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        backlog_hash = hashlib.md5(
            f"global66{fecha}{descripcion}{str(monto)}".encode()
        ).hexdigest()

        await db.contabilidad_pendientes.update_one(
            {"backlog_hash": backlog_hash},
            {"$setOnInsert": {
                "backlog_hash": backlog_hash,
                "banco": "global66",
                "extracto": f"global66_{fecha[:7].replace('-', '_')}",
                "fecha": fecha,
                "descripcion": descripcion,
                "monto": monto,
                "tipo": tipo,
                "confianza_motor": confianza,
                "cuenta_debito_sugerida": cuenta_debito,
                "cuenta_credito_sugerida": cuenta_credito,
                "razon_baja_confianza": clasificacion.razon,
                "estado": "pendiente",
                "journal_alegra_id": None,
                "resuelto_por": None,
                "resuelto_at": None,
                "creado_at": datetime.now(timezone.utc).isoformat(),
            }},
            upsert=True,
        )

        await db.roddos_events.insert_one({
            "event_type": "global66.movimiento.backlog",
            "transaction_id": transaction_id,
            "monto": monto,
            "confianza": confianza,
            "fecha_registro": now_str,
        })

        await db.global66_transacciones_procesadas.insert_one({
            "hash_tx": hash_tx,
            "transaction_id": transaction_id,
            "tipo": tipo,
            "monto": monto,
            "descripcion": descripcion,
            "fecha": fecha,
            "confianza": confianza,
            "estado": "pendiente_conciliacion",
            "fecha_registro": now_str,
        })

        logger.info(
            "[Global66] Baja confianza (%.0f%%) — %s → backlog",
            confianza * 100, transaction_id
        )

        return {
            "success": True,
            "procesado": False,
            "transaction_id": transaction_id,
            "motivo": "confianza_baja",
            "confianza": confianza,
            "estado": "pendiente_conciliacion",
        }


@router.get("/sync")
async def obtener_sync_global66(current_user=Depends(get_current_user)):
    """Resumen de transacciones Global66 del día actual."""
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sincronizados = await db.global66_transacciones_procesadas.count_documents({
        "estado": "procesado", "fecha_registro": hoy,
    })
    pendientes = await db.global66_transacciones_procesadas.count_documents({
        "estado": "pendiente_conciliacion", "fecha_registro": hoy,
    })
    errores = await db.global66_transacciones_procesadas.count_documents({
        "estado": {"$in": ["error_alegra", "error_verificacion"]}, "fecha_registro": hoy,
    })
    eventos_recibidos = await db.global66_eventos_recibidos.count_documents({
        "recibido_at": {"$gte": f"{hoy}T00:00:00"},
    })

    return {
        "sincronizados": sincronizados,
        "pendientes": pendientes,
        "errores": errores,
        "eventos_recibidos_hoy": eventos_recibidos,
        "fecha": hoy,
    }
