"""cfo.py — RODDOS Agente CFO: semáforo financiero, informes, plan de acción."""
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
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


# ── GET /semaforo ─────────────────────────────────────────────────────────────
@router.get("/semaforo")
async def get_semaforo(current_user=Depends(get_current_user)):
    """Semáforo financiero en tiempo real (5 dimensiones)."""
    datos = await consolidar_datos_financieros(db)
    return await generar_semaforo(datos)


# ── GET /pyg ──────────────────────────────────────────────────────────────────
@router.get("/pyg")
async def get_pyg(current_user=Depends(get_current_user)):
    """P&G del mes: ingresos, costos, margen, gastos, resultado."""
    datos = await consolidar_datos_financieros(db)
    pyg = await analizar_pyg(datos)
    # Attach periodo
    pyg["periodo"] = datos.get("periodo", "")
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


# ── POST /generar ─────────────────────────────────────────────────────────────
@router.post("/generar")
async def generar_informe(current_user=Depends(get_current_user)):
    """Genera un informe CFO completo con análisis IA. Puede tomar 10-20 s."""
    try:
        return await generar_informe_cfo(db, triggered_by=current_user.get("email", "manual"))
    except Exception as e:
        logger.error(f"[CFO] /generar error: {e}")
        raise HTTPException(status_code=500, detail=f"Error generando informe: {str(e)}")


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
