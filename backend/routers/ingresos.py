"""ingresos.py — BUILD 20: Registro de Ingresos No Operacionales.

Endpoints:
  GET  /api/ingresos/plantilla          — CSV plantilla (7 cols)
  POST /api/ingresos/preview            — Parse CSV → resumen sin escribir en Alegra
  POST /api/ingresos/procesar           — BackgroundTask: crea journals en Alegra
  GET  /api/ingresos/status/{job_id}    — Estado del job
  GET  /api/ingresos/historial          — Ingresos registrados (con filtros de fecha)
  GET  /api/ingresos/plan               — Plan de ingresos (tipos válidos)
"""
import io
import csv as _csv_module
import uuid
import logging
from datetime import datetime, timezone, date

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user

router = APIRouter(prefix="/ingresos", tags=["ingresos"])
logger = logging.getLogger(__name__)

# ── IDs reales de Alegra — RODDOS SAS ─────────────────────────────────────────

# Cuentas CRÉDITO (ingreso)
PLAN_INGRESOS_RODDOS = [
    {
        "tipo_ingreso":        "Intereses_Bancarios",
        "cuenta_nombre":       "Intereses (Actividades Financieras)",
        "cuenta_codigo":       "415020",
        "alegra_id":           5455,
        "activo":              True,
    },
    {
        "tipo_ingreso":        "Venta_Motos_Recuperadas",
        "cuenta_nombre":       "Utilidad en venta de activos",
        "cuenta_codigo":       "42450501",
        "alegra_id":           5441,
        "activo":              True,
    },
    {
        "tipo_ingreso":        "Otros_Ingresos_No_Op",
        "cuenta_nombre":       "Otros ingresos (no operacionales)",
        "cuenta_codigo":       "42",
        "alegra_id":           5436,
        "activo":              True,
    },
    {
        "tipo_ingreso":        "Devoluciones_Ajustes",
        "cuenta_nombre":       "Devoluciones en ventas",
        "cuenta_codigo":       "41750501",
        "alegra_id":           5457,
        "activo":              True,
    },
]

# Cuentas bancarias DÉBITO (donde entra el dinero)
BANCOS_MAP: dict[str, int] = {
    "bancolombia":        5314,   # Bancolombia 2029 (default)
    "bancolombia 2029":   5314,
    "bancolombia 2540":   5315,
    "bbva":               5318,   # BBVA 0210 (default)
    "bbva 0210":          5318,
    "bbva 0212":          5319,
    "banco de bogota":    5321,
    "bdebogota":          5321,
    "davivienda":         5322,
}
DEFAULT_BANCO_ID    = 5314   # Bancolombia 2029
DEFAULT_BANCO_NAME  = "Bancolombia 2029"

_jobs: dict[str, dict] = {}  # In-memory job state (same pattern as gastos)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _normalize(s: str) -> str:
    import unicodedata
    return unicodedata.normalize("NFD", s.lower().strip()).encode("ascii", "ignore").decode()


def _resolve_banco_id(banco_str: str) -> int:
    if not banco_str:
        return DEFAULT_BANCO_ID
    norm = _normalize(banco_str)
    for key, bid in BANCOS_MAP.items():
        if _normalize(key) in norm or norm in _normalize(key):
            return bid
    return DEFAULT_BANCO_ID


def _resolve_plan_ingreso(tipo_str: str) -> dict | None:
    norm_input = _normalize(tipo_str)
    for entry in PLAN_INGRESOS_RODDOS:
        if _normalize(entry["tipo_ingreso"]) == norm_input:
            return entry
    # Fuzzy match
    for entry in PLAN_INGRESOS_RODDOS:
        if norm_input in _normalize(entry["tipo_ingreso"]) or _normalize(entry["tipo_ingreso"]) in norm_input:
            return entry
    return None


def _parse_monto(v) -> float:
    if v is None:
        return 0.0
    s = str(v).replace("$", "").replace(".", "").replace(",", "").strip()
    try:
        return float(s)
    except Exception:
        return 0.0


# ── GET /ingresos/plan ─────────────────────────────────────────────────────────
@router.get("/plan")
async def get_plan_ingresos(current_user=Depends(get_current_user)):
    """Retorna los tipos de ingreso válidos con sus IDs de Alegra."""
    entries = await db.plan_ingresos_roddos.find({"activo": True}, {"_id": 0}).to_list(50)
    if not entries:
        entries = PLAN_INGRESOS_RODDOS
    return {"plan": entries, "total": len(entries)}


