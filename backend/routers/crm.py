"""routers/crm.py — CRM endpoints: client list, 360° profile, edit, notes, gestiones."""
import uuid
from datetime import date, datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from database import db
from dependencies import get_current_user
from services.crm_service import registrar_gestion, agregar_nota, registrar_ptp, crear_acuerdo, actualizar_estado_acuerdo

router = APIRouter(prefix="/crm", tags=["crm"])


# ── Models ────────────────────────────────────────────────────────────────────

class DatosEditables(BaseModel):
    telefono_alternativo: Optional[str] = None
    direccion: Optional[str] = None
    barrio: Optional[str] = None
    ciudad: Optional[str] = None
    email: Optional[str] = None
    ocupacion: Optional[str] = None
    referencia_1: Optional[dict] = None
    referencia_2: Optional[dict] = None


class NotaCreate(BaseModel):
    texto: str


class GestionCreate(BaseModel):
    canal: str      # llamada | whatsapp | visita | email
    resultado: str
    nota: Optional[str] = ""
    ptp_fecha: Optional[str] = None


class PTPCreate(BaseModel):
    ptp_fecha: str
    ptp_monto: float


# ── Helpers ───────────────────────────────────────────────────────────────────

def _score_letra(pct: float) -> str:
    if pct >= 90: return "A"
    if pct >= 70: return "B"
    if pct >= 50: return "C"
    return "F"


def _compute_score(cuotas: list) -> tuple[float, str]:
    pagadas = [c for c in cuotas if c.get("estado") == "pagada"]
    if not pagadas:
        return 100.0, "A"
    a_tiempo = sum(
        1 for c in pagadas
        if c.get("fecha_pago", "9999") <= c.get("fecha_vencimiento", "9999")
    )
    pct = round(a_tiempo / len(pagadas) * 100, 1)
    return pct, _score_letra(pct)


async def _get_loan_for_id(id: str) -> dict | None:
    """Try to find a loanbook record by loanbook id or client id/phone."""
    loan = await db.loanbook.find_one({"id": id}, {"_id": 0})
    if loan:
        return loan
    # Maybe id is a cliente_id
    loan = await db.loanbook.find_one(
        {"cliente_id": id, "estado": {"$in": ["activo", "mora"]}}, {"_id": 0}
    )
    return loan


async def _get_crm_for_loan(loan: dict) -> dict:
    """Return crm_clientes doc or minimal stub."""
    if not loan:
        return {}
    crm = await db.crm_clientes.find_one(
        {"$or": [
            {"id": loan.get("cliente_id", "")},
            {"telefono_principal": loan.get("cliente_telefono", "")},
        ]},
        {"_id": 0},
    )
    return crm or {}


# ── List ──────────────────────────────────────────────────────────────────────

