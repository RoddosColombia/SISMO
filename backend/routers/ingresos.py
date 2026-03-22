"""ingresos.py — BUILD 23 — F9: Ingresos No Operacionales

Endpoints:
  POST /api/ingresos/no-operacional — Register non-operational income with journal in Alegra
  GET  /api/ingresos/plan-ingresos  — Non-operational income account mappings
  GET  /api/ingresos/bancos         — Bank account mappings
"""
import logging
from datetime import datetime, timezone
from typing import Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from database import db
from dependencies import get_current_user
from alegra_service import AlegraService
from post_action_sync import post_action_sync
from routers.cfo import invalidar_cache_cfo

router = APIRouter(prefix="/ingresos", tags=["ingresos"])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class RegistrarIngresoNoOperacionalRequest(BaseModel):
    """Request schema for registering non-operational income."""
    tipo_ingreso: str              # "Intereses" | "Otros_Ingresos" | "Arrendamientos" | etc.
    monto: float                   # Amount of income
    banco_destino: str             # "Bancolombia" | "BBVA" | etc.
    fecha: Optional[str] = None    # Default: today
    descripcion: Optional[str] = None
    referencia: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR ACCOUNT LOOKUPS
# ══════════════════════════════════════════════════════════════════════════════

async def obtener_cuenta_ingreso_no_operacional(tipo_ingreso: str) -> int:
    """
    Get non-operational income account ID from MongoDB plan_ingresos_roddos.
    Searches by tipo_ingreso and returns the alegra_id.
    """
    cuenta = await db.plan_ingresos_roddos.find_one({
        "tipo_ingreso": tipo_ingreso,
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Try partial match
    cuenta = await db.plan_ingresos_roddos.find_one({
        "tipo_ingreso": {"$regex": tipo_ingreso, "$options": "i"},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Last resort: find any active non-operational income account
    cuenta = await db.plan_ingresos_roddos.find_one({
        "activo": True
    })

    if cuenta:
        logger.warning(f"[F9] Tipo ingreso '{tipo_ingreso}' no encontrado, usando {cuenta['tipo_ingreso']}")
        return cuenta["alegra_id"]

    # Fallback (should never reach this)
    logger.error(f"[F9] No se encontró ninguna cuenta de ingreso en plan_ingresos_roddos")
    raise HTTPException(status_code=500, detail="No hay cuentas de ingreso configuradas en plan_ingresos_roddos")


async def obtener_cuenta_bancaria_ingreso(banco_destino: str) -> int:
    """
    Get bank account ID from MongoDB plan_cuentas_roddos.
    Falls back to Bancolombia if bank not found.
    """
    banco_key = banco_destino.lower().strip()

    # Try exact match
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_alias": {"$in": [banco_key, banco_destino]},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Try partial match
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_alias": {"$regex": banco_key, "$options": "i"},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Default to Bancolombia
    default_cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_nombre": {"$regex": "Bancolombia", "$options": "i"},
        "activo": True
    })

    if default_cuenta:
        logger.warning(f"[F9] Banco '{banco_destino}' no encontrado, usando Bancolombia")
        return default_cuenta["alegra_id"]

    # Fallback (should never reach this)
    logger.error(f"[F9] No se encontró ninguna cuenta bancaria en plan_cuentas_roddos")
    raise HTTPException(status_code=500, detail="No hay cuentas bancarias configuradas en plan_cuentas_roddos")


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/no-operacional")
async def registrar_ingreso_no_operacional(
    payload: RegistrarIngresoNoOperacionalRequest,
    current_user=Depends(get_current_user),
):
    """
    Register non-operational income → Create journal in Alegra.

    CRITICAL FLOW:
    1. Validate: monto > 0, tipo_ingreso valid
    2. Get income account ID from plan_ingresos_roddos
    3. Get bank account ID from plan_cuentas_roddos
    4. Create journal in Alegra via POST /journals with request_with_verify()
    5. ONLY if HTTP 200 confirmed:
       - Insert ingresos_no_operacionales record
       - Publish ingreso.no_operacional.registrado event
       - Invalidate CFO cache
    6. CRITICAL: If Alegra fails → DO NOT modify MongoDB
    """
    try:
        # ── VALIDATIONS ───────────────────────────────────────────────────────
        if not payload.tipo_ingreso or not payload.tipo_ingreso.strip():
            raise HTTPException(status_code=400, detail="tipo_ingreso obligatorio")

        if payload.monto <= 0:
            raise HTTPException(status_code=400, detail="monto debe ser > 0")

        if not payload.banco_destino or not payload.banco_destino.strip():
            raise HTTPException(status_code=400, detail="banco_destino obligatorio")

        logger.info(
            f"[F9] Registrar ingreso no operacional: {payload.tipo_ingreso} - "
            f"${payload.monto:,.0f} a {payload.banco_destino}"
        )

        # ── GET ACCOUNT IDs (from MongoDB) ───────────────────────────────────
        income_account_id = await obtener_cuenta_ingreso_no_operacional(payload.tipo_ingreso)
        bank_account_id = await obtener_cuenta_bancaria_ingreso(payload.banco_destino)

        logger.info(
            f"[F9] Cuentas obtenidas: Ingreso ID {income_account_id}, "
            f"Banco ID {bank_account_id}"
        )

        # ── SET UP ALEGRA SERVICE ─────────────────────────────────────────────
        service = AlegraService(db)

        # ── CREATE JOURNAL IN ALEGRA ──────────────────────────────────────────
        fecha_ingreso = payload.fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        journal_payload = {
            "date": fecha_ingreso,
            "observations": (
                f"Ingreso no operacional: {payload.tipo_ingreso}. "
                f"Monto: ${payload.monto:,.0f}. "
                f"Banco destino: {payload.banco_destino}"
                + (f". {payload.descripcion}" if payload.descripcion else "")
            ),
            "entries": [
                {
                    "id": bank_account_id,
                    "debit": payload.monto,
                    "credit": 0
                },
                {
                    "id": income_account_id,
                    "debit": 0,
                    "credit": payload.monto
                }
            ],
            "_metadata": {
                "tipo_ingreso": payload.tipo_ingreso,
                "monto": payload.monto,
                "banco_destino": payload.banco_destino,
                "referencia": payload.referencia or "",
            }
        }

        logger.info(f"[F9] Creando journal en Alegra para ingreso ${payload.monto:,.0f}...")

        try:
            journal_response = await service.request_with_verify("journals", "POST", journal_payload)
        except Exception as e:
            logger.error(f"[F9] POST a /journals falló: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creando journal en Alegra: {str(e)}"
            )

        # ── VERIFY HTTP 200 BEFORE MODIFYING MongoDB ─────────────────────────
        if not journal_response.get("_verificado"):
            error_msg = journal_response.get("_error_verificacion", "Verificación fallida sin detalles")
            logger.error(f"[F9] Verificación de journal falló: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Journal creado pero no verificado en Alegra: {error_msg}"
            )

        # Extract journal ID
        journal_id = journal_response.get("id")
        if not journal_id:
            logger.error(f"[F9] Alegra no retornó un ID válido: {journal_response}")
            raise HTTPException(status_code=500, detail="Alegra no retornó ID del journal")

        logger.info(f"[F9] ✅ Journal creado en Alegra: ID={journal_id}")

        # ── ONLY NOW: INSERT INTO ingresos_no_operacionales (HTTP 200 CONFIRMED)
        logger.info("[F9] Insertando en ingresos_no_operacionales...")

        ingreso_record = {
            "id": f"ING-{journal_id}",
            "tipo_ingreso": payload.tipo_ingreso,
            "monto": payload.monto,
            "banco_destino": payload.banco_destino,
            "income_account_id": income_account_id,
            "bank_account_id": bank_account_id,
            "alegra_journal_id": journal_id,
            "descripcion": payload.descripcion or "",
            "referencia": payload.referencia or "",
            "fecha_ingreso": fecha_ingreso,
            "fecha_registro": datetime.now(timezone.utc).isoformat(),
        }

        await db.ingresos_no_operacionales.insert_one(ingreso_record)
        logger.info(f"[F9] Registro insertado en ingresos_no_operacionales: {ingreso_record['id']}")

        # ── PUBLISH EVENT ────────────────────────────────────────────────────
        logger.info("[F9] Publicando evento ingreso.no_operacional.registrado...")
        event_doc = {
            "event_type": "ingreso.no_operacional.registrado",
            "tipo_ingreso": payload.tipo_ingreso,
            "monto": payload.monto,
            "banco_destino": payload.banco_destino,
            "alegra_journal_id": journal_id,
            "fecha_ingreso": fecha_ingreso,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }

        await db.roddos_events.insert_one(event_doc)

        # ── POST-ACTION SYNC & CACHE INVALIDATION ───────────────────────────
        logger.info("[F9] Sincronizando con post_action_sync()...")
        try:
            await post_action_sync(
                "registrar_ingreso_no_operacional",
                {"id": journal_id},
                journal_payload,
                db,
                current_user,
                metadata={
                    "tipo_ingreso": payload.tipo_ingreso,
                    "monto": payload.monto,
                }
            )
        except Exception as e:
            logger.warning(f"[F9] post_action_sync falló (no fatal): {str(e)[:100]}")

        logger.info("[F9] Invalidando CFO cache...")
        try:
            await invalidar_cache_cfo()
        except Exception as e:
            logger.warning(f"[F9] Error invalidando CFO cache: {str(e)[:100]}")

        # ── RESPONSE ──────────────────────────────────────────────────────────
        logger.info(f"[F9] ✅ Ingreso no operacional registrado exitosamente")

        return {
            "success": True,
            "journal_id": journal_id,
            "tipo_ingreso": payload.tipo_ingreso,
            "monto": payload.monto,
            "banco_destino": payload.banco_destino,
            "income_account_id": income_account_id,
            "bank_account_id": bank_account_id,
            "fecha_ingreso": fecha_ingreso,
            "mensaje": (
                f"✅ Ingreso no operacional registrado. "
                f"Journal en Alegra: {journal_id}. "
                f"Monto: ${payload.monto:,.0f}"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F9] Error registrando ingreso: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registrando ingreso: {str(e)[:200]}")


@router.get("/plan-ingresos")
async def get_plan_ingresos(current_user=Depends(get_current_user)):
    """Get non-operational income account mappings from MongoDB."""
    try:
        planes = await db.plan_ingresos_roddos.find({}, {"_id": 0, "tipo_ingreso": 1, "alegra_id": 1, "cuenta_nombre": 1}).to_list(None)
        return {
            "plan_ingresos": planes or [],
            "total": len(planes) if planes else 0,
        }
    except Exception as e:
        logger.error(f"[F9] Error: {str(e)}")
        return {"plan_ingresos": [], "total": 0}


@router.get("/bancos")
async def get_bancos(current_user=Depends(get_current_user)):
    """Get bank account mappings from MongoDB."""
    bancos = await db.plan_cuentas_roddos.find({
        "tipo": "banco",
        "activo": True
    }).to_list(None)
    return {
        "bancos": bancos,
        "total": len(bancos),
    }
