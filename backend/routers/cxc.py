"""cxc.py — BUILD 20: Cuentas por Cobrar (Socios + Clientes).

Endpoints Socios:
  POST /api/cxc/socios/registrar            — CXC individual
  POST /api/cxc/socios/registrar-lote       — BackgroundTask batch
  POST /api/cxc/socios/abonar               — Abono a CXC
  GET  /api/cxc/socios/saldo/{socio}        — Saldo pendiente del socio
  GET  /api/cxc/socios/resumen              — Resumen total

Endpoints Clientes:
  POST /api/cxc/clientes/registrar
  GET  /api/cxc/clientes/saldo/{nit}
  GET  /api/cxc/clientes/vencidas
  POST /api/cxc/clientes/abonar
"""
import uuid
import logging
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import Optional, List

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user

router = APIRouter(prefix="/cxc", tags=["cxc"])
logger = logging.getLogger(__name__)

# ── IDs reales de Alegra — RODDOS SAS ─────────────────────────────────────────

CXC_SOCIOS_ID    = 5329   # 132505 — Cuentas por cobrar a socios y accionistas
CXC_CLIENTES_ID  = 5326   # 13050501 — Cuentas por cobrar clientes nacionales

# Cuentas bancarias CRÉDITO (de donde sale el dinero para CXC)
BANCOS_MAP: dict[str, int] = {
    "bancolombia":        5314,
    "bancolombia 2029":   5314,
    "bancolombia 2540":   5315,
    "bbva":               5318,
    "bbva 0210":          5318,
    "bbva 0212":          5319,
    "banco de bogota":    5321,
    "bdebogota":          5321,
    "davivienda":         5322,
}
DEFAULT_BANCO_ID = 5314

SOCIOS_VALIDOS = {
    "andres sanjuan":  {"nombre": "Andres Sanjuan",  "cedula": "80075452"},
    "ivan echeverri":  {"nombre": "Ivan Echeverri",  "cedula": "80086601"},
    "andrés sanjuan":  {"nombre": "Andres Sanjuan",  "cedula": "80075452"},
    "iván echeverri":  {"nombre": "Ivan Echeverri",  "cedula": "80086601"},
    "andres":          {"nombre": "Andres Sanjuan",  "cedula": "80075452"},
    "ivan":            {"nombre": "Ivan Echeverri",  "cedula": "80086601"},
    "80075452":        {"nombre": "Andres Sanjuan",  "cedula": "80075452"},
    "80086601":        {"nombre": "Ivan Echeverri",  "cedula": "80086601"},
}

_jobs: dict[str, dict] = {}


# ── Helpers ───────────────────────────────────────────────────────────────────

def _resolve_banco_id(banco_str: str) -> int:
    import unicodedata
    if not banco_str:
        return DEFAULT_BANCO_ID
    norm = unicodedata.normalize("NFD", banco_str.lower().strip()).encode("ascii", "ignore").decode()
    for key, bid in BANCOS_MAP.items():
        key_norm = unicodedata.normalize("NFD", key.lower()).encode("ascii", "ignore").decode()
        if key_norm in norm or norm in key_norm:
            return bid
    return DEFAULT_BANCO_ID


def _resolve_socio(socio_str: str) -> dict | None:
    import unicodedata
    norm = unicodedata.normalize("NFD", socio_str.lower().strip()).encode("ascii", "ignore").decode()
    for key, val in SOCIOS_VALIDOS.items():
        key_n = unicodedata.normalize("NFD", key.lower()).encode("ascii", "ignore").decode()
        if key_n == norm or key_n in norm or norm in key_n:
            return val
    return None


# ══════════════════════════════════════════════════════════════════════════════
# CXC SOCIOS
# ══════════════════════════════════════════════════════════════════════════════

class CxcSocioReq(BaseModel):
    fecha: str
    socio: str                           # "Andres Sanjuan" | "Ivan Echeverri"
    descripcion: str
    monto: float
    pagado_a: str = ""                   # a quién se pagó el dinero
    banco_origen: str = "Bancolombia"    # de qué banco salió