@router.get("")
async def list_crm_clientes(
    bucket: Optional[str] = None,
    score: Optional[str] = None,
    buscar: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Return list of active clients with DPD, bucket and score info.
    Filters: bucket (RECUPERACION|CRITICO|URGENTE|ACTIVO|HOY|AL_DIA), score (A|B|C|F), buscar (name/cedula/phone).
    """
    today = date.today().isoformat()

    loan_query: dict = {"estado": {"$in": ["activo", "mora"]}}
    loans = await db.loanbook.find(loan_query, {"_id": 0}).to_list(500)

    results = []
    for loan in loans:
        cuotas = loan.get("cuotas", [])
        score_pct, score_letra = _compute_score(cuotas)

        # Compute DPD from first unpaid overdue cuota
        dpd = 0
        bucket_val = "AL_DIA"
        for c in sorted(cuotas, key=lambda x: x.get("fecha_vencimiento", "")):
            if c.get("estado") in ("pendiente", "vencida"):
                fv = c.get("fecha_vencimiento", "")
                if fv <= today:
                    dpd = (date.today() - date.fromisoformat(fv)).days
                    if dpd >= 22:
                        bucket_val = "RECUPERACION"
                    elif dpd >= 15:
                        bucket_val = "CRITICO"
                    elif dpd >= 8:
                        bucket_val = "URGENTE"
                    elif dpd >= 1:
                        bucket_val = "ACTIVO"
                    else:
                        bucket_val = "HOY"
                break

        # Filter by score
        if score and score != score_letra:
            continue
        # Filter by bucket
        if bucket and bucket != bucket_val:
            continue
        # Filter by buscar
        nombre = loan.get("cliente_nombre", "")
        cedula = loan.get("cliente_nit", "")
        telefono = loan.get("cliente_telefono", "")
        if buscar:
            q = buscar.lower()
            if not any(q in x.lower() for x in [nombre, cedula, telefono] if x):
                continue

        results.append({
            "id": loan["id"],
            "loanbook_id": loan["id"],
            "cliente_id": loan.get("cliente_id", ""),
            "cliente_nombre": nombre,
            "cliente_telefono": telefono,
            "cedula": cedula,
            "plan": loan.get("plan", ""),
            "moto": (f"{loan.get('moto_marca', '')} {loan.get('moto_version', '')}".strip()
                     or loan.get("moto_descripcion", "")),
            "estado": loan.get("estado", ""),
            "bucket": bucket_val,
            "dpd_actual": dpd,
            "saldo_pendiente": loan.get("saldo_pendiente", 0),
            "score_pct": score_pct,
            "score_letra": score_letra,
            "ultimo_contacto_fecha": loan.get("ultimo_contacto_fecha", ""),
            "ultimo_contacto_resultado": loan.get("ultimo_contacto_resultado", ""),
        })

    # Sort by DPD desc (most urgent first)
    results.sort(key=lambda x: -x["dpd_actual"])
    return results


# ── 360° Profile ──────────────────────────────────────────────────────────────

@router.get("/{id}")
async def get_crm_cliente(id: str, current_user=Depends(get_current_user)):
    """Return full 360° client profile. id can be loanbook_id or cliente_id."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    crm = await _get_crm_for_loan(loan)
    cuotas = loan.get("cuotas", [])
    score_pct, score_letra = _compute_score(cuotas)
    today = date.today().isoformat()

    # DPD and bucket
    dpd = 0
    bucket_val = "AL_DIA"
    for c in sorted(cuotas, key=lambda x: x.get("fecha_vencimiento", "")):
        if c.get("estado") in ("pendiente", "vencida"):
            fv = c.get("fecha_vencimiento", "")
            if fv <= today:
                dpd = (date.today() - date.fromisoformat(fv)).days
                bucket_val = (
                    "RECUPERACION" if dpd >= 22 else
                    "CRITICO"      if dpd >= 15 else
                    "URGENTE"      if dpd >= 8  else
                    "ACTIVO"       if dpd >= 1  else "HOY"
                )
            break

    # Gestiones history (from gestiones_cartera)
    gestiones = await db.gestiones_cartera.find(
        {"loanbook_id": loan["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)

    # WhatsApp history (from cartera_gestiones — Mercately)
    cedula = loan.get("cliente_nit", "")
    whatsapp_gestiones = []
    if cedula:
        whatsapp_gestiones = await db.cartera_gestiones.find(
            {"cliente_id": cedula}, {"_id": 0}
        ).sort("fecha", -1).to_list(50)

    # Payment history
    pagos = await db.cartera_pagos.find(
        {"loanbook_id": loan["id"]}, {"_id": 0}
    ).sort("fecha_pago", -1).to_list(100)

    # Mora acumulada
    mora_acumulada = sum(
        c.get("mora", 0) for c in cuotas if c.get("estado") in ("vencida", "pendiente")
    )
    cuotas_pagadas  = sum(1 for c in cuotas if c.get("estado") == "pagada")
    cuotas_vencidas = sum(1 for c in cuotas if c.get("estado") == "vencida")
    cuotas_pendientes = sum(1 for c in cuotas if c.get("estado") == "pendiente")
    proxima_cuota = next(
        (c for c in sorted(cuotas, key=lambda x: x.get("fecha_vencimiento", ""))
         if c.get("estado") in ("pendiente", "vencida")),
        None,
    )

    return {
        "loan": loan,
        "crm": crm,
        "score_pct": score_pct,
        "score_letra": score_letra,
        "bucket": bucket_val,
        "dpd_actual": dpd,
        "dias_para_protocolo": max(0, 22 - dpd),
        "mora_acumulada": mora_acumulada,
        "cuotas_pagadas": cuotas_pagadas,
        "cuotas_vencidas": cuotas_vencidas,
        "cuotas_pendientes": cuotas_pendientes,
        "proxima_cuota": proxima_cuota,
        "gestiones": gestiones,
        "whatsapp_gestiones": whatsapp_gestiones,
        "historial_pagos": pagos,
    }


# ── Edit datos del cliente ────────────────────────────────────────────────────

@router.put("/{id}/datos")
async def update_datos(id: str, req: DatosEditables, current_user=Depends(get_current_user)):
    """Update editable contact fields (phones, address, references, occupation)."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    crm = await _get_crm_for_loan(loan)

    update_dict = {k: v for k, v in req.dict().items() if v is not None}
    update_dict["updated_at"] = datetime.now(timezone.utc).isoformat()

    if crm:
        await db.crm_clientes.update_one(
            {"$or": [
                {"id": loan.get("cliente_id", "")},
                {"telefono_principal": loan.get("cliente_telefono", "")},
            ]},
            {"$set": update_dict},
        )
    else:
        # Create minimal crm record
        from services.crm_service import upsert_cliente
        await upsert_cliente(db, loan.get("cliente_telefono", ""), {
            "nombre_completo": loan.get("cliente_nombre", ""),
            **update_dict,
        })

    return {"ok": True, "updated": update_dict}


# ── Add nota ──────────────────────────────────────────────────────────────────

@router.post("/{id}/nota")
async def add_nota(id: str, req: NotaCreate, current_user=Depends(get_current_user)):
    """Append a cobrador note (immutable — cannot edit or delete)."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")
    crm = await _get_crm_for_loan(loan)

    cliente_id = crm.get("id", loan.get("cliente_id", ""))
    if not cliente_id:
        raise HTTPException(status_code=400, detail="El cliente no tiene ficha CRM. Crea el registro primero.")

    nota_doc = await agregar_nota(db, cliente_id, req.texto, current_user.get("email", ""))
    return nota_doc


# ── Register gestion ──────────────────────────────────────────────────────────

@router.post("/{id}/gestion")
async def register_gestion(id: str, req: GestionCreate, current_user=Depends(get_current_user)):
    """Register a contact attempt. id = loanbook_id."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    try:
        gestion = await registrar_gestion(
            db,
            loanbook_id=loan["id"],
            canal=req.canal,
            resultado=req.resultado,
            nota=req.nota or "",
            autor=current_user.get("email", ""),
            ptp_fecha=req.ptp_fecha,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return gestion


# ── Register PTP ──────────────────────────────────────────────────────────────

@router.post("/{id}/ptp")
async def register_ptp(id: str, req: PTPCreate, current_user=Depends(get_current_user)):
    """Register a promise-to-pay date and amount."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    ptp = await registrar_ptp(
        db, loan["id"], req.ptp_fecha, req.ptp_monto, current_user.get("email", "")
    )
    return ptp


# ── Acuerdos de Pago (FASE 8-A) ───────────────────────────────────────────────

class AcuerdoCreate(BaseModel):
    tipo: str = "acuerdo_total"   # pago_parcial | descuento_mora | refinanciacion | acuerdo_total
    condiciones: Optional[str] = ""
    monto_acordado: float = 0
    fecha_inicio: Optional[str] = None
    fecha_limite: Optional[str] = None
    cuotas_acuerdo: Optional[list] = []


class AcuerdoEstadoUpdate(BaseModel):
    estado: str   # activo | cumplido | incumplido | cancelado


@router.post("/{id}/acuerdo")
async def create_acuerdo(id: str, req: AcuerdoCreate, current_user=Depends(get_current_user)):
    """Crea un acuerdo de pago formal en acuerdos_pago + registra gestión 'acuerdo_firmado'."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    datos = req.dict()
    if not datos.get("fecha_inicio"):
        datos["fecha_inicio"] = date.today().isoformat()

    try:
        acuerdo = await crear_acuerdo(
            db,
            loanbook_id=loan["id"],
            datos=datos,
            autor=current_user.get("email", "sistema"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return acuerdo


@router.get("/{id}/acuerdos")
async def list_acuerdos(id: str, current_user=Depends(get_current_user)):
    """Lista todos los acuerdos de pago de un loanbook, ordenados por fecha."""
    loan = await _get_loan_for_id(id)
    if not loan:
        raise HTTPException(status_code=404, detail="Cliente no encontrado.")

    acuerdos = await db.acuerdos_pago.find(
        {"loanbook_id": loan["id"]}, {"_id": 0}
    ).sort("created_at", -1).to_list(100)

    return {"loanbook_id": loan["id"], "total": len(acuerdos), "acuerdos": acuerdos}


@router.put("/acuerdos/{acuerdo_id}/estado")
async def update_acuerdo_estado(acuerdo_id: str, req: AcuerdoEstadoUpdate, current_user=Depends(get_current_user)):
    """Actualiza el estado de un acuerdo de pago (cumplido | incumplido | cancelado | activo)."""
    try:
        acuerdo = await actualizar_estado_acuerdo(db, acuerdo_id, req.estado)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not acuerdo:
        raise HTTPException(status_code=404, detail="Acuerdo no encontrado.")

    return acuerdo
