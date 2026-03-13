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

router = APIRouter(prefix="/loanbook", tags=["loanbook"])

PLAN_CUOTAS = {"Contado": 0, "P39S": 39, "P52S": 52, "P78S": 78}


# ─── Models ───────────────────────────────────────────────────────────────────

class LoanCreate(BaseModel):
    factura_alegra_id: Optional[str] = None
    factura_numero: Optional[str] = None
    moto_id: Optional[str] = None
    moto_descripcion: Optional[str] = ""
    cliente_id: Optional[str] = None
    cliente_nombre: str
    cliente_nit: Optional[str] = ""
    cliente_telefono: Optional[str] = ""
    plan: str  # Contado | P39S | P52S | P78S
    fecha_factura: str
    precio_venta: float
    cuota_inicial: float
    valor_cuota: float  # weekly installment value (manual entry)

class EntregaRequest(BaseModel):
    fecha_entrega: str  # ISO date string

class PagoRequest(BaseModel):
    cuota_numero: int
    valor_pagado: float
    metodo_pago: str = "efectivo"  # efectivo | transferencia | tarjeta
    notas: Optional[str] = ""


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _first_wednesday(fecha_entrega: date) -> date:
    """Return the first Wednesday >= (fecha_entrega + 7 days).

    Rule per RODDOS: 'fecha_entrega + 7 days → miércoles de esa semana'.
    - If target (fecha_entrega+7) is Mon or Tue → advance to Wednesday of same week.
    - If target is Wednesday → use it.
    - If target is Thu/Fri/Sat/Sun → advance to Wednesday of NEXT week.
    All RODDOS installments fall on Wednesdays without exception.
    """
    target = fecha_entrega + timedelta(days=7)
    wd = target.weekday()  # 0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun
    if wd == 2:
        return target
    elif wd < 2:          # Mon/Tue → Wednesday same week
        return target + timedelta(days=2 - wd)
    else:                 # Thu/Fri/Sat/Sun → Wednesday next week
        return target + timedelta(days=9 - wd)


def _update_overdue(cuotas: list) -> list:
    """Mark pending cuotas as overdue if their due date has passed.
    Cuotas with estado 'sin_fecha' or empty fecha_vencimiento are skipped.
    """
    today_str = date.today().isoformat()
    for c in cuotas:
        if c["estado"] == "pendiente" and c.get("fecha_vencimiento") and c["fecha_vencimiento"] <= today_str:
            c["estado"] = "vencida"
    return cuotas


def _compute_stats(loan: dict) -> dict:
    """Recompute aggregated stats from cuotas list."""
    cuotas = _update_overdue(loan.get("cuotas", []))
    pagadas = sum(1 for c in cuotas if c["estado"] == "pagada")
    vencidas = sum(1 for c in cuotas if c["estado"] == "vencida")
    total_cobrado = sum(c.get("valor_pagado", 0) for c in cuotas if c["estado"] == "pagada")
    total_deuda = sum(c["valor"] for c in cuotas if c["estado"] in ("pendiente", "vencida", "parcial"))
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
        "estado": estado,
    }


async def _get_next_codigo():
    """Auto-generate loan code like LB-2026-001."""
    year = datetime.now(timezone.utc).year
    count = await db.loanbook.count_documents({}) + 1
    return f"LB-{year}-{str(count).zfill(4)}"


# ─── Endpoints ────────────────────────────────────────────────────────────────

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
    loans = await db.loanbook.find(query, {"_id": 0}).sort("created_at", -1).to_list(1000)
    # Refresh overdue status
    result = []
    for loan in loans:
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

    num_cuotas = PLAN_CUOTAS[req.plan]
    valor_financiado = req.precio_venta - req.cuota_inicial
    codigo = await _get_next_codigo()

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
        "cliente_telefono": req.cliente_telefono,
        "plan": req.plan,
        "fecha_factura": req.fecha_factura,
        "fecha_entrega": None,
        "fecha_primer_pago": None,
        "precio_venta": req.precio_venta,
        "cuota_inicial": req.cuota_inicial,
        "valor_financiado": valor_financiado,
        "num_cuotas": num_cuotas,
        "valor_cuota": req.valor_cuota,
        "cuotas": cuotas,
        "estado": "activo" if req.plan == "Contado" else "pendiente_entrega",
        "num_cuotas_pagadas": 0,
        "num_cuotas_vencidas": 0,
        "total_cobrado": 0.0,
        "saldo_pendiente": req.precio_venta if req.plan == "Contado" else valor_financiado,
        "ai_suggested": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "created_by": current_user.get("email"),
    }
    await db.loanbook.insert_one(doc)
    doc.pop("_id", None)

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
    loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
    if not loan:
        raise HTTPException(status_code=404, detail="Plan de pago no encontrado")
    stats = _compute_stats(loan)
    loan.update(stats)
    return loan


