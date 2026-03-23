"""cxc_socios.py — BUILD 23 — F8: CXC Socios en Tiempo Real

Endpoints:
  GET  /api/cxc/socios/saldo        — Get current balance for each partner
  POST /api/cxc/socios/abono        — Register partner repayment
  GET  /api/cxc/socios/directorio   — Get partner directory
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

router = APIRouter(prefix="/cxc/socios", tags=["cxc_socios"])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# DIRECTORIO DE SOCIOS — RODDOS SAS
# ══════════════════════════════════════════════════════════════════════════════

DIRECTORIO_SOCIOS = [
    {
        "nombre": "Andrés Sanjuan",
        "cedula": "80075452",
        "rol": "Socio/Propietario",
        "activo": True,
    },
    {
        "nombre": "Iván Echeverri",
        "cedula": "80086601",
        "rol": "Socio/Propietario",
        "activo": True,
    },
]

# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS FOR ACCOUNT LOOKUPS
# ══════════════════════════════════════════════════════════════════════════════

async def obtener_cuenta_cxc_socios() -> int:
    """
    Get CXC Socios account ID from MongoDB plan_cuentas_roddos.
    Defaults to standard CXC Socios account.
    """
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "cxc",
        "cxc_tipo": "socios",
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    # Fallback search
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "cxc",
        "cuenta_nombre": {"$regex": "[Ss]ocios", "$options": "i"},
        "activo": True
    })

    if cuenta:
        return cuenta["alegra_id"]

    logger.warning("[F8] Cuenta CXC Socios no encontrada en plan_cuentas_roddos, usando fallback 5491")
    return 5491


async def obtener_cuenta_bancaria_cxc(banco_origen: str) -> int:
    """
    Get bank account ID from MongoDB plan_cuentas_roddos for CXC operations.
    Falls back to Bancolombia if bank not found.
    """
    banco_key = banco_origen.lower().strip()

    # Try exact match
    cuenta = await db.plan_cuentas_roddos.find_one({
        "tipo": "banco",
        "banco_alias": {"$in": [banco_key, banco_origen]},
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
        return default_cuenta["alegra_id"]

    logger.warning(f"[F8] Banco '{banco_origen}' no encontrado en plan_cuentas_roddos, usando fallback 5314")
    return 5314

# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class RegistrarAbonoRequest(BaseModel):
    """Request schema for registering partner repayment."""
    cedula_socio: str           # "80075452" for Andrés
    monto_abono: float          # Amount being repaid
    fecha: Optional[str] = None # Default: today
    metodo_pago: str            # "transferencia" | "efectivo" | "cheque"
    banco_origen: Optional[str] = None  # Bank account where money arrived
    observaciones: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def obtener_socio_por_cedula(cedula: str) -> Optional[dict]:
    """Get partner info by ID number."""
    for socio in DIRECTORIO_SOCIOS:
        if socio["cedula"] == cedula:
            return socio
    return None


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/saldo")
async def get_saldo_socios(
    cedula: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """
    Get current CXC Socios balance.

    If cedula provided: return specific partner's balance
    If no cedula: return all partners' balances
    """
    try:
        if cedula:
            # Specific partner
            socio = obtener_socio_por_cedula(cedula.strip())
            if not socio:
                raise HTTPException(status_code=400, detail=f"Socio con cédula {cedula} no encontrado")

            logger.info(f"[F8] Consultando saldo de {socio['nombre']} (CC {cedula})...")

            # Get CXC document for this partner
            cxc_doc = await db.cxc_socios.find_one({"cedula": cedula.strip()})

            if not cxc_doc:
                # No CXC record yet — balance is 0
                saldo_pendiente = 0
                movimientos = []
            else:
                saldo_pendiente = cxc_doc.get("saldo_pendiente", 0)
                movimientos = cxc_doc.get("movimientos", [])

            logger.info(f"[F8] Saldo {socio['nombre']}: ${saldo_pendiente:,.0f}")

            return {
                "socio": socio,
                "saldo_pendiente": saldo_pendiente,
                "num_movimientos": len(movimientos),
                "movimientos": movimientos[-10:] if movimientos else [],  # Last 10
                "ultimo_movimiento": movimientos[-1] if movimientos else None,
                "fecha_consulta": datetime.now(timezone.utc).isoformat(),
            }

        else:
            # All partners
            logger.info("[F8] Consultando saldos de todos los socios...")

            socios_saldos = []
            for socio in DIRECTORIO_SOCIOS:
                if socio["activo"]:
                    cxc_doc = await db.cxc_socios.find_one({"cedula": socio["cedula"]})
                    saldo_pendiente = cxc_doc.get("saldo_pendiente", 0) if cxc_doc else 0

                    socios_saldos.append({
                        "nombre": socio["nombre"],
                        "cedula": socio["cedula"],
                        "saldo_pendiente": saldo_pendiente,
                        "num_movimientos": len(cxc_doc.get("movimientos", [])) if cxc_doc else 0,
                    })

            return {
                "total_socios": len(socios_saldos),
                "socios": socios_saldos,
                "fecha_consulta": datetime.now(timezone.utc).isoformat(),
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F8] Error consultando saldo: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error consultando saldo: {str(e)[:200]}")


@router.post("/abono")
async def registrar_abono_socio(
    payload: RegistrarAbonoRequest,
    current_user=Depends(get_current_user),
):
    """
    Register partner repayment.

    CRITICAL FLOW:
    1. Validate cedula + monto
    2. Create journal in Alegra:
       DEBIT: Bank account (where money arrived)
       CREDIT: CXC Socios (partner account)
    3. request_with_verify() HTTP 200
    4. ONLY if HTTP 200: update CXC Socios balance in MongoDB
    5. Publish cxc.socio.abono event
    """
    try:
        # ── VALIDATIONS ───────────────────────────────────────────────────────
        if not payload.cedula_socio or not payload.cedula_socio.strip():
            raise HTTPException(status_code=400, detail="cedula_socio obligatoria")

        cedula = payload.cedula_socio.strip()
        socio = obtener_socio_por_cedula(cedula)
        if not socio:
            raise HTTPException(status_code=400, detail=f"Socio con cédula {cedula} no encontrado")

        if payload.monto_abono <= 0:
            raise HTTPException(status_code=400, detail="monto_abono debe ser > 0")

        if not payload.metodo_pago or not payload.metodo_pago.strip():
            raise HTTPException(status_code=400, detail="metodo_pago obligatorio")

        logger.info(
            f"[F8] Registrar abono de {socio['nombre']}: ${payload.monto_abono:,.0f} "
            f"({payload.metodo_pago})"
        )

        # ── SET UP ALEGRA SERVICE ─────────────────────────────────────────────
        service = AlegraService(db)

        # ── DETERMINE BANK ACCOUNT (from MongoDB plan_cuentas_roddos) ─────────
        banco_origin = payload.banco_origen or "Bancolombia"
        bank_account_id = await obtener_cuenta_bancaria_cxc(banco_origin)
        logger.info(f"[F8] Banco origen: {banco_origin} → Cuenta ID {bank_account_id} (desde plan_cuentas_roddos)")

        # ── CREATE JOURNAL IN ALEGRA ──────────────────────────────────────────
        fecha_abono = payload.fecha or datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Get CXC Socios account from MongoDB
        cuenta_cxc_socios = await obtener_cuenta_cxc_socios()
        logger.info(f"[F8] Cuenta CXC Socios: ID {cuenta_cxc_socios} (desde plan_cuentas_roddos)")

        journal_payload = {
            "date": fecha_abono,
            "observations": (
                f"Abono CXC Socio {socio['nombre']} (CC {cedula}). "
                f"Monto: ${payload.monto_abono:,.0f}. "
                f"Método: {payload.metodo_pago}"
            ),
            "entries": [
                {
                    "id": bank_account_id,
                    "debit": payload.monto_abono,
                    "credit": 0
                },
                {
                    "id": cuenta_cxc_socios,
                    "debit": 0,
                    "credit": payload.monto_abono
                }
            ],
            "_metadata": {
                "cedula_socio": cedula,
                "nombre_socio": socio["nombre"],
                "tipo_movimiento": "abono",
                "metodo_pago": payload.metodo_pago,
            }
        }

        logger.info(f"[F8] Creando journal en Alegra para abono ${payload.monto_abono:,.0f}...")

        try:
            journal_response = await service.request_with_verify("journals", "POST", journal_payload)
        except Exception as e:
            logger.error(f"[F8] POST a /journals falló: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error creando journal en Alegra: {str(e)}")

        # ── VERIFY HTTP 200 BEFORE MODIFYING CXC_SOCIOS ───────────────────────
        if not journal_response.get("_verificado"):
            error_msg = journal_response.get("_error_verificacion", "Verificación fallida")
            logger.error(f"[F8] Verificación de journal falló: {error_msg}")
            raise HTTPException(status_code=500, detail=f"Journal no verificado en Alegra: {error_msg}")

        journal_id = journal_response.get("id")
        if not journal_id:
            raise HTTPException(status_code=500, detail="Alegra no retornó ID del journal")

        logger.info(f"[F8] ✅ Journal creado en Alegra: ID={journal_id}")

        # ── ONLY NOW: UPDATE CXC_SOCIOS (HTTP 200 CONFIRMED) ──────────────────
        logger.info(f"[F8] Actualizando saldo de {socio['nombre']}...")

        # Get or create CXC document
        cxc_doc = await db.cxc_socios.find_one({"cedula": cedula})

        if not cxc_doc:
            # Create new CXC document
            saldo_anterior = 0
            movimientos = []
        else:
            saldo_anterior = cxc_doc.get("saldo_pendiente", 0)
            movimientos = cxc_doc.get("movimientos", [])

        # Calculate new balance
        nuevo_saldo = saldo_anterior - payload.monto_abono  # Abono reduces debt

        # Create movement record
        movimiento = {
            "tipo": "abono",
            "monto": payload.monto_abono,
            "saldo_anterior": saldo_anterior,
            "saldo_nuevo": nuevo_saldo,
            "metodo_pago": payload.metodo_pago,
            "banco_origen": banco_origin,
            "alegra_journal_id": journal_id,
            "observaciones": payload.observaciones or "",
            "fecha": fecha_abono,
            "fecha_registro": datetime.now(timezone.utc).isoformat(),
        }

        movimientos.append(movimiento)

        # Update or insert CXC document
        if not cxc_doc:
            cxc_new_doc = {
                "cedula": cedula,
                "nombre_socio": socio["nombre"],
                "saldo_pendiente": nuevo_saldo,
                "movimientos": movimientos,
                "fecha_actualizado": datetime.now(timezone.utc).isoformat(),
            }
            await db.cxc_socios.insert_one(cxc_new_doc)
            logger.info(f"[F8] CXC documento creado para {socio['nombre']}")
        else:
            await db.cxc_socios.update_one(
                {"cedula": cedula},
                {
                    "$set": {
                        "saldo_pendiente": nuevo_saldo,
                        "movimientos": movimientos,
                        "fecha_actualizado": datetime.now(timezone.utc).isoformat(),
                    }
                }
            )
            logger.info(f"[F8] Saldo actualizado: ${saldo_anterior:,.0f} → ${nuevo_saldo:,.0f}")

        # ── PUBLISH EVENT ────────────────────────────────────────────────────
        logger.info("[F8] Publicando evento cxc.socio.abono...")
        event_doc = {
            "event_type": "cxc.socio.abono",
            "cedula_socio": cedula,
            "nombre_socio": socio["nombre"],
            "monto_abono": payload.monto_abono,
            "saldo_anterior": saldo_anterior,
            "saldo_nuevo": nuevo_saldo,
            "alegra_journal_id": journal_id,
            "metodo_pago": payload.metodo_pago,
            "fecha_pago": fecha_abono,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }

        await db.roddos_events.insert_one(event_doc)

        # ── POST-ACTION SYNC & CACHE INVALIDATION ───────────────────────────
        logger.info("[F8] Sincronizando con post_action_sync()...")
        try:
            await post_action_sync(
                "registrar_abono_socio",
                {"id": journal_id, "cedula": cedula},
                journal_payload,
                db,
                current_user,
                metadata={
                    "cedula_socio": cedula,
                    "nombre_socio": socio["nombre"],
                    "nuevo_saldo": nuevo_saldo,
                }
            )
        except Exception as e:
            logger.warning(f"[F8] post_action_sync falló (no fatal): {str(e)[:100]}")

        logger.info("[F8] Invalidando CFO cache...")
        try:
            await invalidar_cache_cfo()
        except Exception as e:
            logger.warning(f"[F8] Error invalidando CFO cache: {str(e)[:100]}")

        # ── RESPONSE ──────────────────────────────────────────────────────────
        logger.info(f"[F8] ✅ Abono registrado exitosamente")

        return {
            "success": True,
            "journal_id": journal_id,
            "cedula_socio": cedula,
            "nombre_socio": socio["nombre"],
            "monto_abono": payload.monto_abono,
            "saldo_anterior": saldo_anterior,
            "saldo_nuevo": nuevo_saldo,
            "metodo_pago": payload.metodo_pago,
            "mensaje": (
                f"✅ Abono de ${payload.monto_abono:,.0f} registrado para {socio['nombre']}. "
                f"Saldo pendiente: ${nuevo_saldo:,.0f}. Journal: {journal_id}"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F8] Error registrando abono: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registrando abono: {str(e)[:200]}")


@router.get("/directorio")
async def get_directorio_socios(current_user=Depends(get_current_user)):
    """Get partner directory with contact info."""
    return {
        "socios": DIRECTORIO_SOCIOS,
        "total": len([s for s in DIRECTORIO_SOCIOS if s["activo"]]),
    }


@router.get("/plan-cuentas")
async def get_plan_cuentas_cxc(current_user=Depends(get_current_user)):
    """Get CXC Socios and bank account mappings from MongoDB."""
    cuentas = await db.plan_cuentas_roddos.find({
        "tipo": {"$in": ["cxc", "banco"]},
        "activo": True
    }).to_list(None)

    return {
        "cuentas": cuentas,
        "total": len(cuentas),
    }


@router.get("/bancos")
async def get_bancos_cxc(current_user=Depends(get_current_user)):
    """Get bank accounts for CXC abonos."""
    bancos = await db.plan_cuentas_roddos.find({"tipo": "banco", "activo": True}).to_list(None)
    return {
        "bancos": bancos or [],
        "total": len(bancos) if bancos else 0,
    }
