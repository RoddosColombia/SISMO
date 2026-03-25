"""Loanbook router — motorcycle payment plans (Contado/P39S/P52S/P78S)."""
import uuid
from datetime import datetime, timezone, date, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user, require_admin, log_action
from event_bus import emit_event
from services.crm_service import normalizar_telefono
from utils.loanbook_constants import (
    calcular_cuota_valor, dias_entre_cuotas, resumen_cuota,
    MULTIPLICADORES_PAGO, MODOS_VALIDOS,
)

router = APIRouter(prefix="/loanbook", tags=["loanbook"])

PLAN_CUOTAS = {"Contado": 0, "P39S": 39, "P52S": 52, "P78S": 78}


# ─── Loanbook Lookup Helper ──────────────────────────────────────────────────

async def find_loanbook(loan_id: str):
    """Find loanbook by id, codigo, or _id (ObjectId).

    Returns dict with synthesized 'id' and '_mongo_id' for updates, or None.
    '_mongo_id' is the original ObjectId — use for update_one filters.
    """
    loan = await db.loanbook.find_one({"id": loan_id})
    if not loan:
        loan = await db.loanbook.find_one({"codigo": loan_id})
    if not loan:
        try:
            from bson import ObjectId
            loan = await db.loanbook.find_one({"_id": ObjectId(loan_id)})
        except Exception:
            pass
    if loan:
        # Save _id as string for update_one filters
        loan["_oid"] = str(loan["_id"])
        if not loan.get("id"):
            loan["id"] = loan.get("codigo") or str(loan["_id"])
    return loan


def _mongo_filter(loan: dict) -> dict:
    """Build MongoDB filter from saved _oid for update_one calls."""
    from bson import ObjectId
    return {"_id": ObjectId(loan["_oid"])}


# ─── Mora Calculation Helper ───────────────────────────────────────────────────

def calcular_mora(fecha_vencimiento: str, mora_diaria: int = 2000) -> dict:
    """
    Calcular mora acumulada desde el día siguiente al vencimiento (jueves).

    Parámetros:
    - fecha_vencimiento: ISO date string (siempre es miércoles)
    - mora_diaria: COP por día de atraso (default: 2000 RODDOS)

    Retorna:
    {
        "dias_mora": número de días en atraso,
        "mora_total": dinero acumulado (días × mora_diaria)
    }

    Nota: La mora comienza el jueves (día siguiente al miércoles de vencimiento).
    Si hoy <= jueves, retorna 0 días y 0 mora.
    """
    try:
        if isinstance(fecha_vencimiento, str):
            fecha_vencimiento = datetime.fromisoformat(fecha_vencimiento).date()
        elif isinstance(fecha_vencimiento, datetime):
            fecha_vencimiento = fecha_vencimiento.date()

        # Día siguiente al vencimiento (jueves)
        inicio_mora = fecha_vencimiento + timedelta(days=1)
        hoy = date.today()

        if hoy <= inicio_mora:
            return {"dias_mora": 0, "mora_total": 0}

        dias_mora = (hoy - inicio_mora).days
        mora_total = dias_mora * mora_diaria

        return {"dias_mora": dias_mora, "mora_total": mora_total}
    except Exception as e:
        # Si hay error en cálculo, retorna 0
        import logging
        logging.error(f"Error calculando mora: {str(e)}")
        return {"dias_mora": 0, "mora_total": 0}


# ─── Models ───────────────────────────────────────────────────────────────────

class LoanCreate(BaseModel):
    factura_alegra_id: Optional[str] = None
    factura_numero: Optional[str] = None
    moto_id: Optional[str] = None
    moto_descripcion: Optional[str] = ""
    cliente_id: Optional[str] = None
    cliente_nombre: str
    cliente_nit: Optional[str] = ""
    tipo_identificacion: Optional[str] = "CC"  # CC | CE | PPT | PP
    cliente_telefono: Optional[str] = ""
    plan: str  # Contado | P39S | P52S | P78S
    fecha_factura: str
    precio_venta: float
    cuota_inicial: float
    valor_cuota: float        # cuota semanal base (manual entry)
    modo_pago: str = "semanal"  # semanal | quincenal | mensual
    cuota_base: Optional[float] = None  # override de base si difiere de valor_cuota
    # Retoma (moto usada como parte de pago)
    tiene_retoma: bool = False
    retoma_marca_modelo: Optional[str] = None
    retoma_vin: Optional[str] = None
    retoma_placa: Optional[str] = None
    retoma_valor: Optional[float] = None

class LoanEdit(BaseModel):
    """Fields editable on an existing loanbook (all optional)."""
    cliente_nombre: Optional[str] = None
    cliente_nit: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    cliente_telefono: Optional[str] = None
    moto_descripcion: Optional[str] = None
    moto_chasis: Optional[str] = None
    motor: Optional[str] = None
    placa: Optional[str] = None
    plan: Optional[str] = None
    modo_pago: Optional[str] = None
    valor_cuota: Optional[float] = None
    fecha_factura: Optional[str] = None

class EntregaRequest(BaseModel):
    fecha_entrega: str  # ISO date string
    # Optional fields to complete for datos_completos=False loanbooks
    plan: Optional[str] = None
    cuota_inicial: Optional[float] = None
    valor_cuota: Optional[float] = None
    cliente_nit: Optional[str] = None
    precio_venta: Optional[float] = None
    modo_pago: Optional[str] = None  # semanal | quincenal | mensual | contado
    # Moto confirmation fields
    motor: Optional[str] = None       # Engine number (required if null on moto)
    placa: Optional[str] = None       # License plate (optional)
    moto_chasis: Optional[str] = None # VIN confirmation/override

class PagoRequest(BaseModel):
    cuota_numero: int
    valor_pagado: float
    metodo_pago: str = "efectivo"  # efectivo | transferencia_bancolombia | nequi | etc
    notas: Optional[str] = ""
    factura_numero: Optional[str] = None  # Alegra invoice number to link

class GestionRequest(BaseModel):
    tipo: str        # llamada | mensaje | visita | otro
    canal: str       # telefono | whatsapp | presencial
    resultado: str   # contactó | no_contestó | prometió_pago | negó_pago | buzón
    notas: Optional[str] = ""
    ptp_fue_cumplido: Optional[bool] = None
    gestion_por: Optional[str] = None

class PtpRequest(BaseModel):
    ptp_fecha: str   # ISO date
    ptp_monto: float
    registrado_por: Optional[str] = None


class CuotaInicialRequest(BaseModel):
    valor: float
    metodo_pago: str = "efectivo"  # efectivo | transferencia_bancolombia | ... | retoma
    fecha: str  # ISO date string
    valor_retoma: Optional[float] = None  # Only if metodo_pago == "retoma"
    notas: Optional[str] = ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _first_wednesday(fecha_entrega: date) -> date:
    """Miércoles de la semana SIGUIENTE a la semana de entrega.

    Regla RODDOS: primer cobro = miércoles de la próxima semana calendario.
    Ejemplo: entrega jueves 5/mar (semana 2-8 mar)
    → siguiente semana = 9-15 mar → miércoles 11/mar.
    """
    # Ir al lunes de la semana siguiente
    dias_hasta_lunes = (7 - fecha_entrega.weekday()) % 7
    if dias_hasta_lunes == 0:
        dias_hasta_lunes = 7  # si es lunes, ir al lunes siguiente
    lunes_siguiente = fecha_entrega + timedelta(days=dias_hasta_lunes)
    # Miércoles de esa semana = lunes + 2
    return lunes_siguiente + timedelta(days=2)


