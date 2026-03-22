"""nomina.py — BUILD 23 — F4: Módulo Nómina Mensual

Endpoints:
  POST /api/nomina/registrar        — Register monthly payroll → create journal in Alegra
  GET  /api/nomina/historial        — Get payroll history
  GET  /api/nomina/plan-cuentas     — Payroll account mappings
"""
import logging
import hashlib
from datetime import datetime, timezone
from typing import List, Optional
from pydantic import BaseModel

from fastapi import APIRouter, Depends, HTTPException
from database import db
from dependencies import get_current_user
from alegra_service import AlegraService
from post_action_sync import post_action_sync
from routers.cfo import invalidar_cache_cfo

router = APIRouter(prefix="/nomina", tags=["nomina"])
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════════════════════
# PLAN DE CUENTAS NÓMINA — RODDOS SAS
# ══════════════════════════════════════════════════════════════════════════════

PLAN_CUENTAS_NOMINA = {
    "sueldos_base": 5462,  # Sueldos (cuenta de gasto)
    "aportes_eps": 5465,   # Aportes a salud (si aplica)
    "aportes_arl": 5466,   # Aportes a riesgos (si aplica)
}

BANCOS_PAGO_NOMINA = {
    "bancolombia": 5314,
    "bancolombia 2029": 5314,
    "bbva": 5318,
    "davivienda": 5322,
    "banco de bogota": 5321,
}

DEFAULT_BANCO_PAGO = 5314  # Bancolombia 2029
DEFAULT_CUENTA_SUELDOS = 5462


# ══════════════════════════════════════════════════════════════════════════════
# REQUEST SCHEMAS
# ══════════════════════════════════════════════════════════════════════════════

class Empleado(BaseModel):
    """Empleado y su monto de nómina."""
    nombre: str
    monto: float


class RegistrarNominaRequest(BaseModel):
    """Request schema for registering monthly payroll."""
    mes: str              # "YYYY-MM" format
    empleados: List[Empleado]
    banco_pago: str       # "Bancolombia" | "BBVA" | etc.
    observaciones: Optional[str] = None


# ══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ══════════════════════════════════════════════════════════════════════════════

def calcular_hash_empleados(empleados: List[Empleado]) -> str:
    """
    Calculate hash of employees for duplicate detection.
    Hash is based on sorted empleado names to detect duplicates regardless of order.
    """
    nombres_sorted = sorted([e.nombre.lower().strip() for e in empleados])
    hash_input = ",".join(nombres_sorted)
    return hashlib.sha256(hash_input.encode()).hexdigest()[:16]


async def verificar_nomina_existente(mes: str, empleados: List[Empleado]) -> Optional[dict]:
    """
    Check if payroll for this month and employee set already exists.
    Returns existing document if found, None otherwise.
    """
    empleados_hash = calcular_hash_empleados(empleados)
    existing = await db.nomina_registros.find_one({
        "mes": mes,
        "empleados_hash": empleados_hash
    })
    return existing