@router.post("/socios/registrar")
async def registrar_cxc_socio(
    req: CxcSocioReq,
    current_user=Depends(get_current_user),
):
    """Registra una CXC de socio:
       DÉBITO CXC socios (5329) / CRÉDITO Banco (111005).
    """
    socio_info = _resolve_socio(req.socio)
    if not socio_info:
        raise HTTPException(status_code=400, detail=f"Socio '{req.socio}' no reconocido. Válidos: Andres Sanjuan, Ivan Echeverri")
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser positivo")

    banco_id = _resolve_banco_id(req.banco_origen)

    # Anti-duplicado: mismo socio, monto, fecha, descripción
    existing = await db.cxc_socios.find_one({
        "socio": socio_info["nombre"],
        "fecha": req.fecha,
        "monto": req.monto,
        "descripcion": req.descripcion,
    })
    if existing:
        return {
            "ok": False,
            "error": "Esta CXC ya existe (anti-duplicado)",
            "existing_id": str(existing.get("_id")),
        }

    alegra = AlegraService(db)
    obs = f"CXC {socio_info['nombre']} — {req.descripcion}"
    if req.pagado_a:
        obs += f" | Pagado a: {req.pagado_a}"

    payload = {
        "date":         req.fecha,
        "observations": obs,
        "entries": [
            {"id": CXC_SOCIOS_ID, "debit": round(req.monto), "credit": 0},
            {"id": banco_id,      "debit": 0, "credit": round(req.monto)},
        ],
    }

    result = await alegra.request("journals", "POST", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise HTTPException(status_code=502, detail=f"Alegra no creó el journal: {result}")

    alegra_id = str(result["id"])
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "fecha":            req.fecha,
        "socio":            socio_info["nombre"],
        "cedula":           socio_info["cedula"],
        "descripcion":      req.descripcion,
        "monto":            req.monto,
        "pagado_a":         req.pagado_a,
        "banco_origen":     req.banco_origen,
        "banco_id":         banco_id,
        "alegra_journal_id": alegra_id,
        "estado":           "pendiente",
        "abonos":           [],
        "saldo_pendiente":  req.monto,
        "creado_por":       current_user.get("email", ""),
        "timestamp":        now,
    }
    result_insert = await db.cxc_socios.insert_one(doc)

    await db.roddos_events.insert_one({
        "event_type":   "cxc.socio.registrada",
        "cxc_id":       str(result_insert.inserted_id),
        "alegra_id":    alegra_id,
        "socio":        socio_info["nombre"],
        "monto":        req.monto,
        "creado_por":   current_user.get("email", ""),
        "fecha":        now,
    })

    logger.info("CXC socio registrada: %s $%s alegra_id=%s", socio_info["nombre"], req.monto, alegra_id)
    return {
        "ok":        True,
        "alegra_id": alegra_id,
        "cxc_id":    str(result_insert.inserted_id),
        "mensaje":   f"CXC de {socio_info['nombre']} por ${req.monto:,.0f} registrada (journal #{alegra_id})",
    }


# ── Lote de CXC socios (background) ───────────────────────────────────────────

class CxcSocioLoteItem(BaseModel):
    fecha: str
    socio: str
    descripcion: str
    monto: float
    pagado_a: str = ""
    banco_origen: str = "Bancolombia"


class CxcSocioLoteReq(BaseModel):
    items: List[CxcSocioLoteItem]


