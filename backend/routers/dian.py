"""
dian.py — BUILD 19: Router DIAN — consulta y causación automática de facturas.
"""
import os
import uuid
from datetime import datetime, timezone, date, timedelta

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import db
from dependencies import get_current_user
from services.dian_service import (
    consultar_facturas_dian, sync_facturas_dian,
    ya_fue_procesada, DIAN_MODO,
)

router = APIRouter(prefix="/dian", tags=["dian"])


@router.get("/status")
async def dian_status(current_user=Depends(get_current_user)):
    """Estado de la integración DIAN + último sync."""
    ultimo_sync = await db.roddos_events.find_one(
        {"event_type": "dian.sync.completado"},
        {"_id": 0},
        sort=[("timestamp", -1)],
    )
    total_causadas = await db.dian_facturas_procesadas.count_documents({})
    hoy = date.today()
    proximo_sync = datetime(hoy.year, hoy.month, hoy.day, 23, 0, 0).isoformat()

    dian_token = os.environ.get("DIAN_TOKEN", "")
    credenciales_configuradas = bool(dian_token)

    return {
        "modo": DIAN_MODO,
        "credenciales_configuradas": credenciales_configuradas,
        "ambiente": os.environ.get("DIAN_AMBIENTE", "habilitacion"),
        "nit_empresa": os.environ.get("DIAN_NIT", "9010126221"),
        "activo": True,
        "total_causadas": total_causadas,
        "ultimo_sync": ultimo_sync,
        "proximo_sync": proximo_sync,
    }


class SyncRequest(BaseModel):
    fecha_desde: str | None = None
    fecha_hasta: str | None = None


@router.post("/sync")
async def dian_sync_manual(req: SyncRequest = None, current_user=Depends(get_current_user)):
    """Ejecuta un sync manual de facturas DIAN."""
    hoy = date.today()
    inicio_mes = date(hoy.year, hoy.month, 1)
    f_desde = (req.fecha_desde if req and req.fecha_desde else inicio_mes.isoformat())
    f_hasta = (req.fecha_hasta if req and req.fecha_hasta else hoy.isoformat())

    resumen = await sync_facturas_dian(f_desde, f_hasta, db)
    return resumen


@router.get("/historial")
async def dian_historial(current_user=Depends(get_current_user)):
    """Historial de syncs de los últimos 30 días."""
    syncs = await db.roddos_events.find(
        {"event_type": "dian.sync.completado"},
        {"_id": 0},
        sort=[("timestamp", -1)],
    ).limit(30).to_list(30)
    return syncs


@router.get("/facturas")
async def dian_facturas(
    page: int = 1,
    per_page: int = 20,
    current_user=Depends(get_current_user),
):
    """Lista de facturas ya causadas en Alegra desde DIAN."""
    skip = (page - 1) * per_page
    total = await db.dian_facturas_procesadas.count_documents({})
    items = await db.dian_facturas_procesadas.find(
        {},
        {"_id": 0},
        sort=[("fecha_causacion", -1)],
    ).skip(skip).limit(per_page).to_list(per_page)
    return {"total": total, "page": page, "per_page": per_page, "items": items}


@router.post("/probar-conexion")
async def dian_probar_conexion(current_user=Depends(get_current_user)):
    """Prueba la conexión con DIAN (en modo simulación siempre retorna OK)."""
    if DIAN_MODO == "simulacion":
        return {
            "ok": True,
            "modo": "simulacion",
            "mensaje": "Modo simulación activo — conexión real pendiente de credenciales.",
            "proveedores_simulados": 4,
        }
    token = os.environ.get("DIAN_TOKEN", "")
    if not token:
        return {"ok": False, "mensaje": "DIAN_TOKEN no configurado"}
    return {"ok": True, "modo": "produccion", "mensaje": "Credenciales configuradas"}