def _update_overdue(cuotas: list, mora_diaria: int = 2000) -> list:
    """Mark pending cuotas as overdue if their due date has passed.
    Calculate accumulated mora for vencida cuotas.
    Cuotas with estado 'sin_fecha' or empty fecha_vencimiento are skipped.
    """
    today_str = date.today().isoformat()
    for c in cuotas:
        if c["estado"] == "pendiente" and c.get("fecha_vencimiento") and c["fecha_vencimiento"] <= today_str:
            c["estado"] = "vencida"

        # Calculate mora for vencida cuotas
        if c["estado"] == "vencida" and c.get("fecha_vencimiento"):
            mora_info = calcular_mora(c["fecha_vencimiento"], mora_diaria)
            c["dias_mora"] = mora_info["dias_mora"]
            c["mora_total"] = mora_info["mora_total"]
        else:
            # No mora for non-overdue or paid cuotas
            c["dias_mora"] = c.get("dias_mora", 0)
            c["mora_total"] = c.get("mora_total", 0)

    return cuotas


def _compute_stats(loan: dict, mora_diaria: int = 2000) -> dict:
    """Recompute aggregated stats from cuotas list, including mora calculations."""
    cuotas = _update_overdue(loan.get("cuotas", []), mora_diaria)
    pagadas = sum(1 for c in cuotas if c["estado"] == "pagada")
    vencidas = sum(1 for c in cuotas if c["estado"] == "vencida")
    total_cobrado = sum(c.get("valor_pagado", 0) for c in cuotas if c["estado"] in ("pagada", "parcial"))

    # Calcular deuda con mora incluida
    total_deuda = 0
    total_mora = 0
    for c in cuotas:
        if c["estado"] in ("pendiente", "vencida", "parcial"):
            valor_pendiente = c["valor"] - (c.get("valor_pagado", 0) or 0)
            total_deuda += valor_pendiente
            # Agregar mora para cuotas vencidas
            if c["estado"] == "vencida":
                mora = c.get("mora_total", 0)
                total_mora += mora
                total_deuda += mora

    # Determine overall estado
    num_cuotas = loan.get("num_cuotas", 0)
    total_cuotas = num_cuotas + 1  # +1 for cuota inicial
    if pagadas == total_cuotas:
        estado = "completado"
    elif vencidas > 0:
        estado = "mora"
    elif not loan.get("fecha_entrega") and loan.get("plan") != "Contado":
        estado = "pendiente_entrega"
    else:
        estado = "activo"
    return {
        "cuotas": cuotas,
        "num_cuotas_pagadas": pagadas,
        "num_cuotas_vencidas": vencidas,
        "total_cobrado": total_cobrado,
        "saldo_pendiente": total_deuda,
        "total_mora": total_mora,
        "estado": estado,
    }


async def _get_next_codigo():
    """Auto-generate loan code like LB-2026-001."""
    year = datetime.now(timezone.utc).year
    count = await db.loanbook.count_documents({}) + 1
    return f"LB-{year}-{str(count).zfill(4)}"


# ─── Default plan catalog (seeded on first read) ─────────────────────────────

CATALOGO_DEFAULT = [
    {
        "plan": "P39S", "modo_pago": "semanal",
        "cuotas_semanal": 39, "cuotas_quincenal": 20, "cuotas_mensual": 9,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Raider 125": {"precio_venta": 7_800_000, "valor_cuota_semanal": 210_000},
            "Sport 100":  {"precio_venta": 5_750_000, "valor_cuota_semanal": 175_000},
        },
    },
    {
        "plan": "P52S", "modo_pago": "semanal",
        "cuotas_semanal": 52, "cuotas_quincenal": 26, "cuotas_mensual": 12,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Raider 125": {"precio_venta": 7_800_000, "valor_cuota_semanal": 179_900},
            "Sport 100":  {"precio_venta": 5_750_000, "valor_cuota_semanal": 160_000},
        },
    },
    {
        "plan": "P78S", "modo_pago": "semanal",
        "cuotas_semanal": 78, "cuotas_quincenal": 39, "cuotas_mensual": 18,
        "multiplicadores": {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4},
        "mora_diaria": 2000,
        "modelos": {
            "Raider 125": {"precio_venta": 7_800_000, "valor_cuota_semanal": 149_900},
            "Sport 100":  {"precio_venta": 5_750_000, "valor_cuota_semanal": 130_000},
        },
    },
    {
        "plan": "Contado", "modo_pago": "contado",
        "cuotas_semanal": 0, "cuotas_quincenal": 0, "cuotas_mensual": 0,
        "mora_diaria": 2000,
        "modelos": {},
    },
]


# ─── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/catalogo-planes")
async def get_catalogo_planes(current_user=Depends(get_current_user)):
    """Return plan catalog from MongoDB. Upserts default values if missing — never deletes existing."""
    planes = await db.catalogo_planes.find({}, {"_id": 0}).to_list(20)
    # Upsert missing or outdated plans (never delete existing data)
    needs_seed = not planes or not any(p.get("modelos") for p in planes)
    if needs_seed:
        for p in CATALOGO_DEFAULT:
            await db.catalogo_planes.update_one(
                {"plan": p["plan"]},
                {"$set": p},
                upsert=True,
            )
        planes = await db.catalogo_planes.find({}, {"_id": 0}).to_list(20)
    return planes


