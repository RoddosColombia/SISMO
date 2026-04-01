"""global66.py — 260401-esw — Global66 Webhook Receiver

Endpoints:
  POST /api/global66/webhook   — Receive Global66 payment platform webhooks
  GET  /api/global66/sync      — Daily reconciliation counts

CRITICAL RULES (from CLAUDE.md / SISMO error catalog):
  - NEVER /journal-entries — always /journals (ERROR-008)
  - Fallback cuenta ALWAYS 5493, NEVER 5495 (ERROR-009)
  - Date format yyyy-MM-dd STRICT, NEVER ISO-8601 with timezone (ALEGRA API rule)
  - Anti-dup via MD5(transaction_id) in hash_tx field (ERROR-011 pattern)
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

# ── Global66 bank account in Alegra (hardcoded per plan spec)
GLOBAL66_BANK_ACCOUNT_ID = 11100507
# ── Fallback contra-account: Gastos Generales per CLAUDE.md (NEVER 5495)
FALLBACK_CUENTA_ID = 5493


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _calcular_confianza(monto: float, descripcion: str, tipo: str) -> float:
    """
    Compute confidence score for a Global66 movement.

    Scoring logic:
      Base: 0.5
      +0.15 if monto > 0
      +0.10 if descripcion contains payment keywords
      +0.10 if tipo in (credit, ingreso, deposito)
      Capped at 1.0
    """
    score = 0.5
    if monto > 0:
        score += 0.15

    keywords = {"transferencia", "pago", "cuota", "abono"}
    desc_lower = (descripcion or "").lower()
    if any(kw in desc_lower for kw in keywords):
        score += 0.10

    if (tipo or "").lower() in {"credit", "ingreso", "deposito"}:
        score += 0.10

    return min(score, 1.0)


def _verificar_hmac(raw_body: bytes, received_signature: str, secret: str) -> bool:
    """Verify HMAC-SHA256 signature from Global66 webhook header."""
    expected = hmac.new(
        secret.encode("utf-8"),
        raw_body,
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, received_signature)


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/webhook")
async def procesar_webhook_global66(request: Request):
    """
    Receive Global66 payment platform webhook.

    Flow:
    1. Validate HMAC-SHA256 signature (X-Global66-Signature header)
    2. Anti-dup: MD5(transaction_id) → reject 409 if already processed
    3. Determine confianza: from payload field or _calcular_confianza()
    4. confianza >= 0.70 → POST to Alegra /journals via request_with_verify
    5. confianza < 0.70 → insert conciliacion_partidas + event, return 200
    """
    # ── 1. READ RAW BODY FOR HMAC ──────────────────────────────────────────
    raw_body = await request.body()

    # ── 2. VALIDATE HMAC SIGNATURE ─────────────────────────────────────────
    webhook_secret = os.environ.get("GLOBAL66_WEBHOOK_SECRET", "")
    received_sig = request.headers.get("X-Global66-Signature", "")

    if not received_sig:
        logger.warning("[Global66] Webhook received without X-Global66-Signature header")
        raise HTTPException(status_code=401, detail="Firma HMAC requerida")

    if not _verificar_hmac(raw_body, received_sig, webhook_secret):
        logger.warning("[Global66] Invalid HMAC signature — possible spoofed request")
        raise HTTPException(status_code=401, detail="Firma HMAC invalida")

    # ── 3. PARSE JSON ──────────────────────────────────────────────────────
    try:
        import json
        payload = json.loads(raw_body)
    except Exception:
        raise HTTPException(status_code=400, detail="Body no es JSON valido")

    transaction_id = payload.get("transaction_id", "")
    tipo = payload.get("tipo", "")
    monto = float(payload.get("monto", 0.0))
    descripcion = payload.get("descripcion", "")
    fecha = payload.get("fecha", datetime.now(timezone.utc).strftime("%Y-%m-%d"))

    if not transaction_id:
        raise HTTPException(status_code=400, detail="transaction_id es obligatorio")

    # ── 4. ANTI-DUP: MD5(transaction_id) ───────────────────────────────────
    hash_tx = hashlib.md5(transaction_id.encode()).hexdigest()
    existing = await db.global66_transacciones_procesadas.find_one({"hash_tx": hash_tx})
    if existing:
        logger.warning(f"[Global66] Duplicado detectado: transaction_id={transaction_id}")
        raise HTTPException(
            status_code=409,
            detail=f"Duplicado detectado: transaction_id {transaction_id} ya fue procesado"
        )

    # ── 5. DETERMINE CONFIANZA ─────────────────────────────────────────────
    if "confianza" in payload:
        confianza = float(payload["confianza"])
    else:
        confianza = _calcular_confianza(monto, descripcion, tipo)

    logger.info(
        f"[Global66] Procesando {transaction_id}: monto={monto}, confianza={confianza:.2f}"
    )

    # ── 6a. HIGH CONFIDENCE: → Alegra /journals ────────────────────────────
    if confianza >= 0.70:
        service = AlegraService(db)

        # Date must be yyyy-MM-dd STRICT (ALEGRA API rule — NEVER ISO with timezone)
        # If fecha from webhook already in correct format, use directly
        try:
            datetime.strptime(fecha, "%Y-%m-%d")
            fecha_journal = fecha
        except ValueError:
            fecha_journal = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        journal_payload = {
            "date": fecha_journal,
            "observations": (
                f"Global66 - {tipo}: {descripcion}. "
                f"Tx ID: {transaction_id}. "
                f"Monto: {monto}"
            ),
            "entries": [
                {
                    "id": GLOBAL66_BANK_ACCOUNT_ID,
                    "debit": monto,
                    "credit": 0,
                },
                {
                    "id": FALLBACK_CUENTA_ID,  # 5493 Gastos Generales — NEVER 5495
                    "debit": 0,
                    "credit": monto,
                },
            ],
        }

        try:
            journal_response = await service.request_with_verify(
                "journals", "POST", journal_payload
            )
        except Exception as e:
            logger.error(f"[Global66] POST /journals falló: {e}")
            await db.global66_transacciones_procesadas.insert_one({
                "hash_tx": hash_tx,
                "transaction_id": transaction_id,
                "tipo": tipo,
                "monto": monto,
                "descripcion": descripcion,
                "fecha": fecha_journal,
                "confianza": confianza,
                "estado": "error_verificacion",
                "error": str(e),
                "fecha_registro": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            })
            raise HTTPException(status_code=500, detail=f"Error creando journal: {e}")

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

        logger.info(
            f"[Global66] Journal {alegra_journal_id} — verificado={verificado}, estado={estado}"
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

    # ── 6b. LOW CONFIDENCE: → conciliacion_partidas + event ───────────────
    else:
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        await db.conciliacion_partidas.insert_one({
            "origen": "global66",
            "transaction_id": transaction_id,
            "tipo": tipo,
            "monto": monto,
            "descripcion": descripcion,
            "fecha": fecha,
            "confianza": confianza,
            "estado": "pendiente",
            "fecha_registro": now_str,
        })

        await db.roddos_events.insert_one({
            "event_type": "global66.movimiento.pendiente",
            "transaction_id": transaction_id,
            "monto": monto,
            "confianza": confianza,
            "alerta_whatsapp": True,
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
            f"[Global66] Baja confianza ({confianza:.2f}) — {transaction_id} → conciliacion_partidas"
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
    """
    Daily reconciliation summary for Global66 transactions.

    Returns counts by estado for today:
      sincronizados = procesado
      pendientes    = pendiente_conciliacion
      errores       = error_verificacion
    """
    hoy = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    sincronizados = await db.global66_transacciones_procesadas.count_documents({
        "estado": "procesado",
        "fecha_registro": hoy,
    })
    pendientes = await db.global66_transacciones_procesadas.count_documents({
        "estado": "pendiente_conciliacion",
        "fecha_registro": hoy,
    })
    errores = await db.global66_transacciones_procesadas.count_documents({
        "estado": "error_verificacion",
        "fecha_registro": hoy,
    })

    logger.info(
        f"[Global66] Sync {hoy}: sincronizados={sincronizados}, "
        f"pendientes={pendientes}, errores={errores}"
    )

    return {
        "sincronizados": sincronizados,
        "pendientes": pendientes,
        "errores": errores,
        "fecha": hoy,
    }