# ══════════════════════════════════════════════════════════════════════════════
# ENDPOINTS
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/registrar")
async def registrar_nomina(
    payload: RegistrarNominaRequest,
    current_user=Depends(get_current_user),
):
    """
    Register monthly payroll and create journal in Alegra.

    CRITICAL FLOW:
    1. Validate: mes format, empleados list not empty
    2. Check for duplicates: verify mes + empleados_hash not already registered
    3. Calculate total payroll
    4. Determine bank account ID
    5. Create journal in Alegra via POST /journals with request_with_verify()
    6. ONLY if HTTP 200 confirmed:
       - Insert nomina_registros with alegra_journal_id
       - Publish nomina.registrada event
       - Call post_action_sync() and invalidar_cache_cfo()
    7. Return: journal_id + total + mes
    """
    try:
        # ── VALIDATIONS ───────────────────────────────────────────────────────
        if not payload.mes or not payload.mes.strip():
            raise HTTPException(status_code=400, detail="mes obligatorio (formato YYYY-MM)")

        # Validate mes format (YYYY-MM)
        try:
            datetime.strptime(payload.mes, "%Y-%m")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Formato mes inválido: {payload.mes}. Use YYYY-MM (ej: 2026-01)"
            )

        if not payload.empleados or len(payload.empleados) == 0:
            raise HTTPException(status_code=400, detail="empleados list no puede estar vacía")

        for emp in payload.empleados:
            if not emp.nombre or not emp.nombre.strip():
                raise HTTPException(status_code=400, detail="Nombre de empleado obligatorio")
            if emp.monto <= 0:
                raise HTTPException(status_code=400, detail=f"Monto para {emp.nombre} debe ser > 0")

        if not payload.banco_pago or not payload.banco_pago.strip():
            raise HTTPException(status_code=400, detail="banco_pago obligatorio")

        logger.info(
            f"[F4] Registrar nómina {payload.mes}: {len(payload.empleados)} empleados, "
            f"total ${sum(e.monto for e in payload.empleados):,.0f}"
        )

        # ── ANTI-DUPLICADOS: CHECK IF ALREADY REGISTERED ──────────────────────
        existing = await verificar_nomina_existente(payload.mes, payload.empleados)
        if existing:
            logger.warning(f"[F4] Nómina de {payload.mes} ya registrada (journal: {existing.get('alegra_journal_id')})")
            raise HTTPException(
                status_code=409,
                detail=f"Nómina de {payload.mes} ya registrada. Journal: {existing.get('alegra_journal_id')}"
            )

        # ── CALCULATE TOTALS ──────────────────────────────────────────────────
        total_nomina = sum(emp.monto for emp in payload.empleados)
        logger.info(f"[F4] Total nómina: ${total_nomina:,.0f}")

        # ── GET BANK ACCOUNT ID ───────────────────────────────────────────────
        banco_key = payload.banco_pago.lower().strip()
        bank_account_id = BANCOS_PAGO_NOMINA.get(banco_key, DEFAULT_BANCO_PAGO)
        logger.info(f"[F4] Banco pago: {payload.banco_pago} → Cuenta ID {bank_account_id}")

        # ── SET UP ALEGRA SERVICE ─────────────────────────────────────────────
        service = AlegraService(db)

        # ── CREATE JOURNAL IN ALEGRA ──────────────────────────────────────────
        fecha_nomina = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        # Build entries: one DEBIT per employee + one CREDIT for bank
        entries = []

        # DEBITS: One per employee on Sueldos account (5462)
        for emp in payload.empleados:
            entries.append({
                "id": DEFAULT_CUENTA_SUELDOS,
                "debit": emp.monto,
                "credit": 0
            })

        # CREDIT: Total payroll to bank account
        entries.append({
            "id": bank_account_id,
            "debit": 0,
            "credit": total_nomina
        })

        journal_payload = {
            "date": fecha_nomina,
            "observations": (
                f"Nómina {payload.mes} — {len(payload.empleados)} empleados — "
                f"Total: ${total_nomina:,.0f}"
            ),
            "entries": entries,
            "_metadata": {
                "mes": payload.mes,
                "num_empleados": len(payload.empleados),
                "total_nomina": total_nomina,
                "banco_pago": payload.banco_pago,
            }
        }

        logger.info(
            f"[F4] Creando journal en Alegra con {len(entries)} líneas "
            f"({len(payload.empleados)} débitos + 1 crédito)..."
        )

        try:
            journal_response = await service.request_with_verify("journals", "POST", journal_payload)
        except Exception as e:
            logger.error(f"[F4] POST a /journals falló: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Error creando journal en Alegra: {str(e)}"
            )

        # ── VERIFY HTTP 200 BEFORE MODIFYING MongoDB ─────────────────────────
        if not journal_response.get("_verificado"):
            error_msg = journal_response.get("_error_verificacion", "Verificación fallida sin detalles")
            logger.error(f"[F4] Verificación de journal falló: {error_msg}")
            raise HTTPException(
                status_code=500,
                detail=f"Journal creado pero no verificado en Alegra: {error_msg}"
            )

        # Extract journal ID
        journal_id = journal_response.get("id")
        if not journal_id:
            logger.error(f"[F4] Alegra no retornó un ID válido: {journal_response}")
            raise HTTPException(status_code=500, detail="Alegra no retornó ID del journal")

        logger.info(f"[F4] ✅ Journal creado en Alegra: ID={journal_id}")

        # ── ONLY NOW: INSERT INTO nomina_registros (HTTP 200 CONFIRMED) ───────
        logger.info("[F4] Insertando en nomina_registros...")

        empleados_hash = calcular_hash_empleados(payload.empleados)

        nomina_doc = {
            "id": f"NOMINA-{journal_id}",
            "mes": payload.mes,
            "empleados": [
                {
                    "nombre": emp.nombre,
                    "monto": emp.monto
                }
                for emp in payload.empleados
            ],
            "empleados_hash": empleados_hash,
            "total_nomina": total_nomina,
            "banco_pago": payload.banco_pago,
            "alegra_journal_id": journal_id,
            "observaciones": payload.observaciones or "",
            "fecha_registro": datetime.now(timezone.utc).isoformat(),
        }

        await db.nomina_registros.insert_one(nomina_doc)
        logger.info(f"[F4] Registro insertado en nomina_registros: {nomina_doc['id']}")

        # ── PUBLISH EVENT ────────────────────────────────────────────────────
        logger.info("[F4] Publicando evento nomina.registrada...")
        event_doc = {
            "event_type": "nomina.registrada",
            "mes": payload.mes,
            "num_empleados": len(payload.empleados),
            "total_nomina": total_nomina,
            "alegra_journal_id": journal_id,
            "banco_pago": payload.banco_pago,
            "fecha": datetime.now(timezone.utc).isoformat(),
        }

        await db.roddos_events.insert_one(event_doc)

        # ── POST-ACTION SYNC & CACHE INVALIDATION ───────────────────────────
        logger.info("[F4] Sincronizando con post_action_sync()...")
        try:
            await post_action_sync(
                "registrar_nomina",
                {"id": journal_id, "mes": payload.mes},
                journal_payload,
                db,
                current_user,
                metadata={
                    "mes": payload.mes,
                    "num_empleados": len(payload.empleados),
                    "total_nomina": total_nomina,
                }
            )
        except Exception as e:
            logger.warning(f"[F4] post_action_sync falló (no fatal): {str(e)[:100]}")

        logger.info("[F4] Invalidando CFO cache...")
        try:
            await invalidar_cache_cfo()
        except Exception as e:
            logger.warning(f"[F4] Error invalidando CFO cache: {str(e)[:100]}")

        # ── RESPONSE ──────────────────────────────────────────────────────────
        logger.info(f"[F4] ✅ Nómina {payload.mes} registrada exitosamente")

        return {
            "success": True,
            "journal_id": journal_id,
            "mes": payload.mes,
            "num_empleados": len(payload.empleados),
            "total_nomina": total_nomina,
            "banco_pago": payload.banco_pago,
            "mensaje": (
                f"✅ Nómina {payload.mes} registrada. "
                f"Journal en Alegra: {journal_id}. "
                f"Total: ${total_nomina:,.0f} ({len(payload.empleados)} empleados)"
            ),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[F4] Error registrando nómina: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error registrando nómina: {str(e)[:200]}")


@router.get("/historial")
async def get_nomina_historial(
    mes: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Get payroll history."""
    query = {}
    if mes:
        query["mes"] = mes

    registros = await db.nomina_registros.find(query).sort("mes", -1).to_list(100)

    return {
        "total": len(registros),
        "registros": [
            {
                "mes": r.get("mes"),
                "num_empleados": len(r.get("empleados", [])),
                "total_nomina": r.get("total_nomina"),
                "banco_pago": r.get("banco_pago"),
                "alegra_journal_id": r.get("alegra_journal_id"),
                "fecha_registro": r.get("fecha_registro"),
            }
            for r in registros
        ]
    }


@router.get("/plan-cuentas")
async def get_plan_cuentas(current_user=Depends(get_current_user)):
    """Get payroll account plan."""
    return {
        "cuentas": PLAN_CUENTAS_NOMINA,
        "bancos": BANCOS_PAGO_NOMINA,
        "default_cuenta_sueldos": DEFAULT_CUENTA_SUELDOS,
        "default_banco_pago": DEFAULT_BANCO_PAGO,
    }