# ── GET /ingresos/plantilla ────────────────────────────────────────────────────
@router.get("/plantilla")
async def descargar_plantilla_ingresos(current_user=Depends(get_current_user)):
    """CSV de ingresos: fecha, tipo_ingreso, descripcion, monto, tercero, banco, referencia"""
    tipos = " | ".join(e["tipo_ingreso"] for e in PLAN_INGRESOS_RODDOS)
    bancos = "Bancolombia | BBVA | Banco de Bogota | Davivienda"
    lines = [
        "fecha,tipo_ingreso,descripcion,monto,tercero,banco,referencia",
        f"# Tipos válidos: {tipos}",
        f"# Bancos válidos: {bancos}",
        "# Ejemplo (elimina el # para que sea fila de datos):",
        f"# {date.today().isoformat()},Venta_Motos_Recuperadas,Venta motos recuperadas Motos del Tropico,3000000,Motos del Tropico,Bancolombia,FAC-2026-001",
        "#",
        "# Completa tus datos desde esta línea (sin el # al inicio):",
    ]
    return StreamingResponse(
        io.BytesIO("\n".join(lines).encode("utf-8-sig")),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="RODDOS_Plantilla_Ingresos.csv"'},
    )


# ── POST /ingresos/preview ─────────────────────────────────────────────────────
@router.post("/preview")
async def preview_ingresos_csv(
    file: UploadFile = File(...),
    current_user=Depends(get_current_user),
):
    """Valida CSV y retorna resumen sin escribir nada en Alegra."""
    if not (file.filename or "").endswith(".csv"):
        return {
            "ok": False,
            "error": "Solo .csv. Si tienes .xlsx: Archivo → Guardar como → CSV UTF-8",
        }
    contents = await file.read()
    try:
        text = contents.decode("utf-8-sig")
    except UnicodeDecodeError:
        text = contents.decode("latin-1", errors="replace")

    data_lines = [ln for ln in text.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    if not data_lines:
        return {"ok": False, "error": "El CSV está vacío."}

    delimiter = ";" if (data_lines[0].count(";") > data_lines[0].count(",")) else ","
    reader = _csv_module.DictReader(data_lines, delimiter=delimiter)

    validos, errores, por_tipo = [], [], {}

    for row_num, row in enumerate(reader, start=2):
        def g(key): return str(row.get(key, "") or row.get(key.capitalize(), "") or "").strip()

        tipo_str = g("tipo_ingreso")
        monto = _parse_monto(g("monto"))
        tercero = g("tercero")
        banco = g("banco")

        if not tipo_str or not tercero:
            errores.append({"fila": row_num, "motivo": "Falta tipo_ingreso o tercero"})
            continue
        if monto <= 0:
            errores.append({"fila": row_num, "motivo": f"Monto inválido ('{g('monto')}')"})
            continue
        plan_entry = _resolve_plan_ingreso(tipo_str)
        if not plan_entry:
            errores.append({"fila": row_num, "motivo": f"Tipo '{tipo_str}' no válido. Válidos: {[e['tipo_ingreso'] for e in PLAN_INGRESOS_RODDOS]}"})
            continue

        tipo_key = plan_entry["tipo_ingreso"]
        if tipo_key not in por_tipo:
            por_tipo[tipo_key] = {"filas": 0, "monto": 0}
        por_tipo[tipo_key]["filas"] += 1
        por_tipo[tipo_key]["monto"] += monto
        validos.append({
            "row_num":    row_num,
            "fecha":      g("fecha") or date.today().isoformat(),
            "tipo_ingreso": tipo_key,
            "descripcion": g("descripcion"),
            "monto":      monto,
            "tercero":    tercero,
            "banco":      banco,
            "referencia": g("referencia"),
            "cuenta_credito_id":   plan_entry["alegra_id"],
            "cuenta_credito_nombre": plan_entry["cuenta_nombre"],
            "banco_debito_id":     _resolve_banco_id(banco),
        })

    return {
        "ok":          True,
        "total_filas": len(validos),
        "filas_validas": len(validos),
        "filas_error": len(errores),
        "por_tipo":    por_tipo,
        "monto_total": sum(r["monto"] for r in validos),
        "filas":       validos,
        "errores":     errores,
    }


# ── Background job ────────────────────────────────────────────────────────────

async def _run_ingresos_job(job_id: str, filas: list[dict], user_email: str):
    """Crea journal-entries en Alegra para cada fila de ingreso."""
    import asyncio
    alegra = AlegraService(db)
    exitosos, errores = [], []
    _jobs[job_id].update({"estado": "procesando", "total": len(filas), "procesados": 0})

    for i, fila in enumerate(filas):
        try:
            payload = {
                "date":         fila["fecha"],
                "observations": f"{fila.get('descripcion') or fila['tipo_ingreso']} — {fila['tercero']}",
                "entries": [
                    {"id": fila["banco_debito_id"],    "debit": round(fila["monto"]), "credit": 0},
                    {"id": fila["cuenta_credito_id"],  "debit": 0, "credit": round(fila["monto"])},
                ],
            }
            result = await alegra.request("journals", "POST", payload)
            if not isinstance(result, dict) or not result.get("id"):
                raise ValueError(f"Alegra no retornó ID: {result}")
            alegra_id = str(result["id"])
            exitosos.append({**fila, "alegra_id": alegra_id})
            logger.info("ingreso_journal creado: id=%s tipo=%s monto=%s", alegra_id, fila["tipo_ingreso"], fila["monto"])
        except Exception as e:
            errores.append({**fila, "error": str(e)})
            logger.error("ingreso_journal error fila %s: %s", fila.get("row_num"), e)

        _jobs[job_id]["procesados"] = i + 1
        _jobs[job_id]["exitosos"]   = len(exitosos)
        _jobs[job_id]["errores"]    = len(errores)

        if (i + 1) % 10 == 0:
            await asyncio.sleep(1)

    now = datetime.now(timezone.utc).isoformat()
    alegra_ids = [e["alegra_id"] for e in exitosos if e.get("alegra_id")]

    await db.roddos_events.insert_one({
        "event_type": "ingreso.masivo.registrado",
        "job_id":     job_id,
        "procesados": len(filas),
        "exitosos":   len(exitosos),
        "errores":    len(errores),
        "alegra_ids": alegra_ids,
        "filas":      exitosos,
        "filas_error": errores,
        "creado_por": user_email,
        "fecha":      now,
    })

    # Persist individual records to ingresos_registrados
    for item in exitosos:
        await db.ingresos_registrados.update_one(
            {"referencia": item.get("referencia"), "fecha": item["fecha"], "tercero": item["tercero"]},
            {"$setOnInsert": {**item, "timestamp": now}},
            upsert=True,
        )

    _jobs[job_id].update({
        "estado":       "completado",
        "alegra_ids":   alegra_ids,
        "filas_error":  errores,
        "completado_en": now,
    })
    logger.info("ingresos_job %s completado: %d exitosos, %d errores", job_id, len(exitosos), len(errores))


# ── POST /ingresos/procesar ────────────────────────────────────────────────────
class ProcesarIngresosReq(BaseModel):
    filas: List[dict]


@router.post("/procesar")
async def procesar_ingresos(
    req: ProcesarIngresosReq,
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Inicia procesamiento en background. Retorna job_id inmediatamente."""
    if not req.filas:
        raise HTTPException(status_code=400, detail="No hay ingresos para procesar")
    if len(req.filas) > 200:
        raise HTTPException(status_code=400, detail="Máximo 200 ingresos por solicitud")

    job_id = str(uuid.uuid4())
    _jobs[job_id] = {
        "job_id":     job_id,
        "estado":     "iniciando",
        "total":      len(req.filas),
        "procesados": 0,
        "exitosos":   0,
        "errores":    0,
        "creado_en":  datetime.now(timezone.utc).isoformat(),
    }
    background_tasks.add_task(_run_ingresos_job, job_id, req.filas, current_user.get("email", ""))
    return {"ok": True, "job_id": job_id, "total": len(req.filas),
            "mensaje": f"Procesamiento iniciado para {len(req.filas)} ingresos. Consulta /api/ingresos/status/{job_id}"}


# ── GET /ingresos/status/{job_id} ─────────────────────────────────────────────
@router.get("/status/{job_id}")
async def get_ingreso_job_status(job_id: str, current_user=Depends(get_current_user)):
    job = _jobs.get(job_id)
    if not job:
        ev = await db.roddos_events.find_one(
            {"job_id": job_id, "event_type": "ingreso.masivo.registrado"}, {"_id": 0}
        )
        if ev:
            return {
                "job_id":   job_id,
                "estado":   "completado",
                "total":    ev.get("procesados", 0),
                "exitosos": ev.get("exitosos", 0),
                "errores":  ev.get("errores", 0),
                "alegra_ids": ev.get("alegra_ids", []),
            }
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return {k: v for k, v in job.items() if k not in ("filas_error",)} | {
        "tiene_errores": len(job.get("filas_error", [])) > 0
    }


# ── GET /ingresos/historial ───────────────────────────────────────────────────
@router.get("/historial")
async def get_historial_ingresos(
    fecha_desde: str = "",
    fecha_hasta: str = "",
    tipo: str = "",
    current_user=Depends(get_current_user),
):
    query: dict = {}
    if fecha_desde or fecha_hasta:
        query["fecha"] = {}
        if fecha_desde:
            query["fecha"]["$gte"] = fecha_desde
        if fecha_hasta:
            query["fecha"]["$lte"] = fecha_hasta
    if tipo:
        query["tipo_ingreso"] = tipo

    registros = await db.ingresos_registrados.find(query, {"_id": 0}).sort("fecha", -1).to_list(500)
    total = sum(r.get("monto", 0) for r in registros)
    return {
        "registros": registros,
        "total_registros": len(registros),
        "monto_total": total,
    }


# ── POST /ingresos/registrar-manual ──────────────────────────────────────────
class IngresManualReq(BaseModel):
    fecha: str
    tipo_ingreso: str
    descripcion: str
    monto: float
    tercero: str
    banco: str = "Bancolombia"
    referencia: str = ""


@router.post("/registrar-manual")
async def registrar_ingreso_manual(
    req: IngresManualReq,
    current_user=Depends(get_current_user),
):
    """Registra un ingreso individual directamente (sin CSV) y crea el journal en Alegra."""
    plan_entry = _resolve_plan_ingreso(req.tipo_ingreso)
    if not plan_entry:
        raise HTTPException(status_code=400, detail=f"Tipo '{req.tipo_ingreso}' no válido. Válidos: {[e['tipo_ingreso'] for e in PLAN_INGRESOS_RODDOS]}")
    if req.monto <= 0:
        raise HTTPException(status_code=400, detail="Monto debe ser positivo")

    banco_id = _resolve_banco_id(req.banco)

    # Anti-duplicado: verificar si ya existe
    existing = await db.ingresos_registrados.find_one({
        "fecha": req.fecha, "monto": req.monto, "tercero": req.tercero, "tipo_ingreso": plan_entry["tipo_ingreso"]
    })
    if existing:
        return {"ok": False, "error": "Este ingreso ya fue registrado previamente (anti-duplicado)", "existing_id": existing.get("alegra_id")}

    alegra = AlegraService(db)
    payload = {
        "date":         req.fecha,
        "observations": f"{req.descripcion or plan_entry['tipo_ingreso']} — {req.tercero}",
        "entries": [
            {"id": banco_id,                    "debit": round(req.monto), "credit": 0},
            {"id": plan_entry["alegra_id"],      "debit": 0, "credit": round(req.monto)},
        ],
    }
    result = await alegra.request("journals", "POST", payload)
    if not isinstance(result, dict) or not result.get("id"):
        raise HTTPException(status_code=502, detail=f"Alegra no creó el journal: {result}")

    alegra_id = str(result["id"])
    now = datetime.now(timezone.utc).isoformat()

    doc = {
        "fecha":            req.fecha,
        "tipo_ingreso":     plan_entry["tipo_ingreso"],
        "descripcion":      req.descripcion,
        "monto":            req.monto,
        "tercero":          req.tercero,
        "banco":            req.banco,
        "referencia":       req.referencia,
        "cuenta_credito_id":   plan_entry["alegra_id"],
        "cuenta_credito_nombre": plan_entry["cuenta_nombre"],
        "banco_debito_id":  banco_id,
        "alegra_id":        alegra_id,
        "creado_por":       current_user.get("email", ""),
        "timestamp":        now,
    }
    await db.ingresos_registrados.insert_one({**doc})

    await db.roddos_events.insert_one({
        "event_type": "ingreso.manual.registrado",
        "alegra_id":  alegra_id,
        "monto":      req.monto,
        "tipo":       plan_entry["tipo_ingreso"],
        "tercero":    req.tercero,
        "creado_por": current_user.get("email", ""),
        "fecha":      now,
    })

    return {"ok": True, "alegra_id": alegra_id, "mensaje": f"Ingreso registrado en Alegra (journal #{alegra_id})"}
