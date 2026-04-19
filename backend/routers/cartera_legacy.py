"""
cartera_legacy.py — BUILD 0.1 — Cartera Legacy RODDOS (read-only)

Endpoints:
  GET /api/cartera-legacy         — lista paginada, filtros estado/aliado/en_mora
  GET /api/cartera-legacy/stats   — totales y distribución
  GET /api/cartera-legacy/{codigo} — detalle + historial pagos

Colección MongoDB: loanbook_legacy
Schema: ver LoanbookLegacyDoc (Pydantic inline)
"""
import logging
from datetime import datetime, timezone
from typing import Optional, List

from bson import ObjectId
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from database import db
from dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/cartera-legacy", tags=["cartera-legacy"])


# ── Pydantic schema (mirrors MongoDB document) ────────────────────────────────

class PagoRegistrado(BaseModel):
    fecha: Optional[str] = None
    monto: Optional[float] = None
    alegra_journal_id: Optional[str] = None
    backlog_movimiento_id: Optional[str] = None


class LoanbookLegacyDoc(BaseModel):
    codigo_sismo: str
    cedula: str
    numero_credito_original: str
    nombre_completo: str
    placa: Optional[str] = None
    aliado: str
    estado: str
    estado_legacy_excel: str
    saldo_actual: float
    saldo_inicial: float
    dias_mora_maxima: Optional[int] = None
    pct_on_time: Optional[float] = None
    score_total: Optional[float] = None
    decision_historica: Optional[str] = None
    analisis_texto: Optional[str] = None
    alegra_contact_id: Optional[str] = None
    fecha_importacion: Optional[datetime] = None
    pagos_recibidos: List[PagoRegistrado] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


def _clean(doc: dict) -> dict:
    """Remove MongoDB ObjectId and return JSON-safe dict."""
    doc.pop("_id", None)
    return doc


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/stats")
async def get_cartera_legacy_stats(
    current_user: dict = Depends(get_current_user),
):
    """Totales y distribución de cartera legacy."""
    pipeline = [
        {
            "$group": {
                "_id": None,
                "total_creditos": {"$sum": 1},
                "saldo_total": {"$sum": "$saldo_actual"},
                "saldo_inicial_total": {"$sum": "$saldo_inicial"},
                "activos": {"$sum": {"$cond": [{"$eq": ["$estado", "activo"]}, 1, 0]}},
                "saldados": {"$sum": {"$cond": [{"$eq": ["$estado", "saldado"]}, 1, 0]}},
                "castigados": {"$sum": {"$cond": [{"$eq": ["$estado", "castigado"]}, 1, 0]}},
                "en_mora": {"$sum": {"$cond": [{"$eq": ["$estado_legacy_excel", "En Mora"]}, 1, 0]}},
                "al_dia": {"$sum": {"$cond": [{"$eq": ["$estado_legacy_excel", "Al Día"]}, 1, 0]}},
            }
        }
    ]
    totales = {}
    async for doc in db.loanbook_legacy.aggregate(pipeline):
        doc.pop("_id", None)
        totales = doc

    # Distribución por aliado
    aliado_pipeline = [
        {"$group": {
            "_id": "$aliado",
            "count": {"$sum": 1},
            "saldo": {"$sum": "$saldo_actual"}
        }},
        {"$sort": {"saldo": -1}}
    ]
    por_aliado = []
    async for doc in db.loanbook_legacy.aggregate(aliado_pipeline):
        por_aliado.append({"aliado": doc["_id"], "count": doc["count"], "saldo": doc["saldo"]})

    return {
        "success": True,
        "data": {
            **totales,
            "por_aliado": por_aliado,
        }
    }


@router.get("")
async def list_cartera_legacy(
    estado: Optional[str] = Query(None, description="activo|saldado|castigado"),
    aliado: Optional[str] = Query(None),
    en_mora: Optional[bool] = Query(None, description="true=En Mora, false=Al Día"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    current_user: dict = Depends(get_current_user),
):
    """Lista paginada de créditos legacy con filtros."""
    filtro: dict = {}
    if estado:
        filtro["estado"] = estado
    if aliado:
        filtro["aliado"] = aliado
    if en_mora is not None:
        filtro["estado_legacy_excel"] = "En Mora" if en_mora else "Al Día"

    skip = (page - 1) * limit
    total = await db.loanbook_legacy.count_documents(filtro)

    cursor = (
        db.loanbook_legacy.find(filtro, {"pagos_recibidos": 0})
        .sort("saldo_actual", -1)
        .skip(skip)
        .limit(limit)
    )
    docs = [_clean(d) async for d in cursor]

    return {
        "success": True,
        "data": docs,
        "total": total,
        "page": page,
        "pages": (total + limit - 1) // limit,
    }


@router.get("/{codigo}")
async def get_cartera_legacy_detalle(
    codigo: str,
    current_user: dict = Depends(get_current_user),
):
    """Detalle de un crédito legacy con historial de pagos."""
    doc = await db.loanbook_legacy.find_one({"codigo_sismo": codigo})
    if not doc:
        raise HTTPException(status_code=404, detail=f"Crédito {codigo} no encontrado")
    return {"success": True, "data": _clean(doc)}