@router.post("/admin/reset-catalogo")
async def reset_catalogo_planes(
    current_user=Depends(require_admin),
):
    """ADMIN ONLY: Force reset catalogo_planes to default values.

    Use case: MongoDB corruption or merge issues that prevent auto-seed.
    Deletes ALL existing documents and re-inserts clean seed data.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Count existing documents
        existing_count = await db.catalogo_planes.count_documents({})
        logger.warning(f"[ADMIN] Reset catalogo_planes: deleting {existing_count} existing documents")

        # Delete ALL documents
        delete_result = await db.catalogo_planes.delete_many({})
        logger.warning(f"[ADMIN] Deleted {delete_result.deleted_count} documents from catalogo_planes")

        # Insert fresh CATALOGO_DEFAULT
        insert_count = 0
        for plan_data in CATALOGO_DEFAULT:
            result = await db.catalogo_planes.insert_one({**plan_data})
            insert_count += 1
            logger.warning(f"[ADMIN] Inserted plan {plan_data.get('plan')}: {result.inserted_id}")

        # Verify insertion
        final_count = await db.catalogo_planes.count_documents({})
        planes = await db.catalogo_planes.find({}, {"_id": 0}).to_list(20)

        logger.warning(f"[ADMIN] Reset complete: {final_count} plans in catalogo_planes")

        return {
            "status": "success",
            "deleted": delete_result.deleted_count,
            "inserted": insert_count,
            "total_in_db": final_count,
            "planes": planes,
            "message": f"✅ Catalogo reset complete. {insert_count} planes inserted."
        }
    except Exception as e:
        logger.error(f"[ADMIN] Reset failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Reset failed: {str(e)}")


@router.post("/admin/migrar-loanbooks-legacy")
async def migrar_loanbooks_legacy(
    current_user=Depends(require_admin),
):
    """ADMIN ONLY: Migrate legacy loanbooks (LB-2026-0001 to LB-2026-0010) with incomplete data.

    SIMPLIFIED: FORCE update all loanbooks with missing precio_venta or incomplete fields.
    """
    import logging
    logger = logging.getLogger(__name__)

    try:
        # Find loanbooks with codigo starting with LB-2026-00
        all_lbs = await db.loanbook.find({}).to_list(2000)
        legacy_lbs = [lb for lb in all_lbs if str(lb.get("codigo", "")).startswith("LB-2026-00")]

        logger.warning(f"[ADMIN] Migration: Found {len(legacy_lbs)} potential legacy loanbooks")

        updated_lbs = []

        for lb in legacy_lbs:
            updates = {}
            lb_codigo = lb.get("codigo", "UNKNOWN")

            # 1. ALWAYS calculate precio_venta from cuotas if price is 0/null
            if not lb.get("precio_venta") or lb.get("precio_venta") == 0:
                cuotas = lb.get("cuotas", [])
                cuota_inicial = lb.get("cuota_inicial", 0)
                cuotas_ordinarias = [c for c in cuotas if c.get("numero", 0) > 0]

                if cuotas_ordinarias:
                    valor_cuota = cuotas_ordinarias[0].get("valor", 0)
                    num_cuotas = len(cuotas_ordinarias)
                    precio_venta = (num_cuotas * valor_cuota) + cuota_inicial
                    updates["precio_venta"] = precio_venta
                    updates["num_cuotas"] = num_cuotas
                    updates["valor_cuota"] = valor_cuota

            # 2. ALWAYS set missing fields (even if they exist but empty)
            updates["tipo_id"] = lb.get("tipo_id") or "CC"
            updates["cliente_telefono"] = lb.get("cliente_telefono") or ""
            updates["moto_placa"] = lb.get("moto_placa") or ""
            updates["moto_motor"] = lb.get("moto_motor") or ""

            # 3. ALWAYS update by codigo (legacy loanbooks don't have reliable id)
            result = await db.loanbook.update_one(
                {"codigo": lb_codigo},
                {"$set": updates}
            )

            if result.matched_count > 0:
                logger.warning(f"[ADMIN] {lb_codigo}: Updated {len(updates)} fields (matched={result.matched_count}, modified={result.modified_count})")
                updated_lbs.append({
                    "codigo": lb_codigo,
                    "precio_venta_calculado": updates.get("precio_venta", lb.get("precio_venta")),
                    "campos_agregados": list(updates.keys())
                })

        logger.warning(f"[ADMIN] Migration complete: {len(updated_lbs)}/{len(legacy_lbs)} processed")

        return {
            "status": "success",
            "total_found": len(legacy_lbs),
            "updated": len(updated_lbs),
            "updated_loanbooks": updated_lbs,
            "message": f"Migración completada. {len(updated_lbs)} loanbooks procesados."
        }

    except Exception as e:
        logger.error(f"[ADMIN] Migration failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Migration failed: {str(e)}")


@router.get("/stats")
async def get_stats(current_user=Depends(get_current_user)):
    all_loans = await db.loanbook.find({}, {"_id": 0}).to_list(2000)
    total = len(all_loans)
    activos = sum(1 for l in all_loans if l["estado"] in ("activo", "mora"))
    en_mora = sum(1 for l in all_loans if l["estado"] == "mora")
    completados = sum(1 for l in all_loans if l["estado"] == "completado")
    pendiente_entrega = sum(1 for l in all_loans if l["estado"] == "pendiente_entrega")
    total_cartera = sum(l.get("saldo_pendiente", 0) for l in all_loans)
    total_cobrado = sum(l.get("total_cobrado", 0) for l in all_loans)
    # Cuotas due this week
    today = date.today()
    week_start = today - timedelta(days=today.weekday())
    week_end = week_start + timedelta(days=6)
    cuotas_semana = 0
    valor_semana = 0.0
    for loan in all_loans:
        for c in loan.get("cuotas", []):
            fv = c.get("fecha_vencimiento", "")
            if week_start.isoformat() <= fv <= week_end.isoformat() and c["estado"] in ("pendiente", "vencida"):
                cuotas_semana += 1
                valor_semana += c.get("valor", 0)
    return {
        "total": total,
        "activo": activos,           # alias for frontend
        "activos": activos,
        "en_mora": en_mora,
        "completados": completados,
        "pendiente_entrega": pendiente_entrega,
        "total_cartera_activa": total_cartera,
        "total_cobrado_historico": total_cobrado,
        "cuotas_esta_semana": cuotas_semana,
        "valor_esta_semana": valor_semana,
    }


@router.get("")
async def get_loans(
    estado: Optional[str] = None,
    plan: Optional[str] = None,
    cliente: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    query = {}
    if estado:
        query["estado"] = estado
    if plan:
        query["plan"] = plan
    if cliente:
        query["cliente_nombre"] = {"$regex": cliente, "$options": "i"}
    loans = await db.loanbook.find(query).sort("created_at", -1).to_list(1000)
    # Refresh overdue status + ensure 'id' field exists for all docs
    result = []
    for loan in loans:
        loan["id"] = loan.get("id") or str(loan.get("_id", ""))
        loan.pop("_id", None)
        stats = _compute_stats(loan)
        loan.update(stats)
        result.append(loan)
    return result


@router.post("")
async def create_loan(req: LoanCreate, current_user=Depends(get_current_user)):
    if req.plan not in PLAN_CUOTAS:
        raise HTTPException(status_code=400, detail=f"Plan inválido. Opciones: {list(PLAN_CUOTAS.keys())}")

    # ── MUTEX R5: prevent double-sale for the same moto ───────────────────────
    if req.moto_id:
        existing_loan = await db.loanbook.find_one(
            {"moto_id": req.moto_id, "estado": {"$nin": ["completado"]}},
            {"_id": 0, "codigo": 1},
        )
        if existing_loan:
            raise HTTPException(
                status_code=400,
                detail=f"Esta moto ya tiene un crédito activo: {existing_loan['codigo']}",
            )
    # ─────────────────────────────────────────────────────────────────────────

    num_cuotas_semanal = PLAN_CUOTAS[req.plan]
    valor_financiado = req.precio_venta - req.cuota_inicial
    codigo = await _get_next_codigo()

    # ── modo_pago y cálculo de cuota ──────────────────────────────────────────
    modo_pago = req.modo_pago if req.modo_pago in MODOS_VALIDOS or req.modo_pago == "contado" else "semanal"
    cuota_base = int(req.cuota_base) if req.cuota_base else int(req.valor_cuota)
    cuota_valor_calculado = calcular_cuota_valor(cuota_base, modo_pago) if modo_pago != "contado" else 0

    # Adjust num_cuotas based on modo_pago
    if modo_pago == "contado" or req.plan == "Contado":
        num_cuotas = 0
    elif modo_pago == "semanal":
        num_cuotas = num_cuotas_semanal
    else:
        # Look up from catalogo_planes
        catalogo_plan = await db.catalogo_planes.find_one({"plan": req.plan}, {"_id": 0})
        cuotas_key = f"cuotas_{modo_pago}"
        if catalogo_plan and cuotas_key in catalogo_plan:
            num_cuotas = catalogo_plan[cuotas_key]
        else:
            CUOTAS_FALLBACK = {
                "quincenal": {"P39S": 20, "P52S": 26, "P78S": 39},
                "mensual":   {"P39S": 9,  "P52S": 12, "P78S": 18},
            }
            num_cuotas = CUOTAS_FALLBACK.get(modo_pago, {}).get(req.plan, num_cuotas_semanal)
    # ─────────────────────────────────────────────────────────────────────────

    # Initial cuota (cuota 0)
    cuotas = [{
        "numero": 0,
        "tipo": "inicial",
        "fecha_vencimiento": req.fecha_factura,
        "valor": req.cuota_inicial,
        "estado": "pendiente",
        "fecha_pago": None,
        "valor_pagado": 0.0,
        "alegra_payment_id": None,
        "comprobante": None,
        "notas": "",
    }]

    # For Contado: schedule = just cuota inicial covering full price
    if req.plan == "Contado":
        cuotas[0]["valor"] = req.precio_venta
        valor_financiado = 0
        num_cuotas = 0

    doc = {
        "id": str(uuid.uuid4()),
        "codigo": codigo,
        "factura_alegra_id": req.factura_alegra_id,
        "factura_numero": req.factura_numero,
        "moto_id": req.moto_id,
        "moto_descripcion": req.moto_descripcion,
        "cliente_id": req.cliente_id,
        "cliente_nombre": req.cliente_nombre,
        "cliente_nit": req.cliente_nit,
        "tipo_identificacion": req.tipo_identificacion or "CC",
        "cliente_telefono": normalizar_telefono(req.cliente_telefono or ""),
        "plan": req.plan,
        "fecha_factura": req.fecha_factura,
        "fecha_entrega": None,
        "fecha_primer_pago": None,
        "precio_venta": req.precio_venta,
        "cuota_inicial": req.cuota_inicial,
        "valor_financiado": valor_financiado,
        "num_cuotas": num_cuotas,
        "modo_pago": modo_pago,
        "cuota_base": cuota_base,
        "valor_cuota": cuota_valor_calculado,
        "cuota_valor": cuota_valor_calculado,   # alias de compatibilidad
        "cuotas": cuotas,
        "estado": "activo" if req.plan == "Contado" else "pendiente_entrega",
        "num_cuotas_pagadas": 0,
        "num_cuotas_vencidas": 0,
        "total_cobrado": 0.0,
        "saldo_pendiente": req.precio_venta if req.plan == "Contado" else valor_financiado,
        "ai_suggested": False,
        "tiene_retoma": req.tiene_retoma,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email"),
    }

    # ── Retoma: moto usada como parte de pago ──────────────────────────────
    retoma_inventario_id = None
    if req.tiene_retoma and req.retoma_valor and req.retoma_valor > 0:
        retoma_inventario_id = str(uuid.uuid4())
        retoma_moto = {
            "id": retoma_inventario_id,
            "marca": (req.retoma_marca_modelo or "").split(" ")[0] if req.retoma_marca_modelo else "Usada",
            "version": req.retoma_marca_modelo or "Retoma",
            "chasis": req.retoma_vin or None,
            "placa": req.retoma_placa or None,
            "motor": None,
            "costo": req.retoma_valor,
            "total": req.retoma_valor,
            "estado": "Disponible",
            "tipo": "usada",
            "origen": "retoma",
            "loanbook_codigo": codigo,
            "propietario": "RODDOS SAS",
            "ubicacion": "BODEGA",
            "fecha_ingreso": date.today().isoformat(),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.inventario_motos.insert_one(retoma_moto)

        # Update loanbook doc with retoma info
        retoma_valor = req.retoma_valor
        valor_efectivo = max(0, req.cuota_inicial - retoma_valor)
        doc["retoma_valor"] = retoma_valor
        doc["retoma_descripcion"] = req.retoma_marca_modelo
        doc["retoma_inventario_id"] = retoma_inventario_id

        # Update cuota inicial with retoma breakdown
        cuota_0 = doc["cuotas"][0]
        cuota_0["valor_retoma"] = retoma_valor
        cuota_0["valor_efectivo"] = valor_efectivo
        if retoma_valor >= req.cuota_inicial:
            cuota_0["estado"] = "pagada"
            cuota_0["valor_pagado"] = req.cuota_inicial
            cuota_0["fecha_pago"] = date.today().isoformat()
            cuota_0["notas"] = f"Retoma: {req.retoma_marca_modelo} (${retoma_valor:,.0f})"
        elif retoma_valor > 0:
            cuota_0["estado"] = "parcial"
            cuota_0["valor_pagado"] = retoma_valor
            cuota_0["saldo_cuota"] = valor_efectivo
            cuota_0["notas"] = f"Retoma: {req.retoma_marca_modelo} (${retoma_valor:,.0f}) — Saldo efectivo: ${valor_efectivo:,.0f}"
    # ─────────────────────────────────────────────────────────────────────────

    await db.loanbook.insert_one(doc)
    doc.pop("_id", None)

    # Emit retoma event if applicable
    if retoma_inventario_id:
        await emit_event(db, "loanbook", "retoma.registrada", {
            "loanbook_id": doc["id"],
            "codigo": codigo,
            "cliente_nombre": req.cliente_nombre,
            "moto_retoma": {
                "marca_modelo": req.retoma_marca_modelo,
                "vin": req.retoma_vin,
                "placa": req.retoma_placa,
                "valor": req.retoma_valor,
            },
            "inventario_id_creado": retoma_inventario_id,
        })

    # Store pattern for AI learning
    await db.agent_memory.update_one(
        {"tipo": "loanbook_pattern", "plan": req.plan, "rango_precio": f"{(req.precio_venta // 500000) * 500000}"},
        {"$set": {
            "id": str(uuid.uuid4()),
            "tipo": "loanbook_pattern",
            "plan": req.plan,
            "precio_venta": req.precio_venta,
            "rango_precio": f"{(req.precio_venta // 500000) * 500000}",
            "cuota_inicial_tipica": req.cuota_inicial,
            "valor_cuota_tipico": req.valor_cuota,
            "ultima_ejecucion": datetime.now(timezone.utc).isoformat(),
        }, "$inc": {"frecuencia_count": 1}},
        upsert=True,
    )

    await log_action(current_user, "/loanbook", "POST", {"codigo": codigo, "plan": req.plan})
    return doc


@router.get("/{loan_id}")
async def get_loan(loan_id: str, current_user=Depends(get_current_user)):
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan de pago no encontrado")
    loan.pop("_id", None)
    stats = _compute_stats(loan)
    loan.update(stats)
    return loan


@router.post("/{loan_id}/recalcular")
async def recalcular_cuotas(loan_id: str, current_user=Depends(get_current_user)):
    """Recalculate cuotas schedule based on current modo_pago and plan.

    Preserves cuota inicial (numero=0) and any already-paid cuotas.
    Regenerates remaining cuotas with correct count, values, and Wednesday dates.
    """
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)

    plan = loan.get("plan", "")
    modo_pago = loan.get("modo_pago", "semanal")
    is_contado = modo_pago == "contado" or plan == "Contado"
    if is_contado:
        raise HTTPException(status_code=400, detail="Contado no tiene cuotas para recalcular")

    # Get correct num_cuotas from catalog
    catalogo_plan = await db.catalogo_planes.find_one({"plan": plan}, {"_id": 0})
    cuotas_key = f"cuotas_{modo_pago}"
    if catalogo_plan and cuotas_key in catalogo_plan:
        num_cuotas = catalogo_plan[cuotas_key]
    else:
        CUOTAS_FALLBACK = {
            "semanal":   {"P39S": 39, "P52S": 52, "P78S": 78},
            "quincenal": {"P39S": 20, "P52S": 26, "P78S": 39},
            "mensual":   {"P39S": 9,  "P52S": 12, "P78S": 18},
        }
        num_cuotas = CUOTAS_FALLBACK.get(modo_pago, {}).get(plan, 0)

    if num_cuotas == 0:
        raise HTTPException(status_code=400, detail=f"No se pudo determinar num_cuotas para {plan}/{modo_pago}")

    # Get cuota value and interval
    # Use valor_cuota directly if set (already includes multiplier for quincenal/mensual)
    # Only apply multiplier if we only have cuota_base (semanal base value)
    valor_cuota_stored = loan.get("valor_cuota") or loan.get("cuota_valor") or 0
    cuota_base_stored = loan.get("cuota_base") or 0
    if valor_cuota_stored:
        valor_cuota = int(valor_cuota_stored)
    elif cuota_base_stored:
        valor_cuota = calcular_cuota_valor(int(cuota_base_stored), modo_pago)
    else:
        valor_cuota = 0
    intervalo_dias = dias_entre_cuotas(modo_pago)

    # Determine first payment date
    fecha_primer_pago_str = loan.get("fecha_primer_pago")
    if fecha_primer_pago_str:
        fecha_primer_pago = date.fromisoformat(fecha_primer_pago_str)
    elif loan.get("fecha_entrega"):
        fecha_primer_pago = _first_wednesday(date.fromisoformat(loan["fecha_entrega"]))
    else:
        raise HTTPException(status_code=400, detail="No hay fecha de entrega ni primer pago para calcular cronograma")

    # Preserve cuota inicial and any paid cuotas
    old_cuotas = loan.get("cuotas", [])
    cuota_0 = next((c for c in old_cuotas if c.get("numero") == 0), None)
    paid_cuotas = {c["numero"]: c for c in old_cuotas if c.get("estado") in ("pagada", "parcial") and c.get("numero", 0) > 0}

    new_cuotas = []
    if cuota_0:
        new_cuotas.append(cuota_0)

    today_str = date.today().isoformat()
    for i in range(1, num_cuotas + 1):
        fecha_cuota = fecha_primer_pago + timedelta(days=intervalo_dias * (i - 1))
        if i in paid_cuotas:
            # Keep paid/partial cuota as-is but update fecha_vencimiento
            paid = paid_cuotas[i]
            paid["fecha_vencimiento"] = fecha_cuota.isoformat()
            paid["valor"] = valor_cuota
            new_cuotas.append(paid)
        else:
            new_cuotas.append({
                "numero": i, "tipo": modo_pago,
                "fecha_vencimiento": fecha_cuota.isoformat(),
                "valor": valor_cuota,
                "estado": "vencida" if fecha_cuota.isoformat() < today_str else "pendiente",
                "fecha_pago": None, "valor_pagado": 0.0,
                "alegra_payment_id": None, "comprobante": None, "notas": "",
            })

    valor_financiado = valor_cuota * num_cuotas
    saldo_pendiente = sum(
        (c["valor"] - (c.get("valor_pagado", 0) or 0))
        for c in new_cuotas if c.get("estado") in ("pendiente", "vencida", "parcial")
    )

    update = {
        "cuotas": new_cuotas,
        "num_cuotas": num_cuotas,
        "modo_pago": modo_pago,
        "valor_cuota": valor_cuota,
        "cuota_valor": valor_cuota,
        "valor_financiado": valor_financiado,
        "saldo_pendiente": saldo_pendiente,
        "fecha_primer_pago": fecha_primer_pago.isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": update})
    loan.update(update)
    stats = _compute_stats(loan)
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": stats})
    loan.update(stats)
    loan.pop("_id", None)

    await log_action(current_user, f"/loanbook/{loan_id}/recalcular", "POST", {
        "num_cuotas": num_cuotas, "valor_cuota": valor_cuota, "modo_pago": modo_pago,
    })

    return {
        **loan,
        "message": f"Recalculado: {num_cuotas} cuotas de ${valor_cuota:,.0f} ({modo_pago}) — Saldo: ${saldo_pendiente:,.0f}",
    }


@router.put("/{loan_id}")
async def edit_loan(loan_id: str, body: dict, current_user=Depends(get_current_user)):
    """Edit mutable fields on an existing loanbook (pre-delivery or active)."""
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)

    EDITABLE = {
        "cliente_nombre", "cliente_nit", "tipo_identificacion", "cliente_telefono",
        "moto_descripcion", "moto_chasis", "motor", "placa",
        "plan", "modo_pago", "valor_cuota", "fecha_factura", "fecha_primer_pago",
        "numero_factura_alegra",  # Optional Alegra invoice number
        # Retoma fields
        "tiene_retoma", "retoma_marca_modelo", "retoma_vin", "retoma_placa",
        "retoma_valor", "retoma_descripcion",
    }
    update_fields: dict = {k: v for k, v in body.items() if k in EDITABLE and v is not None}

    # Handle boolean tiene_retoma=False explicitly (v is not None but falsy)
    if "tiene_retoma" in body and body["tiene_retoma"] is False:
        update_fields["tiene_retoma"] = False

    if "plan" in update_fields and update_fields["plan"] in PLAN_CUOTAS:
        update_fields["num_cuotas"] = PLAN_CUOTAS[update_fields["plan"]]
    if "valor_cuota" in update_fields:
        update_fields["cuota_valor"] = int(update_fields["valor_cuota"])

    # Retoma cleanup: if disabling retoma, clear all retoma fields
    if update_fields.get("tiene_retoma") is False:
        update_fields["retoma_valor"] = 0
        update_fields["retoma_marca_modelo"] = None
        update_fields["retoma_vin"] = None
        update_fields["retoma_placa"] = None
        update_fields["retoma_descripcion"] = None

    # Sync retoma_descripcion from retoma_marca_modelo for consistency with Create flow
    if "retoma_marca_modelo" in update_fields and update_fields["retoma_marca_modelo"]:
        update_fields["retoma_descripcion"] = update_fields["retoma_marca_modelo"]

    if not update_fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    update_fields["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": update_fields})
    await log_action(current_user, f"/loanbook/{loan_id}", "PUT", update_fields)

    updated = await db.loanbook.find_one(_mongo_filter(loan))
    if not updated.get("id"):
        updated["id"] = updated.get("codigo") or str(updated["_id"])
    updated.pop("_id", None)
    stats = _compute_stats(updated)
    updated.update(stats)
    return updated


@router.post("/{loan_id}/cuota-inicial")
async def registrar_cuota_inicial(loan_id: str, req: CuotaInicialRequest, current_user=Depends(get_current_user)):
    """Register the initial payment (cuota 0) for a legacy loanbook that doesn't have one yet."""
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)

    # Validate cuota 0 doesn't already exist
    if any(c.get("numero") == 0 for c in loan.get("cuotas", [])):
        raise HTTPException(status_code=400, detail="Este loanbook ya tiene cuota inicial")

    cuota_0 = {
        "numero": 0,
        "tipo": "inicial",
        "fecha_vencimiento": req.fecha,
        "valor": req.valor,
        "estado": "pagada",
        "fecha_pago": req.fecha,
        "valor_pagado": req.valor,
        "canal_pago": req.metodo_pago,
        "notas": req.notas or "",
    }

    extra_set: dict = {
        "cuota_inicial": req.valor,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }

    if req.metodo_pago == "retoma" and req.valor_retoma:
        cuota_0["valor_retoma"] = req.valor_retoma
        cuota_0["notas"] = f"Retoma: ${req.valor_retoma:,.0f}"
        extra_set["retoma_valor"] = req.valor_retoma

    await db.loanbook.update_one(
        _mongo_filter(loan),
        {
            "$push": {"cuotas": {"$each": [cuota_0], "$position": 0}},
            "$set": extra_set,
            "$inc": {"num_cuotas_pagadas": 1},
        },
    )

    await log_action(current_user, f"/loanbook/{loan_id}/cuota-inicial", "POST", {
        "valor": req.valor, "metodo_pago": req.metodo_pago,
    })

    updated = await db.loanbook.find_one(_mongo_filter(loan))
    if not updated.get("id"):
        updated["id"] = updated.get("codigo") or str(updated["_id"])
    updated.pop("_id", None)
    stats = _compute_stats(updated)
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": stats})
    updated.update(stats)
    return updated