async def _run_cxc_lote(job_id: str, items: list[dict], user_email: str):
    """Background task: registra lote de CXC socios."""
    import asyncio
    alegra = AlegraService(db)
    exitosos, errores, duplicados = [], [], []
    _jobs[job_id].update({"estado": "procesando", "total": len(items), "procesados": 0})

    for i, item in enumerate(items):
        try:
            socio_info = _resolve_socio(item["socio"])
            if not socio_info:
                errores.append({**item, "error": f"Socio '{item['socio']}' no reconocido"})
                continue

            banco_id = _resolve_banco_id(item.get("banco_origen", "Bancolombia"))

            # Anti-duplicado
            existing = await db.cxc_socios.find_one({
                "socio": socio_info["nombre"],
                "fecha": item["fecha"],
                "monto": item["monto"],
                "descripcion": item["descripcion"],
            })
            if existing:
                duplicados.append({**item, "msg": "duplicado omitido"})
                _jobs[job_id]["duplicados"] = len(duplicados)
                continue

            obs = f"CXC {socio_info['nombre']} — {item['descripcion']}"
            if item.get("pagado_a"):
                obs += f" | Pagado a: {item['pagado_a']}"

            payload = {
                "date":         item["fecha"],
                "observations": obs,
                "entries": [
                    {"id": CXC_SOCIOS_ID, "debit": round(item["monto"]), "credit": 0},
                    {"id": banco_id,      "debit": 0, "credit": round(item["monto"])},
                ],
            }
            result = await alegra.request("journals", "POST", payload)
            if not isinstance(result, dict) or not result.get("id"):
                raise ValueError(f"Alegra no retornó ID: {result}")

            alegra_id = str(result["id"])
            now = datetime.now(timezone.utc).isoformat()

            doc = {
                "fecha":            item["fecha"],
                "socio":            socio_info["nombre"],
                "cedula":           socio_info["cedula"],
                "descripcion":      item["descripcion"],
                "monto":            item["monto"],
                "pagado_a":         item.get("pagado_a", ""),
                "banco_origen":     item.get("banco_origen", "Bancolombia"),
                "banco_id":         banco_id,
                "alegra_journal_id": alegra_id,
                "estado":           "pendiente",
                "abonos":           [],
                "saldo_pendiente":  item["monto"],
                "job_id":           job_id,
                "creado_por":       user_email,
                "timestamp":        now,
            }
            await db.cxc_socios.insert_one(doc)
            exitosos.append({**item, "alegra_id": alegra_id, "socio_nombre": socio_info["nombre"]})

        except Exception as e:
            errores.append({**item, "error": str(e)})
            logger.error("cxc_lote error item %s: %s", i, e)

        _jobs[job_id]["procesados"] = i + 1
        _jobs[job_id]["exitosos"]   = len(exitosos)
        _jobs[job_id]["errores"]    = len(errores)

        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)

    now = datetime.now(timezone.utc).isoformat()
    alegra_ids = [e.get("alegra_id", "") for e in exitosos]

    await db.roddos_events.insert_one({
        "event_type": "cxc.socios.lote",
        "job_id":     job_id,
        "procesados": len(items),
        "exitosos":   len(exitosos),
        "errores":    len(errores),
        "duplicados": len(duplicados),
        "alegra_ids": alegra_ids,
        "creado_por": user_email,
        "fecha":      now,
    })

    _jobs[job_id].update({
        "estado":       "completado",
        "alegra_ids":   alegra_ids,
        "filas_error":  errores,
        "duplicados":   len(duplicados),
        "completado_en": now,
    })
    logger.info("cxc_lote %s completado: %d exitosos, %d errores, %d duplicados", job_id, len(exitosos), len(errores), len(duplicados))


