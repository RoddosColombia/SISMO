"""cartera.py — BUILD 23 — F7: Ingresos por Cuotas de Cartera

Endpoints:
  POST /api/cartera/registrar-pago      — Create income journal in Alegra for quota payment
  GET  /api/cartera/plan-ingresos       — Financial income account mappings
  GET  /api/cartera/bancos              — Bank account mappings
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

router = APIRouter(prefix="/cartera", tags=["cartera"])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR ACCOUNT LOOKUPS
# ══════════════════════════════════════════════════════════════════════════════

async def obtener_cuenta_bancaria(banco_origen: str) -> int:
    """
    Get bank account ID from MongoDB plan_cuentas_roddos.
    Falls back to Bancolombia if bank not found.
    """
    banco_key = banco_origen.lower().strip()

    # Try exact match in plan_cuentas_roddos
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_alias": {"$in": [banco_key, banco_origen]},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # If not found, try partial match
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_alias": {"$regex": banco_key, "$options": "i"},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Default to Bancolombia if not found
    default_cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_nombre": {"$regex": "Bancolombia", "$options": "i"},
        "activo": True
    })

    if default_cuenta:
        return default_cuenta["alegra_id"]

    # Fallback: return 111005 Bancolombia (should never reach this)
    logger.warning(f"[F7] Banco '{banco_origen}' no encontrado en plan_cuentas_roddos, usando fallback 111005 (Bancolombia)")
    return 111005


async def obtener_cuenta_ingreso(tipo_ingreso: str = "Intereses_Financieros_Cartera") -> int:
    """
    Get income account ID from MongoDB plan_ingresos_roddos.
    Defaults to Intereses Financieros.
    """
    cuenta = await db.plan_ingresos_roddos.find_one({
        "tipo_ingreso": tipo_ingreso,
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Fallback: search for any active income account
    cuenta = await db.plan_ingresos_roddos.find_one({
        "tipo_ingreso": {"$in": [
            "Intereses_Financieros_Cartera",
            "Intereses_Financieros",
            "Ingresos_Financieros"
        ]},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Last resort fallback: return 5455 (should never reach this)
    logger.warning(f"[F7] Tipo ingreso '{tipo_ingreso}' no encontrado en plan_ingresos_roddos, usando fallback 5455")
    return 5455


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class RegistrarPagoRequest(BaseModel):
    """Request schema for registering a quota payment."""
    loanbook_id: str              # LB-2026-0042
    cliente_nombre: str            # Cliente nombre
    monto_pago: float             # Amount paid
    numero_cuota: Optional[int]   # Cuota número (if known)
    metodo_pago: str              # "transferencia" | "efectivo" | "nequi" | "otro"
    banco_origen: str             # "Bancolombia" | "BBVA" | etc.
    referencia_pago: Optional[str] = None  # Transaction ID / reference
    observaciones: Optional[str] = None    # Extra notes
    fecha_pago: Optional[str] = None      # Default: today


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/registrar-pago")
async def registrar_pago_cartera(
    payload: RegistrarPagoRequest,
    current_user=Depends(get_current_user),
):
    """
    Register a quota payment → Create income journal in Alegra.

    CRITICAL FLOW:
    1. Validate: monto_pago > 0, loanbook_id valid
    2. Find loanbook + oldest pending cuota
    3. Get income account ID from plan_ingresos_roddos
    4. Create journal in Alegra via POST /journals with request_with_verify()
    5. ONLY if HTTP 200 confirmed:
       - Mark cuota as "pagada"
       - Update loanbook.saldo_pendiente
       - Insert cartera_pagos record
       - Publish pago.cuota.registrado event
       - Invalidate CFO cache
    6. CRITICAL: If Alegra fails → DO NOT modify loanbook
    """
    try:
        # ── VALIDATIONS ───────────────────────────────────────────────────────
        if not payload.loanbook_id or not payload.loanbook_id.strip():
            raise HTTPException(status_code=400, detail="loanbook_id obligatorio")

        if payload.monto_pago <= 0:
            raise HTTPException(status_code=400, detail="monto_pago debe ser > 0")

        if not payload.cliente_nombre or not payload.cliente_nombre.strip():
            raise HTTPException(status_code=400, detail="cliente_nombre obligatorio")

        if not payload.metodo_pago or not payload.metodo_pago.strip():
            raise HTTPException(status_code=400, detail="metodo_pago obligatorio")

        if not payload.banco_origen or not payload.banco_origen.strip():
            raise HTTPException(status_code=400, detail="banco_origen obligatorio")

        # ── FIND LOANBOOK ─────────────────────────────────────────────────────
        logger.info(f"[F7] Buscando loanbook {payload.loanbook_id}...")

        # Búsqueda robusta: soportar múltiples formatos de ID
        loanbook = None
        loanbook_query_id = payload.loanbook_id.strip()

        # Intentar búsqueda por múltiples campos y formatos
        # 1. Búsqueda exacta por "id"
        loanbook = await db.loanbook.find_one({"id": loanbook_query_id})

        # 2. Si no encuentra, buscar por "codigo"
        if not loanbook:
            loanbook = await db.loanbook.find_one({"codigo": loanbook_query_id})
            if loanbook:
                logger.info(f"[F7] Encontrado por campo 'codigo': {loanbook_query_id}")

        # 3. Si no encuentra y el ID tiene formato "LB-XXXX-XXXX", extraer el número y buscar
        if not loanbook and loanbook_query_id.startswith("LB-"):
            # Extraer el número secuencial (ej: "LB-2026-0001" → "0001")
            try:
                parts = loanbook_query_id.split("-")
                if len(parts) == 3:
                    # Buscar por patrón alternativo: codigo = "LB" + número
                    alt_codigo = f"LB{parts[2]}"
                    loanbook = await db.loanbook.find_one({"codigo": alt_codigo})
                    if loanbook:
                        logger.info(f"[F7] Encontrado por código alternativo: {alt_codigo}")
            except Exception as e:
                logger.warning(f"[F7] Error procesando formato LB-XXXX-XXXX: {str(e)}")

        # 4. Si todavía no encuentra, buscar por expresión regular
        if not loanbook:
            import re
            pattern = re.escape(loanbook_query_id)
            loanbook = await db.loanbook.find_one({
                "$or": [
                    {"id": {"$regex": pattern, "$options": "i"}},
                    {"codigo": {"$regex": pattern, "$options": "i"}},
                    {"loanbook_id": {"$regex": pattern, "$options": "i"}}
                ]
            })
            if loanbook:
                logger.info(f"[F7] Encontrado por búsqueda regex: {loanbook_query_id}")

        if not loanbook:
            raise HTTPException(status_code=400, detail=f"Loanbook {payload.loanbook_id} no encontrado")

        # ── FIND OLDEST PENDING CUOTA ─────────────────────────────────────────
        cuotas = loanbook.get("cuotas", [])
        pending_cuotas = [c for c in cuotas if c.get("estado") == "pendiente"]

        if not pending_cuotas:
            raise HTTPException(status_code=400, detail="No hay cuotas pendientes en este loanbook")

        # Find oldest pending cuota (lowest numero)
        cuota_a_pagar = min(pending_cuotas, key=lambda c: c.get("numero", 999))
        cuota_numero = cuota_a_pagar.get("numero")
        cuota_valor = cuota_a_pagar.get("valor", 0)

        # Validate payment amount matches cuota value
        if abs(payload.monto_pago - cuota_valor) > 1:
            logger.warning(
                f"[F7] Advertencia: monto_pago ${payload.monto_pago} ≠ cuota_valor ${cuota_valor}"
            )
            # Allow it but log warning

        logger.info(
            f"[F7] Cuota {cuota_numero} encontrada: ${cuota_valor}. "
            f"Pago registrado: ${payload.monto_pago}"
        )

        # ── GET INCOME ACCOUNT ID (from MongoDB plan_ingresos_roddos) ─────────
        income_account_id = await obtener_cuenta_ingreso("Intereses_Financieros_Cartera")
        logger.info(f"[F7] Cuenta de ingreso: ID {income_account_id} (desde plan_ingresos_roddos)")

        # ── GET BANK ACCOUNT ID (from MongoDB plan_cuentas_roddos) ──────────────
        bank_account_id = await obtener_cuenta_bancaria(payload.banco_origen)
        logger.info(f"[F7] Banco: {payload.banco_origen} → Cuenta ID {bank_account_id} (desde plan_cuentas_roddos)")

        # ── SET UP ALEGRA SERVICE ─────────────────────────────────────────────
        service = AlegraService(db)

        # ── CREATE JOURNAL IN ALEGRA ──────────────────────────────────────────
        fecha_pago = payload.fecha_pago or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        journal_payload = {
            "date": fecha_pago,
            "observations": (
                f"Pago cuota #{cuota_numero} - {payload.cliente_nombre}. "
                f"Referencia: {payload.referencia_pago or 'N/A'}. "
                f"Método: {payload.metodo_pago}"
            ),
            "entries": [
                {
                    "id": bank_account_id,
                    "debit": payload.monto_pago,
                    "credit": 0
                },
                {
                    "id": income_account_id,
                    "debit": 0,
                    "credit": payload.monto_pago
                }
            ],
            "_metadata": {
                "loanbook_id": payload.loanbook_id,
                "cuota_numero": cuota_numero,
                "cliente_nombre": payload.cliente_nombre,
                "banco_origen": payload.banco_origen,
                "metodo_pago": payload.metodo_pago,
            }
        }

        logger.info(f"[F7] Creando journal en Alegra para pago ${payload.monto_pago}...")

        try:
            journal_response = await service.request_with_verify("journals", "POST", journal_payload)
        except Exception as e:
            logger.error(f"[F7] POST a /journals falló: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creando journal en Alegra: {str(e)}"
            )

        # ── VERIFY HTTP 200 BEFORE MODIFYING LOANBOOK ─────────────────────────
        if not journal_response.get("_verificado"):
            error_msg = journal_response.get("_error_verificacion", "Verificación fallida sin detalles")
            logger.error(f"[F7] Verificación de journal falló: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Journal creado pero no verificado en Alegra: {error_msg}"
            )

        # Extract journal ID
        journal_id = journal_response.get("id")
        if not journal_id:
            logger.error(f"[F7] Alegra no retornó un ID válido: {journal_response}")
            raise HTTPException(status_code=500, detail="Alegra no retornó ID del journal")

        logger.info(f"[F7] ✅ Journal creado en Alegra: ID={journal_id}")

        # ── ONLY NOW: MODIFY LOANBOOK (HTTP 200 CONFIRMED) ──────────────────
        logger.info(f"[F7] Marcando cuota {cuota_numero} como pagada...")

        # Update cuota state
        for idx, c in enumerate(cuotas):
            if c.get("numero") == cuota_numero:
                cuotas[idx]["estado"] = "pagada"
                cuotas[idx]["fecha_pago"] = fecha_pago
                cuotas[idx]["alegra_journal_id"] = journal_id
                break

        # Calculate new saldo_pendiente
        saldo_pendiente = loanbook.get("saldo_pendiente", loanbook.get("precio_venta", 0))
        saldo_pendiente -= payload.monto_pago

        # Update loanbook
        await db.loanbook.update_one(
            {"id": payload.loanbook_id.strip()},
            {
                "$set": {
                    "cuotas": cuotas,
                    "saldo_pendiente": saldo_pendiente,
                    "ultima_cuota_pagada": cuota_numero,
                    "fecha_ultimo_pago": fecha_pago,
                }
            }
        )

        logger.info(
            f"[F7] Loanbook actualizado: cuota {cuota_numero} marcada pagada, "
            f"saldo_pendiente = ${saldo_pendiente}"
        )

        # ── INSERT INTO cartera_pagos ────────────────────────────────────────
        pago_record = {
            "id": f"PAGO-{journal_id}",
            "loanbook_id": payload.loanbook_id.strip(),
            "cuota_numero": cuota_numero,
            "cliente_nombre": payload.cliente_nombre,
            "monto_pago": payload.monto_pago,
            "metodo_pago": payload.metodo_pago,
            "banco_origen": payload.banco_origen,
            "referencia_pago": payload.referencia_pago or "",
            "alegra_journal_id": journal_id,
            "fecha_pago": fecha_pago,
            "fecha_registro": datetime.now(timezone.utc).isoformat(),
            "observaciones": payload.observaciones or "",
        }

        await db.cartera_pagos.insert_one(pago_record)
        logger.info(f"[F7] Registro insertado en cartera_pagos: {pago_record['id']}")

        # ── PUBLISH EVENT ────────────────────────────────────────────────────
        logger.info("[F7] Publicando evento pago.cuota.registrado...")
        event_doc = {
            "event_type": "pago.cuota.registrado",
            "loanbook_id": payload.loanbook_id.strip(),
            "cuota_numero": cuota_numero,
            "monto_pago": payload.monto_pago,
            "cliente_nombre": payload.cliente_nombre,
            "alegra_journal_id": journal_id,
            "saldo_pendiente": saldo_pendiente,
            "metodo_pago": payload.metodo_pago,
            "fecha_pago": fecha_pago,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }

        await db.roddos_events.insert_one(event_doc)

        # ── POST-ACTION SYNC & CACHE INVALIDATION ───────────────────────────
        logger.info("[F7] Sincronizando con post_action_sync()...")
        try:
            await post_action_sync(
                "registrar_pago_cartera",
                {"id": journal_id, "loanbook_id": payload.loanbook_id},
                journal_payload,
                db,
                current_user,
                metadata={
                    "loanbook_id": payload.loanbook_id,
                    "cuota_numero": cuota_numero,
                    "saldo_pendiente": saldo_pendiente,
                }
            )
        except Exception as e:
            logger.warning(f"[F7] post_action_sync falló (no fatal): {str(e)[:100]}")

        logger.info("[F7] Invalidando CFO cache...")
        try:
            await invalidar_cache_cfo()
        except Exception as e:
            logger.warning(f"[F7] Error invalidando CFO cache: {str(e)[:100]}")

        # ── RESPONSE ──────────────────────────────────────────────────────────
        logger.info(f"[F7] ✅ Pago registrado exitosamente. Journal: {journal_id}")

        return {
            "success": True,
            "journal_id": journal_id,
            "loanbook_id": payload.loanbook_id,
            "cuota_numero": cuota_numero,
            "monto_pago": payload.monto_pago,
            "saldo_pendiente": saldo_pendiente,
            "fecha_pago": fecha_pago,
            "mensaje": (
                f"✅ Pago cuota #{cuota_numero} registrado. "
                f"Journal en Alegra: {journal_id}. "
                f"Saldo pendiente: ${saldo_pendiente:,.0f}"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F7] Error registrando pago: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registrando pago: {str(e)[:200]}")


@router.get("/plan-ingresos")
async def get_plan_ingresos(current_user=Depends(get_current_user)):
    """Get financial income account mappings from MongoDB."""
    try:
        planes = await db.plan_ingresos_roddos.find({}, {"_id": 0, "tipo_ingreso": 1, "alegra_id": 1, "cuenta_nombre": 1}).to_list(None)
        return {
            "plan_ingresos": planes or [],
            "total": len(planes) if planes else 0,
        }
    except Exception as e:
        logger.error(f"[F7] Error: {str(e)}")
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