@router.put("/{loan_id}/entrega")
async def register_entrega(loan_id: str, req: EntregaRequest, current_user=Depends(get_current_user)):
    """Register delivery date → generate weekly installment schedule."""
    loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    if loan["plan"] == "Contado":
        raise HTTPException(status_code=400, detail="Plan Contado no requiere fecha de entrega")
    if loan.get("fecha_entrega"):
        raise HTTPException(status_code=400, detail="La fecha de entrega ya fue registrada. Contacte al administrador para modificarla.")

    fecha_entrega = date.fromisoformat(req.fecha_entrega)

    # ── MUTEX R5: verify moto state before delivery ───────────────────────────
    if loan.get("moto_id"):
        moto = await db.inventario_motos.find_one({"id": loan["moto_id"]}, {"_id": 0})
        if moto:
            estado_moto = (moto.get("estado") or "").lower()
            if estado_moto != "vendida":
                raise HTTPException(
                    status_code=400,
                    detail=f"Moto no disponible para entrega. Estado actual: {moto.get('estado')}",
                )
            loanbook_id_moto = moto.get("loanbook_id")
            if loanbook_id_moto and loanbook_id_moto != loan_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"Esta moto ya está asignada a otro crédito: {loanbook_id_moto}",
                )
    # ─────────────────────────────────────────────────────────────────────────
    # RODDOS rule: first payment = first Wednesday >= (fecha_entrega + 7 days)
    fecha_primer_pago = _first_wednesday(fecha_entrega)
    num_cuotas = loan["num_cuotas"]
    valor_cuota = loan["valor_cuota"]

    # Keep cuota inicial (index 0), generate weekly cuotas 1..N (all Wednesdays)
    cuotas = [loan["cuotas"][0]]  # preserve cuota inicial
    for i in range(1, num_cuotas + 1):
        fecha_cuota = fecha_primer_pago + timedelta(weeks=i - 1)
        cuotas.append({
            "numero": i,
            "tipo": "semanal",
            "fecha_vencimiento": fecha_cuota.isoformat(),
            "valor": valor_cuota,
            "estado": "vencida" if fecha_cuota.isoformat() < date.today().isoformat() else "pendiente",
            "fecha_pago": None,
            "valor_pagado": 0.0,
            "alegra_payment_id": None,
            "comprobante": None,
            "notas": "",
        })

    update = {
        "fecha_entrega": req.fecha_entrega,
        "fecha_primer_pago": fecha_primer_pago.isoformat(),
        "cuotas": cuotas,
        "estado": "activo",
        "saldo_pendiente": loan["valor_financiado"],
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.loanbook.update_one({"id": loan_id}, {"$set": update})
    loan.update(update)
    stats = _compute_stats(loan)
    loan.update(stats)
    loan.pop("_id", None)

    # Update moto status to "Entregada" if moto_id available
    if loan.get("moto_id"):
        await db.inventario_motos.update_one(
            {"id": loan["moto_id"]},
            {"$set": {"estado": "Entregada", "fecha_entrega": req.fecha_entrega}},
        )

    # Emit loanbook.activado event
    await emit_event(db, "loanbook", "loanbook.activado", {
        "loanbook_id": loan_id,
        "codigo": loan["codigo"],
        "cliente_nombre": loan["cliente_nombre"],
        "fecha_entrega": req.fecha_entrega,
        "primera_cuota": fecha_primer_pago.isoformat(),
        "num_cuotas": num_cuotas,
    })

    await log_action(current_user, f"/loanbook/{loan_id}/entrega", "PUT", {"fecha_entrega": req.fecha_entrega})
    return {
        **loan,
        "primera_cuota_fecha": fecha_primer_pago.isoformat(),
        "message": f"Loanbook activado — Primera cuota: {fecha_primer_pago.strftime('%d/%m/%Y')} (miércoles)",
    }


@router.put("/{loan_id}/cuota/{cuota_num}")
async def update_cuota(loan_id: str, cuota_num: int, body: dict, current_user=Depends(get_current_user)):
    """Edit cuota value or notes (AI verification checkpoint)."""
    loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
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
        {"id": loan_id},
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
    loan = await db.loanbook.find_one({"id": loan_id}, {"_id": 0})
    if not loan:
        raise HTTPException(status_code=404, detail="Plan no encontrado")
    cuotas = loan.get("cuotas", [])
    cuota = next((c for c in cuotas if c["numero"] == req.cuota_numero), None)
    if not cuota:
        raise HTTPException(status_code=404, detail=f"Cuota {req.cuota_numero} no encontrada")
    if cuota["estado"] == "pagada":
        raise HTTPException(status_code=400, detail="Esta cuota ya está pagada")

    # Create payment in Alegra
    service = AlegraService(db)
    alegra_payment_id = None
    comprobante_num = f"COMP-{loan['codigo']}-C{str(req.cuota_numero).zfill(3)}"
    try:
        payment_payload = {
            "date": date.today().isoformat(),
            "invoices": [{"id": loan["factura_alegra_id"], "amount": req.valor_pagado}],
            "paymentMethod": req.metodo_pago,
            "observations": f"{loan['codigo']} — Cuota {req.cuota_numero}/{loan['num_cuotas']} — {req.metodo_pago}",
        }
        alegra_res = await service.request("payments", "POST", payment_payload)
        alegra_payment_id = alegra_res.get("id")
    except Exception as e:
        # Don't block if Alegra fails — record locally
        pass

    # Update cuota
    cuota["estado"] = "pagada"
    cuota["fecha_pago"] = date.today().isoformat()
    cuota["valor_pagado"] = req.valor_pagado
    cuota["alegra_payment_id"] = str(alegra_payment_id) if alegra_payment_id else None
    cuota["comprobante"] = comprobante_num
    cuota["notas"] = req.notas or ""

    # Save payment record
    await db.cartera_pagos.insert_one({
        "id": str(uuid.uuid4()),
        "loanbook_id": loan_id,
        "codigo_loan": loan["codigo"],
        "cuota_numero": req.cuota_numero,
        "cliente_id": loan["cliente_id"],
        "cliente_nombre": loan["cliente_nombre"],
        "plan": loan["plan"],
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
    await db.loanbook.update_one({"id": loan_id}, {"$set": {"cuotas": cuotas, "updated_at": datetime.now(timezone.utc).isoformat()}})
    loan["cuotas"] = cuotas
    stats = _compute_stats(loan)
    await db.loanbook.update_one({"id": loan_id}, {"$set": stats})
    loan.update(stats)
    loan.pop("_id", None)

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
