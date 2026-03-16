"""cfo.py — RODDOS Agente CFO: semáforo financiero, informes, plan de acción."""
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from database import db
from dependencies import get_current_user
from services.cfo_agent import (
    consolidar_datos_financieros,
    analizar_pyg,
    analizar_cartera,
    generar_semaforo,
    generar_informe_cfo,
)

router = APIRouter(prefix="/cfo", tags=["cfo"])
logger = logging.getLogger(__name__)


# ── Cache helper ─────────────────────────────────────────────────────────────

_CFO_CACHE_TTL = 300  # 5 minutes in seconds


async def _get_cache(key: str):
    """Return cached value if still valid, else None."""
    doc = await db.cfo_cache.find_one({"key": key}, {"_id": 0})
    if not doc:
        return None
    expires_at = doc.get("expires_at")
    if expires_at and datetime.fromisoformat(expires_at) > datetime.now(timezone.utc):
        return doc.get("value")
    return None


async def _set_cache(key: str, value: dict, ttl: int = _CFO_CACHE_TTL):
    """Upsert a cache entry with TTL."""
    expires_at = datetime.now(timezone.utc).replace(microsecond=0)
    from datetime import timedelta
    expires_at = expires_at.replace(second=0) + timedelta(seconds=ttl)
    await db.cfo_cache.update_one(
        {"key": key},
        {"$set": {"key": key, "value": value, "expires_at": expires_at.isoformat()}},
        upsert=True,
    )


# ── GET /semaforo ─────────────────────────────────────────────────────────────
@router.get("/semaforo")
async def get_semaforo(current_user=Depends(get_current_user)):
    """Semáforo financiero — cached 5 min (calls Alegra + Claude, ~30s cold)."""
    cached = await _get_cache("semaforo")
    if cached:
        return cached
    datos = await consolidar_datos_financieros(db)
    result = await generar_semaforo(datos)
    out = {k: v for k, v in result.items() if k != "metricas"}
    await _set_cache("semaforo", out)
    return out


# ── GET /pyg ──────────────────────────────────────────────────────────────────
@router.get("/pyg")
async def get_pyg(current_user=Depends(get_current_user)):
    """P&G del mes — cached 5 min (calls Alegra 3x, ~30s cold)."""
    cached = await _get_cache("pyg")
    if cached:
        return cached
    datos = await consolidar_datos_financieros(db)
    pyg = await analizar_pyg(datos)
    pyg["periodo"] = datos.get("periodo", "")
    await _set_cache("pyg", pyg)
    return pyg


# ── GET /informe-mensual ──────────────────────────────────────────────────────
@router.get("/informe-mensual")
async def get_informe_mensual(current_user=Depends(get_current_user)):
    """Último informe CFO guardado en la BD."""
    informe = await db.cfo_informes.find_one(
        {}, {"_id": 0}, sort=[("fecha_generacion", -1)]
    )
    if not informe:
        return {"mensaje": "Sin informes aún. Usa el botón 'Generar Informe CFO'."}
    return informe


# ── GET /informes ─────────────────────────────────────────────────────────────
@router.get("/informes")
async def get_informes(current_user=Depends(get_current_user)):
    """Últimos 6 informes CFO (resumen, sin analisis_ia completo)."""
    docs = await db.cfo_informes.find(
        {}, {"_id": 0, "id": 1, "periodo": 1, "fecha_generacion": 1,
             "semaforo": 1, "generado_por": 1}
    ).sort("fecha_generacion", -1).to_list(6)
    return docs


# ── Background task helper ────────────────────────────────────────────────────

async def _generar_informe_background(job_id: str, triggered_by: str):
    """Ejecuta la generación del informe CFO y actualiza el estado del job en cfo_jobs."""
    try:
        await db.cfo_jobs.update_one(
            {"id": job_id},
            {"$set": {"estado": "en_proceso", "iniciado_en": datetime.now(timezone.utc).isoformat()}},
        )
        informe = await generar_informe_cfo(db, triggered_by=triggered_by)
        await db.cfo_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "estado": "completado",
                "completado_en": datetime.now(timezone.utc).isoformat(),
                "informe_id": informe.get("id", ""),
            }},
        )
        logger.info("[CFO] Job %s completado — informe %s", job_id, informe.get("id"))
        # Invalidar cache tras nuevo informe
        await db.cfo_cache.delete_many({"key": {"$in": ["semaforo", "pyg"]}})
    except Exception as exc:
        logger.error("[CFO] Job %s falló: %s", job_id, exc)
        await db.cfo_jobs.update_one(
            {"id": job_id},
            {"$set": {
                "estado": "error",
                "error": str(exc)[:500],
                "completado_en": datetime.now(timezone.utc).isoformat(),
            }},
        )