@router.post("/socios/registrar-lote")
async def registrar_lote_cxc_socios(
    req: CxcSocioLoteReq,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Registra múltiples CXC socios en background. Retorna job_id inmediatamente."""
    if not req.items:
        raise HTTPException(status_code=400, detail="No hay items para procesar")
    if len(req.items) > 200:
        raise HTTPException(status_code=400, detail="Máximo 200 items por lote")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id":     job_id,
        "estado":     "iniciando",
        "total":      len(req.items),
        "procesados": 0,
        "exitosos":   0,
        "errores":    0,
        "duplicados": 0,
        "creado_en":  datetime.now(timezone.utc).isoformat(),
    }
    items_plain = [item.model_dump() for item in req.items]
    background_tasks.add_task(_run_cxc_lote, job_id, items_plain, current_user.get("email", ""))
    return {
        "ok":      True,
        "job_id":  job_id,
        "total":   len(req.items),
        "mensaje": f"Procesamiento de {len(req.items)} CXC iniciado. Consulta /api/cxc/status/{job_id}",
    }


# ── GET /cxc/status/{job_id} ──────────────────────────────────────────────────
@router.get("/status/{job_id}")
async def get_cxc_job_status(job_id: str, current_user=Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        ev = await db.roddos_events.find_one(
            {"job_id": job_id, "event_type": {"$in": ["cxc.socios.lote"]}},
            {"_id": 0},
        )
        if ev:
            return {
                "job_id":   job_id,
                "estado":   "completado",
                "total":    ev.get("procesados", 0),
                "exitosos": ev.get("exitosos", 0),
                "errores":  ev.get("errores", 0),
                "duplicados": ev.get("duplicados", 0),
            }
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return {k: v for k, v in job.items() if k not in ("filas_error",)} | {
        "tiene_errores": len(job.get("filas_error", [])) > 0
    }


# ── POST /cxc/socios/abonar ───────────────────────────────────────────────────

class AbonoSocioReq(BaseModel):
    socio: str
    monto: float
    fecha: str
    banco_destino: str = "Bancolombia"   # donde entra el pago
    descripcion: str = ""
    cxc_id: str = ""                     # opcional: id específico a abonar


@router.post("/socios/abonar")
async def abonar_cxc_socio(
    req: AbonoSocioReq,
    current_user=Depends(get_current_user),
):
    """Registra un abono del socio:
       DÉBITO Banco / CRÉDITO CXC socios.
       Actualiza saldo_pendiente en MongoDB.
    """
    socio_info = _resolve_socio(req.socio)
    if not socio_info:
        raise HTTPException(status_code=400, detail=f"Socio '{req.socio}' no reconocido")
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser positivo")

    banco_id = _resolve_banco_id(req.banco_destino)
    alegra = AlegraService(db)

    # Crear journal en Alegra: DÉBITO banco / CRÉDITO CXC socios
    obs = f"Abono CXC {socio_info['nombre']} — {req.descripcion or 'Pago recibido'}"
    payload = {
        "date":         req.fecha,
        "observations": obs,
        "entries": [
            {"id": banco_id,      "debit": round(req.monto), "credit": 0},
            {"id": CXC_SOCIOS_ID, "debit": 0, "credit": round(req.monto)},
        ],
    }
    result = await alegra.request("journals", "POST", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise HTTPException(status_code=502, detail=f"Alegra no creó el journal: {result}")

    alegra_id = str(result["id"])
    now = datetime.now(timezone.utc).isoformat()
    abono_entry = {
        "fecha":       req.fecha,
        "monto":       req.monto,
        "alegra_journal_id": alegra_id,
        "timestamp":   now,
    }

    # Si cxc_id específico — abonar solo a ese registro
    if req.cxc_id:
        from bson import ObjectId
        cxc_doc = await db.cxc_socios.find_one({"_id": ObjectId(req.cxc_id)})
        if cxc_doc:
            nuevo_saldo = max(0, cxc_doc["saldo_pendiente"] - req.monto)
            nuevo_estado = "saldado" if nuevo_saldo == 0 else "abonado"
            await db.cxc_socios.update_one(
                {"_id": ObjectId(req.cxc_id)},
                {"$push": {"abonos": abono_entry}, "$set": {"saldo_pendiente": nuevo_saldo, "estado": nuevo_estado}},
            )
    else:
        # Distribuir el abono en pendientes del socio (FIFO)
        pendientes = await db.cxc_socios.find(
            {"socio": socio_info["nombre"], "estado": {"$in": ["pendiente", "abonado"]}, "saldo_pendiente": {"$gt": 0}},
        ).sort("fecha", 1).to_list(100)

        restante = req.monto
        for cxc in pendientes:
            if restante <= 0:
                break
            from bson import ObjectId
            aplicar = min(restante, cxc["saldo_pendiente"])
            nuevo_saldo = cxc["saldo_pendiente"] - aplicar
            nuevo_estado = "saldado" if nuevo_saldo == 0 else "abonado"
            await db.cxc_socios.update_one(
                {"_id": cxc["_id"]},
                {"$push": {"abonos": abono_entry}, "$set": {"saldo_pendiente": nuevo_saldo, "estado": nuevo_estado}},
            )
            restante -= aplicar

    await db.roddos_events.insert_one({
        "event_type": "cxc.socio.abono",
        "alegra_id":  alegra_id,
        "socio":      socio_info["nombre"],
        "monto":      req.monto,
        "creado_por": current_user.get("email", ""),
        "fecha":      now,
    })

    # Calcular nuevo saldo total del socio
    cursor = db.cxc_socios.aggregate([
        {"$match": {"socio": socio_info["nombre"], "estado": {"$in": ["pendiente", "abonado"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$saldo_pendiente"}}},
    ])
    saldo_total = 0
    async for doc in cursor:
        saldo_total = doc["total"]

    return {
        "ok":         True,
        "alegra_id":  alegra_id,
        "nuevo_saldo_total": saldo_total,
        "mensaje":    f"Abono de ${req.monto:,.0f} registrado para {socio_info['nombre']}. Saldo total pendiente: ${saldo_total:,.0f}",
    }


# ── GET /cxc/socios/saldo/{socio} ─────────────────────────────────────────────
@router.get("/socios/saldo/{socio}")
async def get_saldo_socio(socio: str, current_user=Depends(get_current_user)):
    """Retorna el saldo pendiente total de un socio."""
    socio_info = _resolve_socio(socio)
    if not socio_info:
        raise HTTPException(status_code=404, detail=f"Socio '{socio}' no reconocido")

    cursor = db.cxc_socios.aggregate([
        {"$match": {"socio": socio_info["nombre"], "estado": {"$in": ["pendiente", "abonado"]}}},
        {"$group": {"_id": None, "total": {"$sum": "$saldo_pendiente"}, "registros": {"$sum": 1}}},
    ])
    saldo_total, registros = 0, 0
    async for doc in cursor:
        saldo_total = doc["total"]
        registros   = doc["registros"]

    detalle = await db.cxc_socios.find(
        {"socio": socio_info["nombre"], "estado": {"$in": ["pendiente", "abonado"]}},
        {"_id": 0, "fecha": 1, "descripcion": 1, "monto": 1, "saldo_pendiente": 1, "estado": 1, "alegra_journal_id": 1},
    ).sort("fecha", 1).to_list(200)

    return {
        "socio":          socio_info["nombre"],
        "cedula":         socio_info["cedula"],
        "saldo_pendiente": saldo_total,
        "registros":      registros,
        "detalle":        detalle,
    }


# ── GET /cxc/socios/resumen ───────────────────────────────────────────────────
@router.get("/socios/resumen")
async def resumen_cxc_socios(current_user=Depends(get_current_user)):
    """Total CXC pendiente por socio y gran total."""
    cursor = db.cxc_socios.aggregate([
        {"$match": {"estado": {"$in": ["pendiente", "abonado"]}}},
        {"$group": {"_id": "$socio", "saldo": {"$sum": "$saldo_pendiente"}, "registros": {"$sum": 1}}},
    ])
    por_socio = {}
    gran_total = 0
    async for doc in cursor:
        por_socio[doc["_id"]] = {"saldo": doc["saldo"], "registros": doc["registros"]}
        gran_total += doc["saldo"]

    return {
        "por_socio":   por_socio,
        "gran_total":  gran_total,
        "socios":      list(por_socio.keys()),
    }


# ══════════════════════════════════════════════════════════════════════════════
# CXC CLIENTES
# ══════════════════════════════════════════════════════════════════════════════

class CxcClienteReq(BaseModel):
    fecha: str
    cliente: str
    nit_cliente: str = ""
    descripcion: str
    monto: float
    vencimiento: str = ""
    referencia: str = ""


@router.post("/clientes/registrar")
async def registrar_cxc_cliente(
    req: CxcClienteReq,
    current_user=Depends(get_current_user),
):
    """Registra CXC cliente:
       DÉBITO CXC clientes (5326) / CRÉDITO Otros Ingresos (5436).
    """
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser positivo")

    # Anti-duplicado
    existing = await db.cxc_clientes.find_one({
        "cliente": req.cliente, "fecha": req.fecha, "monto": req.monto, "descripcion": req.descripcion
    })
    if existing:
        return {"ok": False, "error": "CXC ya registrada (anti-duplicado)", "existing_id": str(existing.get("_id"))}

    alegra = AlegraService(db)
    payload = {
        "date":         req.fecha,
        "observations": f"CXC {req.cliente} — {req.descripcion}",
        "entries": [
            {"id": CXC_CLIENTES_ID, "debit": round(req.monto), "credit": 0},
            {"id": 5436,            "debit": 0, "credit": round(req.monto)},  # Otros ingresos
        ],
    }
    result = await alegra.request("journals", "POST", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise HTTPException(status_code=502, detail=f"Alegra no creó el journal: {result}")

    alegra_id = str(result["id"])
    now = datetime.now(timezone.utc).isoformat()
    vencimiento = req.vencimiento or req.fecha

    doc = {
        "fecha":            req.fecha,
        "cliente":          req.cliente,
        "nit_cliente":      req.nit_cliente,
        "descripcion":      req.descripcion,
        "monto":            req.monto,
        "vencimiento":      vencimiento,
        "referencia":       req.referencia,
        "alegra_journal_id": alegra_id,
        "estado":           "pendiente",
        "abonos":           [],
        "saldo_pendiente":  req.monto,
        "creado_por":       current_user.get("email", ""),
        "timestamp":        now,
    }
    result_insert = await db.cxc_clientes.insert_one(doc)

    await db.roddos_events.insert_one({
        "event_type": "cxc.cliente.registrada",
        "cxc_id":     str(result_insert.inserted_id),
        "alegra_id":  alegra_id,
        "cliente":    req.cliente,
        "monto":      req.monto,
        "creado_por": current_user.get("email", ""),
        "fecha":      now,
    })

    return {"ok": True, "alegra_id": alegra_id, "cxc_id": str(result_insert.inserted_id),
            "mensaje": f"CXC cliente {req.cliente} por ${req.monto:,.0f} registrada (journal #{alegra_id})"}


@router.get("/clientes/saldo/{nit}")
async def get_saldo_cliente(nit: str, current_user=Depends(get_current_user)):
    cliente_docs = await db.cxc_clientes.find(
        {"nit_cliente": nit, "estado": {"$in": ["pendiente", "abonado"]}},
        {"_id": 0}
    ).to_list(100)
    if not cliente_docs:
        # Try by name
        cliente_docs = await db.cxc_clientes.find(
            {"cliente": {"$regex": nit, "$options": "i"}, "estado": {"$in": ["pendiente", "abonado"]}},
            {"_id": 0}
        ).to_list(100)

    total = sum(d.get("saldo_pendiente", 0) for d in cliente_docs)
    return {"cliente": cliente_docs[0].get("cliente", nit) if cliente_docs else nit,
            "saldo_total": total, "registros": len(cliente_docs), "detalle": cliente_docs}


@router.get("/clientes/vencidas")
async def get_cxc_vencidas(current_user=Depends(get_current_user)):
    """CXC con fecha de vencimiento pasada y saldo pendiente > 0."""
    hoy = date.today().isoformat()
    docs = await db.cxc_clientes.find(
        {"vencimiento": {"$lt": hoy}, "estado": {"$in": ["pendiente", "abonado"]}, "saldo_pendiente": {"$gt": 0}},
        {"_id": 0},
    ).sort("vencimiento", 1).to_list(200)
    total_vencido = sum(d.get("saldo_pendiente", 0) for d in docs)
    return {"vencidas": docs, "total_vencido": total_vencido, "cantidad": len(docs)}


class AbonoClienteReq(BaseModel):
    cxc_id: str
    monto: float
    fecha: str
    banco_destino: str = "Bancolombia"
    descripcion: str = ""


@router.post("/clientes/abonar")
async def abonar_cxc_cliente(
    req: AbonoClienteReq,
    current_user=Depends(get_current_user),
):
    from bson import ObjectId
    cxc_doc = await db.cxc_clientes.find_one({"_id": ObjectId(req.cxc_id)})
    if not cxc_doc:
        raise HTTPException(status_code=404, detail="CXC no encontrada")
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser positivo")

    banco_id = _resolve_banco_id(req.banco_destino)
    alegra = AlegraService(db)
    payload = {
        "date":         req.fecha,
        "observations": f"Abono CXC {cxc_doc['cliente']} — {req.descripcion or 'Pago recibido'}",
        "entries": [
            {"id": banco_id,         "debit": round(req.monto), "credit": 0},
            {"id": CXC_CLIENTES_ID,  "debit": 0, "credit": round(req.monto)},
        ],
    }
    result = await alegra.request("journals", "POST", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise HTTPException(status_code=502, detail=f"Alegra no creó el journal: {result}")

    alegra_id = str(result["id"])
    now = datetime.now(timezone.utc).isoformat()
    nuevo_saldo = max(0, cxc_doc["saldo_pendiente"] - req.monto)
    nuevo_estado = "saldado" if nuevo_saldo == 0 else "abonado"

    await db.cxc_clientes.update_one(
        {"_id": ObjectId(req.cxc_id)},
        {
            "$push": {"abonos": {"fecha": req.fecha, "monto": req.monto, "alegra_journal_id": alegra_id, "timestamp": now}},
            "$set":  {"saldo_pendiente": nuevo_saldo, "estado": nuevo_estado},
        },
    )
    return {"ok": True, "alegra_id": alegra_id, "nuevo_saldo": nuevo_saldo,
            "mensaje": f"Abono registrado. Saldo pendiente: ${nuevo_saldo:,.0f}"}