@router.put("/{loan_id}/entrega")
async def register_entrega(loan_id: str, req: EntregaRequest, current_user=Depends(get_current_user)):
    """Register delivery date → generate weekly installment schedule.
    Also accepts optional plan/cuota_inicial/valor_cuota/cedula to complete
    loanbooks created automatically from Alegra (datos_completos=False).
    """
    from routers.cfo import invalidar_cache_cfo

    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)
    if loan.get("fecha_entrega"):
        raise HTTPException(status_code=400, detail="La fecha de entrega ya fue registrada. Contacte al administrador para modificarla.")

    # Complete missing data if provided
    update_fields: dict = {}
    if req.plan and not loan.get("plan"):
        if req.plan not in PLAN_CUOTAS:
            raise HTTPException(status_code=400, detail=f"Plan inválido. Opciones: {list(PLAN_CUOTAS.keys())}")
        update_fields["plan"] = req.plan
        update_fields["num_cuotas"] = PLAN_CUOTAS[req.plan]
    if req.cuota_inicial is not None and not loan.get("cuota_inicial"):
        update_fields["cuota_inicial"] = req.cuota_inicial
    if req.valor_cuota is not None and not loan.get("valor_cuota"):
        update_fields["valor_cuota"] = req.valor_cuota
    if req.precio_venta is not None and not loan.get("precio_venta"):
        update_fields["precio_venta"] = req.precio_venta
    if req.cliente_nit and not loan.get("cliente_nit"):
        update_fields["cliente_nit"] = req.cliente_nit

    # Merge updates into loan object for processing
    loan.update(update_fields)

    # Override moto_chasis if provided in request
    if req.moto_chasis:
        loan["moto_chasis"] = req.moto_chasis

    plan = loan.get("plan", req.plan)
    if not plan:
        raise HTTPException(status_code=400, detail="Plan de crédito requerido para registrar entrega")

    # ── MUTEX R5: verify moto state before delivery ───────────────────────────
    # Check by moto_chasis (preferred) or moto_id
    chasis = loan.get("moto_chasis")
    moto_ref = None
    if chasis:
        moto_ref = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0, "id": 1, "estado": 1})
    elif loan.get("moto_id"):
        moto_ref = await db.inventario_motos.find_one({"id": loan["moto_id"]}, {"_id": 0, "id": 1, "estado": 1})

    if moto_ref:
        estado_moto = (moto_ref.get("estado") or "").lower()
        if estado_moto not in ("vendida", "disponible"):
            raise HTTPException(
                status_code=400,
                detail=f"Moto no disponible para entrega. Estado actual: {moto_ref.get('estado')}",
            )
    # ─────────────────────────────────────────────────────────────────────────

    fecha_entrega = date.fromisoformat(req.fecha_entrega)

    # ── modo_pago: request overrides stored value ─────────────────────────────
    modo_pago = req.modo_pago or loan.get("modo_pago", "semanal")
    is_contado = modo_pago == "contado" or plan == "Contado"
    if is_contado:
        modo_pago = "contado"
    elif modo_pago not in MODOS_VALIDOS:
        modo_pago = "semanal"

    # ── num_cuotas: adjust based on modo_pago from catalog ──────────────────
    # Default from stored plan (semanal count)
    num_cuotas_semanal = loan.get("num_cuotas", 0) or PLAN_CUOTAS.get(plan, 0)
    if is_contado:
        num_cuotas = 0
    elif modo_pago == "semanal":
        num_cuotas = num_cuotas_semanal
    else:
        # Look up from catalogo_planes in MongoDB
        catalogo_plan = await db.catalogo_planes.find_one({"plan": plan}, {"_id": 0})
        cuotas_key = f"cuotas_{modo_pago}"
        if catalogo_plan and cuotas_key in catalogo_plan:
            num_cuotas = catalogo_plan[cuotas_key]
        else:
            # Fallback: P39S(20/9), P52S(26/12), P78S(39/18)
            CUOTAS_FALLBACK = {
                "quincenal": {"P39S": 20, "P52S": 26, "P78S": 39},
                "mensual":   {"P39S": 9,  "P52S": 12, "P78S": 18},
            }
            num_cuotas = CUOTAS_FALLBACK.get(modo_pago, {}).get(plan, num_cuotas_semanal)

    # For non-contado: calculate schedule with Wednesday rule
    fecha_primer_pago = None if is_contado else _first_wednesday(fecha_entrega)
    intervalo_dias = 0 if is_contado else dias_entre_cuotas(modo_pago)

    # cuota_base: siempre el valor semanal puro; recalcular cuota_valor con ceil
    cuota_base_stored = loan.get("cuota_base") or loan.get("valor_cuota") or loan.get("cuota_valor") or 0
    if is_contado:
        valor_cuota_final = 0
        valor_financiado = 0
    else:
        # Support both field names: valor_cuota (created via form) and cuota_valor (legacy/auto-created)
        valor_cuota_final = calcular_cuota_valor(int(cuota_base_stored), modo_pago)
        valor_financiado = loan.get("valor_financiado") or (valor_cuota_final * num_cuotas)
    # ─────────────────────────────────────────────────────────────────────────

    # Build cuotas schedule
    cuota_inicial_val = loan.get("cuota_inicial", 0)
    cuotas_base = loan.get("cuotas") or []
    # Keep existing cuota inicial if present, else create it
    cuota_0 = next((c for c in cuotas_base if c.get("tipo") == "inicial"), None)
    cuotas = []
    if cuota_0:
        cuotas.append(cuota_0)
    elif cuota_inicial_val > 0:
        cuotas.append({
            "numero": 0, "tipo": "inicial",
            "fecha_vencimiento": loan.get("fecha_factura", req.fecha_entrega),
            "valor": cuota_inicial_val,
            "estado": "pendiente", "fecha_pago": None,
            "valor_pagado": 0.0, "alegra_payment_id": None,
            "comprobante": None, "notas": "",
        })

    # Contado: no installment cuotas; credit plans: generate full schedule
    if not is_contado:
        for i in range(1, num_cuotas + 1):
            fecha_cuota = fecha_primer_pago + timedelta(days=intervalo_dias * (i - 1))
            cuotas.append({
                "numero": i, "tipo": modo_pago,
                "fecha_vencimiento": fecha_cuota.isoformat(),
                "valor": valor_cuota_final,
                "estado": "vencida" if fecha_cuota.isoformat() < date.today().isoformat() else "pendiente",
                "fecha_pago": None, "valor_pagado": 0.0,
                "alegra_payment_id": None, "comprobante": None, "notas": "",
            })

    # For contado, mark as completado immediately (single payment already covers total)
    estado_final = "completado" if is_contado else "activo"

    update: dict = {
        **update_fields,
        "fecha_entrega": req.fecha_entrega,
        "fecha_primer_pago": fecha_primer_pago.isoformat() if fecha_primer_pago else None,
        "modo_pago": modo_pago,
        "num_cuotas": num_cuotas,
        "cuota_base": int(cuota_base_stored),
        "valor_cuota": valor_cuota_final,
        "cuota_valor": valor_cuota_final,   # alias de compatibilidad
        "valor_financiado": valor_financiado,
        "cuotas": cuotas,
        "estado": estado_final,
        "datos_completos": True,
        "campos_pendientes": [],
        "saldo_pendiente": valor_financiado,
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    # Store moto confirmation fields if provided
    if req.moto_chasis:
        update["moto_chasis"] = req.moto_chasis
    if req.motor:
        update["motor"] = req.motor
    if req.placa:
        update["placa"] = req.placa
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": update})
    loan.update(update)
    stats = _compute_stats(loan)
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": stats})
    loan.update(stats)
    loan.pop("_id", None)

    # Update moto status to "Entregada" + motor/placa if provided
    now_iso = datetime.now(timezone.utc).isoformat()
    moto_update: dict = {"estado": "Entregada", "fecha_entrega": req.fecha_entrega, "updated_at": now_iso}
    if req.motor:
        moto_update["motor"] = req.motor
    if req.placa:
        moto_update["placa"] = req.placa
    if chasis:
        await db.inventario_motos.update_one(
            {"chasis": chasis},
            {"$set": moto_update},
        )
    elif loan.get("moto_id"):
        await db.inventario_motos.update_one(
            {"id": loan["moto_id"]},
            {"$set": moto_update},
        )

    # Emit loanbook.activado event
    await emit_event(db, "loanbook", "loanbook.activado", {
        "loanbook_id": loan_id,
        "codigo": loan["codigo"],
        "cliente_nombre": loan["cliente_nombre"],
        "fecha_entrega": req.fecha_entrega,
        "primera_cuota": fecha_primer_pago.isoformat() if fecha_primer_pago else None,
        "num_cuotas": num_cuotas,
        "modo_pago": modo_pago,
    })

    # Emit moto.entregada event
    await emit_event(db, "loanbook", "moto.entregada", {
        "loanbook_id": loan_id,
        "codigo": loan["codigo"],
        "cliente_nombre": loan["cliente_nombre"],
        "moto_descripcion": loan.get("moto_descripcion", ""),
        "moto_chasis": chasis or loan.get("moto_chasis", ""),
        "motor": req.motor or loan.get("motor", ""),
        "placa": req.placa or loan.get("placa", ""),
        "fecha_entrega": req.fecha_entrega,
    })

    # Invalidate CFO cache
    await invalidar_cache_cfo()

    await log_action(current_user, f"/loanbook/{loan_id}/entrega", "PUT", {"fecha_entrega": req.fecha_entrega, "modo_pago": modo_pago})

    if is_contado:
        return {
            **loan,
            "primera_cuota_fecha": None,
            "message": f"Loanbook completado — Pago de contado registrado.",
        }
    return {
        **loan,
        "primera_cuota_fecha": fecha_primer_pago.isoformat(),
        "message": (
            f"Loanbook activado — Primera cuota: {fecha_primer_pago.strftime('%d/%m/%Y')} (miércoles) | "
            + resumen_cuota(int(cuota_base_stored), modo_pago)
        ),
    }


@router.put("/{loan_id}/cuota/{cuota_num}")
async def update_cuota(loan_id: str, cuota_num: int, body: dict, current_user=Depends(get_current_user)):
    """Edit cuota value or notes (AI verification checkpoint)."""
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)
    cuotas = loan.get("cuotas", [])
    cuota = next((c for c in cuotas if c["numero"] == cuota_num), None)
    if not cuota:
        raise HTTPException(status_code=404, detail=f"Cuota {cuota_num} no encontrada")

    # Allow editing: valor, notas, fecha_vencimiento (if not paid)
    if cuota["estado"] == "pagada":
        raise HTTPException(status_code=400, detail="No se puede editar una cuota ya pagada")
    for field in ("valor", "notas", "fecha_vencimiento"):
        if field in body:
            cuota[field] = body[field]

    # If editing valor, also update loan-level valor_cuota for consistency
    if "valor" in body and cuota_num > 0:
        loan["valor_cuota"] = body["valor"]

    await db.loanbook.update_one(
        _mongo_filter(loan),
        {"$set": {"cuotas": cuotas, "valor_cuota": loan.get("valor_cuota"), "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    loan["cuotas"] = cuotas
    stats = _compute_stats(loan)
    loan.update(stats)
    loan.pop("_id", None)
    return loan


@router.post("/{loan_id}/pago")
async def register_pago(loan_id: str, req: PagoRequest, current_user=Depends(get_current_user)):
    """Register payment for a cuota + create payment in Alegra."""
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail=f"Plan de crédito no encontrado (ID: {loan_id})")
    loan.pop("_id", None)

    # Allow payments for pendiente_entrega, activo, mora — all operational states
    is_cuota_inicial = req.cuota_numero == 0
    if loan.get("estado") not in ("activo", "mora", "pendiente_entrega"):
        raise HTTPException(
            status_code=400,
            detail=f"No puedes registrar el pago: el crédito está en estado '{loan.get('estado')}'.",
        )

    cuotas = loan.get("cuotas", [])
    cuota = next((c for c in cuotas if c["numero"] == req.cuota_numero), None)
    if not cuota:
        raise HTTPException(status_code=404, detail=f"Cuota {req.cuota_numero} no encontrada en {loan.get('codigo','')}")
    if cuota["estado"] == "pagada":
        raise HTTPException(
            status_code=400,
            detail=f"La cuota {req.cuota_numero} ya fue registrada (pagada el {cuota.get('fecha_pago','?')}).",
        )

    # If factura_numero provided, try to link to Alegra invoice
    service = AlegraService(db)
    if req.factura_numero and not loan.get("factura_alegra_id"):
        try:
            invoices = await service.request_with_verify(
                f"invoices?numberTemplate={req.factura_numero}", "GET", None
            )
            inv_list = invoices if isinstance(invoices, list) else invoices.get("data", [])
            if inv_list:
                alegra_id = str(inv_list[0].get("id", ""))
                if alegra_id:
                    await db.loanbook.update_one(
                        _mongo_filter(loan),
                        {"$set": {"factura_alegra_id": alegra_id, "factura_numero": req.factura_numero}},
                    )
                    loan["factura_alegra_id"] = alegra_id
                    loan["factura_numero"] = req.factura_numero
        except Exception:
            pass  # Continue — user can still register pago without linking

    # Create payment in Alegra (skip for cuota inicial or when no factura_alegra_id)
    alegra_payment_id = None
    comprobante_num = f"COMP-{loan['codigo']}-C{str(req.cuota_numero).zfill(3)}"
    has_alegra = bool(loan.get("factura_alegra_id"))

    if is_cuota_inicial or not has_alegra:
        # Cuota inicial or manual loanbook — register locally without Alegra
        alegra_payment_id = None
    else:
        # Ordinary cuota with Alegra invoice — register in Alegra
        try:
            payment_payload = {
                "date": date.today().isoformat(),
                "invoices": [{"id": loan["factura_alegra_id"], "amount": req.valor_pagado}],
                "paymentMethod": req.metodo_pago,
                "observations": f"{loan['codigo']} — Cuota {req.cuota_numero}/{loan['num_cuotas']} — {req.metodo_pago}",
            }

            alegra_res = await service.request_with_verify("payments", "POST", payment_payload)

            if not alegra_res.get("_verificado"):
                raise HTTPException(
                    status_code=500,
                    detail="VERIFICACIÓN FALLIDA: Alegra respondió pero no se pudo confirmar el registro. No se actualizará el loanbook hasta verificar manualmente."
                )

            alegra_payment_id = alegra_res.get("id") or alegra_res.get("_verificacion_id")

            if not alegra_payment_id:
                raise HTTPException(
                    status_code=500,
                    detail="Alegra registró el pago pero no retornó un ID. Verifica manualmente en Alegra antes de continuar."
                )

        except HTTPException:
            raise

        except Exception as e:
            raise HTTPException(
                status_code=503,
                detail=f"No se pudo conectar con Alegra: {str(e)}. Verifica tu conexión e intenta nuevamente."
            )

    # Update cuota — determine if full or partial payment
    abonado_previo = cuota.get("valor_pagado", 0) or 0
    total_abonado = abonado_previo + req.valor_pagado
    valor_cuota = cuota.get("valor", 0)
    if total_abonado >= valor_cuota:
        cuota["estado"] = "pagada"
        cuota["valor_pagado"] = total_abonado
    else:
        cuota["estado"] = "parcial"
        cuota["valor_pagado"] = total_abonado
        cuota["saldo_cuota"] = valor_cuota - total_abonado
    cuota["fecha_pago"] = date.today().isoformat()
    cuota["alegra_payment_id"] = str(alegra_payment_id) if alegra_payment_id else None
    cuota["comprobante"] = comprobante_num
    cuota["notas"] = req.notas or ""

    # Save payment record — use .get() for optional fields to prevent KeyError
    await db.cartera_pagos.insert_one({
        "id": str(uuid.uuid4()),
        "loanbook_id": loan_id,
        "codigo_loan": loan.get("codigo", ""),
        "cuota_numero": req.cuota_numero,
        "cliente_id": loan.get("cliente_id", ""),
        "cliente_nombre": loan.get("cliente_nombre", ""),
        "plan": loan.get("plan", ""),
        "fecha_pago": date.today().isoformat(),
        "valor_pagado": req.valor_pagado,
        "metodo_pago": req.metodo_pago,
        "registrado_por": current_user.get("email"),
        "alegra_payment_id": str(alegra_payment_id) if alegra_payment_id else None,
        "comprobante": comprobante_num,
        "notas": req.notas or "",
        "created_at": datetime.now(timezone.utc).isoformat(),
    })

    # Update loanbook stats
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": {"cuotas": cuotas, "updated_at": datetime.now(timezone.utc).isoformat()}})
    loan["cuotas"] = cuotas
    stats = _compute_stats(loan)
    await db.loanbook.update_one(_mongo_filter(loan), {"$set": stats})
    loan.update(stats)
    loan.pop("_id", None)

    # HOTFIX 21.1 FIX #2: Invalidate CFO cache so dashboard recomputes fresh data
    from routers.cfo import invalidar_cache_cfo
    await invalidar_cache_cfo()

    await log_action(current_user, f"/loanbook/{loan_id}/pago", "POST", {
        "cuota": req.cuota_numero, "valor": req.valor_pagado, "comprobante": comprobante_num
    })

    # Emit event to bus
    await emit_event(db, "loanbook", "pago.cuota.registrado", {
        "loanbook_id": loan_id,
        "codigo": loan["codigo"],
        "cuota_numero": req.cuota_numero,
        "total_cuotas": loan["num_cuotas"],
        "valor_pagado": req.valor_pagado,
        "metodo_pago": req.metodo_pago,
        "cliente_nombre": loan["cliente_nombre"],
        "comprobante": comprobante_num,
        "registrado_por": current_user.get("email"),
    })

    return {**loan, "comprobante": comprobante_num, "alegra_payment_id": alegra_payment_id}


# ─── BUILD 3 Endpoints ────────────────────────────────────────────────────────

@router.post("/{loan_id}/gestion")
async def register_gestion(loan_id: str, req: GestionRequest, current_user=Depends(get_current_user)):
    """Registra una gestión de cobro → append a gestiones[] + update CRM."""
    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)

    now_iso = datetime.now(timezone.utc).isoformat()
    gestion = {
        "id":              str(uuid.uuid4()),
        "fecha":           now_iso,
        "tipo":            req.tipo,
        "canal":           req.canal,
        "resultado":       req.resultado,
        "notas":           req.notas or "",
        "ptp_fue_cumplido": req.ptp_fue_cumplido,
        "gestion_por":     req.gestion_por or current_user.get("email"),
    }

    await db.loanbook.update_one(
        _mongo_filter(loan),
        {"$push": {"gestiones": gestion}, "$set": {"updated_at": now_iso}},
    )

    # Actualizar ultima_interaccion en CRM
    crm_filter = (
        {"id": loan["cliente_id"]} if loan.get("cliente_id")
        else {"telefono_principal": loan.get("cliente_telefono", "")}
    )
    await db.crm_clientes.update_one(
        crm_filter,
        {"$set": {"ultima_interaccion": now_iso, "updated_at": now_iso}},
    )

    await log_action(current_user, f"/loanbook/{loan_id}/gestion", "POST",
                     {"resultado": req.resultado, "canal": req.canal})
    return {"id": loan_id, "gestion": gestion, "message": "Gestión registrada"}


@router.post("/{loan_id}/ptp")
async def register_ptp(loan_id: str, req: PtpRequest, current_user=Depends(get_current_user)):
    """Registra un compromiso de pago (PTP) + emite evento al bus."""
    from services.shared_state import emit_state_change

    loan = await find_loanbook(loan_id)
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    loan.pop("_id", None)

    now_iso = datetime.now(timezone.utc).isoformat()
    await db.loanbook.update_one(
        _mongo_filter(loan),
        {"$set": {
            "ptp_fecha":          req.ptp_fecha,
            "ptp_monto":          req.ptp_monto,
            "ptp_registrado_por": req.registrado_por or current_user.get("email"),
            "updated_at":         now_iso,
        }},
    )

    await emit_state_change(
        db, "ptp.registrado", loan_id, "ptp_activo", current_user.get("email"),
        {"ptp_fecha": req.ptp_fecha, "ptp_monto": req.ptp_monto,
         "codigo": loan.get("codigo")},
    )

    await log_action(current_user, f"/loanbook/{loan_id}/ptp", "POST",
                     {"ptp_fecha": req.ptp_fecha, "ptp_monto": req.ptp_monto})
    return {
        "id":        loan_id,
        "ptp_fecha": req.ptp_fecha,
        "ptp_monto": req.ptp_monto,
        "message":   "PTP registrado",
    }


@router.get("/{loan_id}/snapshot")
async def get_snapshot(loan_id: str, current_user=Depends(get_current_user)):
    """Snapshot del loanbook desde shared_state (caché TTL 30 s)."""
    from services.shared_state import get_loanbook_snapshot

    snapshot = await get_loanbook_snapshot(db, loan_id)
    if not snapshot:
        raise HTTPException(status_code=404, detail="Loanbook no encontrado")
    return snapshot


# ── Direct bulk-insert endpoint (bypasses chat agent entirely) ─────────────

class CargaMasivaRequest(BaseModel):
    loanbooks: list
    dry_run: bool = False


@router.post("/carga-masiva")
async def carga_masiva_loanbooks(
    req: CargaMasivaRequest,
    current_user=Depends(get_current_user),
):
    """Inserta o actualiza loanbooks en lote sin pasar por el agente de chat.

    Útil para llamadas directas desde la Shell de Render, scripts de migración
    o cualquier herramienta externa que no use el flujo de confirmación del chat.

    Payload:
        {
          "loanbooks": [ { ...campos... }, ... ],
          "dry_run": false          # true → simula sin escribir en DB
        }

    Campos por loanbook:
        cliente_nombre, moto_chasis, plan (P26S|P39S|P52S|P78S|Contado),
        modo_pago (semanal|quincenal|mensual), cuota_base (int, COP),
        precio_venta, cuota_inicial, fecha_factura (ISO date),
        fecha_entrega (ISO date, opcional), cuotas_pagadas (int, opcional).
        Opcionales: cliente_nit, cliente_telefono, moto_descripcion.

    Returns el mismo resultado que cargar_loanbooks_lote del agente.
    """
    if not req.loanbooks:
        raise HTTPException(
            status_code=400,
            detail="Se requiere 'loanbooks' con al menos un registro.",
        )
    if len(req.loanbooks) > 500:
        raise HTTPException(
            status_code=400,
            detail="Máximo 500 loanbooks por lote. Divide el archivo y vuelve a intentarlo.",
        )

    # Inline import to avoid circular dependency (ai_chat imports nothing from loanbook)
    from ai_chat import execute_chat_action

    payload = {"loanbooks": req.loanbooks}
    if req.dry_run:
        payload["dry_run"] = True

    try:
        return await execute_chat_action(
            "cargar_loanbooks_lote", payload, db, current_user
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Error en carga masiva de loanbooks: {exc}",
        )