# ── POST /generar ─────────────────────────────────────────────────────────────
@router.post("/generar")
async def generar_informe(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Dispara la generación asíncrona del informe CFO. Retorna job_id para polling."""
    job_id = str(uuid.uuid4())
    triggered_by = current_user.get("email", "manual")
    now = datetime.now(timezone.utc).isoformat()

    await db.cfo_jobs.insert_one({
        "id": job_id,
        "estado": "pendiente",
        "triggered_by": triggered_by,
        "created_at": now,
        "iniciado_en": None,
        "completado_en": None,
        "informe_id": None,
        "error": None,
    })

    background_tasks.add_task(_generar_informe_background, job_id, triggered_by)
    return {"job_id": job_id, "estado": "pendiente"}


# ── GET /status/{job_id} ──────────────────────────────────────────────────────
@router.get("/status/{job_id}")
async def get_job_status(job_id: str, current_user=Depends(get_current_user)):
    """Polling endpoint para conocer el estado de un job de generación de informe CFO."""
    job = await db.cfo_jobs.find_one({"id": job_id}, {"_id": 0})
    if not job:
        raise HTTPException(status_code=404, detail="Job no encontrado")
    return job


# ── GET /plan-accion ──────────────────────────────────────────────────────────
@router.get("/plan-accion")
async def get_plan_accion(current_user=Depends(get_current_user)):
    """Plan de acción del último informe CFO."""
    informe = await db.cfo_informes.find_one(
        {},
        {"_id": 0, "plan_acciones": 1, "periodo": 1, "fecha_generacion": 1},
        sort=[("fecha_generacion", -1)],
    )
    if not informe:
        return {"plan_acciones": [], "mensaje": "Sin informes aún."}
    return informe


# ── PATCH /plan-accion/{informe_id}/{idx} ─────────────────────────────────────
class PlanAccionUpdate(BaseModel):
    estado: str  # "pendiente" | "en_proceso" | "completado"


@router.patch("/plan-accion/{informe_id}/{item_idx}")
async def update_plan_accion(
    informe_id: str,
    item_idx: int,
    body: PlanAccionUpdate,
    current_user=Depends(get_current_user),
):
    """Actualiza el estado de un ítem del plan de acción."""
    informe = await db.cfo_informes.find_one({"id": informe_id})
    if not informe:
        raise HTTPException(status_code=404, detail="Informe no encontrado")
    plan = informe.get("plan_acciones", [])
    if item_idx < 0 or item_idx >= len(plan):
        raise HTTPException(status_code=400, detail="Índice fuera de rango")
    plan[item_idx]["estado"] = body.estado
    await db.cfo_informes.update_one(
        {"id": informe_id}, {"$set": {"plan_acciones": plan}}
    )
    return {"ok": True}


# ── GET /alertas ──────────────────────────────────────────────────────────────
@router.get("/alertas")
async def get_alertas(current_user=Depends(get_current_user)):
    """Alertas CFO activas ordenadas por urgencia DESC."""
    alertas = await db.cfo_alertas.find(
        {"resuelta": False}, {"_id": 0}
    ).sort("urgencia", -1).to_list(100)
    return alertas


# ── POST /alertas/{alerta_id}/resolver ───────────────────────────────────────
@router.post("/alertas/{alerta_id}/resolver")
async def resolver_alerta(alerta_id: str, current_user=Depends(get_current_user)):
    """Marca una alerta CFO como resuelta."""
    await db.cfo_alertas.update_one(
        {"id": alerta_id},
        {"$set": {"resuelta": True, "resuelta_en": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True}


# ── GET /config ───────────────────────────────────────────────────────────────
@router.get("/config")
async def get_config(current_user=Depends(get_current_user)):
    """Configuración CFO guardada."""
    cfg = await db.cfo_config.find_one({}, {"_id": 0})
    return cfg or {
        "dia_informe": 1,
        "umbral_mora_pct": 5.0,
        "umbral_caja_cop": 5_000_000,
        "whatsapp_activo": False,
        "whatsapp_ceo": "",
    }


# ── POST /config ──────────────────────────────────────────────────────────────
class CfoConfigRequest(BaseModel):
    dia_informe:     int   = 1
    umbral_mora_pct: float = 5.0
    umbral_caja_cop: float = 5_000_000
    whatsapp_activo: bool  = False
    whatsapp_ceo:    str   = ""


@router.post("/config")
async def save_config(req: CfoConfigRequest, current_user=Depends(get_current_user)):
    """Guarda la configuración CFO."""
    data = req.model_dump()
    data["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.cfo_config.update_one({}, {"$set": data}, upsert=True)
    return {"ok": True, "config": data}
