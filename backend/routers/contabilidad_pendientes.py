"""contabilidad_pendientes.py — Gestión de movimientos contables ambigua/pendientes.

Endpoints:
  GET  /api/contabilidad_pendientes/listado          — Obtener movimientos pendientes
  GET  /api/contabilidad_pendientes/{movimiento_id}  — Detalles de un movimiento
  POST /api/contabilidad_pendientes/{movimiento_id}/confirmar — Confirmar clasificación
  POST /api/contabilidad_pendientes/{movimiento_id}/resolver — Marcar como resuelto
  POST /api/contabilidad_pendientes/webhook/mercately — Webhook de Mercately (público)
  GET  /api/contabilidad_pendientes/estadisticas     — Resumen de pendientes
"""

import logging
from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, log_action
from services.accounting_engine import AmbiguousMovementHandler, EstadoResolucion

router = APIRouter(prefix="/contabilidad_pendientes", tags=["contabilidad_pendientes"])
logger = logging.getLogger(__name__)

handler = AmbiguousMovementHandler(db)


# ── Pydantic Models ────────────────────────────────────────────────────────────

class ConfirmarMovimientoRequest(BaseModel):
    cuenta_debito_final: int
    cuenta_credito_final: Optional[int] = None
    notas: str = ""


class ResolverMovimientoRequest(BaseModel):
    cuenta_debito_final: int
    cuenta_credito_final: Optional[int] = None
    notas: str = ""


class WebhookMercatelyRequest(BaseModel):
    movimiento_id: str
    respuesta_usuario: str
    telefono_usuario: str
    conversation_id: Optional[str] = None


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/listado")
async def listar_pendientes(
    estado: Optional[str] = Query(None),
    limite: int = Query(50, ge=1, le=200),
    current_user=Depends(get_current_user),
):
    """Obtiene lista de movimientos pendientes con filtros opcionales."""
    filtro_estado = None
    if estado:
        try:
            filtro_estado = EstadoResolucion[estado.upper()]
        except KeyError:
            raise HTTPException(status_code=400, detail=f"Estado inválido: {estado}")

    movimientos = await handler.obtener_pendientes(estado=filtro_estado)
    movimientos_paginated = movimientos[:limite]

    return {
        "total": len(movimientos),
        "mostrados": len(movimientos_paginated),
        "movimientos": movimientos_paginated,
    }


@router.get("/{movimiento_id}")
async def obtener_movimiento(
    movimiento_id: str,
    current_user=Depends(get_current_user),
):
    """Obtiene detalles completos de un movimiento pendiente."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    return movimiento


@router.post("/{movimiento_id}/confirmar")
async def confirmar_movimiento(
    movimiento_id: str,
    req: ConfirmarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Confirma la clasificación de un movimiento (por usuario)."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    success = await handler.marcar_resuelto(
        movimiento_id=movimiento_id,
        cuenta_debito_final=req.cuenta_debito_final,
        cuenta_credito_final=req.cuenta_credito_final,
        notas=f"Confirmado manualmente por usuario {current_user}: {req.notas}",
    )

    if not success:
        raise HTTPException(status_code=500, detail="No se pudo marcar como resuelto")

    await log_action(
        current_user,
        f"/contabilidad_pendientes/{movimiento_id}/confirmar",
        "POST",
        {"cuenta_debito": req.cuenta_debito_final, "cuenta_credito": req.cuenta_credito_final},
    )

    return {
        "ok": True,
        "mensaje": f"Movimiento {movimiento_id} confirmado y resuelto",
        "movimiento_id": movimiento_id,
    }


@router.post("/{movimiento_id}/resolver")
async def resolver_movimiento(
    movimiento_id: str,
    req: ResolverMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Marca un movimiento como resuelto después de ser enviado a Alegra."""
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if not movimiento:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    success = await handler.marcar_resuelto(
        movimiento_id=movimiento_id,
        cuenta_debito_final=req.cuenta_debito_final,
        cuenta_credito_final=req.cuenta_credito_final,
        notas=f"Resuelto por {current_user}: {req.notas}",
    )

    if not success:
        raise HTTPException(status_code=500, detail="No se pudo marcar como resuelto")

    await log_action(
        current_user,
        f"/contabilidad_pendientes/{movimiento_id}/resolver",
        "POST",
        {"cuenta_debito": req.cuenta_debito_final},
    )

    return {
        "ok": True,
        "mensaje": f"Movimiento {movimiento_id} resuelto y enviado a Alegra",
        "movimiento_id": movimiento_id,
    }


@router.post("/webhook/mercately")
async def webhook_mercately(req: WebhookMercatelyRequest):
    """
    Webhook público para recibir respuestas de Mercately WhatsApp.
    No requiere autenticación JWT.
    """
    try:
        success = await handler.procesar_respuesta_whatsapp(
            movimiento_id=req.movimiento_id,
            respuesta_usuario=req.respuesta_usuario,
            telefono_usuario=req.telefono_usuario,
        )

        if not success:
            logger.warning(f"Respuesta no procesada para {req.movimiento_id}: {req.respuesta_usuario}")

        return {
            "ok": True,
            "mensaje": f"Respuesta registrada para {req.movimiento_id}",
            "movimiento_id": req.movimiento_id,
        }

    except Exception as e:
        logger.error(f"Error en webhook Mercately: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando respuesta: {str(e)}")


@router.get("/estadisticas")
async def obtener_estadisticas(current_user=Depends(get_current_user)):
    """Obtiene resumen de movimientos pendientes por estado."""
    todos = await handler.obtener_pendientes()

    estadisticas = {
        "total_pendientes": len(todos),
        "pendiente": len([m for m in todos if m.get("estado") == "pendiente"]),
        "confirmada": len([m for m in todos if m.get("estado") == "confirmada"]),
        "rechazada": len([m for m in todos if m.get("estado") == "rechazada"]),
        "resuelta": len([m for m in todos if m.get("estado") == "resuelta"]),
        "abandonada": len([m for m in todos if m.get("estado") == "abandonada"]),
        "monto_total_pendiente": sum(m.get("monto", 0) for m in todos if m.get("estado") == "pendiente"),
        "dias_promedio_pendencia": _calcular_dias_promedio(todos),
    }

    return estadisticas


# ── Helpers ────────────────────────────────────────────────────────────────────

def _calcular_dias_promedio(movimientos: list) -> float:
    """Calcula días promedio de pendencia para movimientos aún sin resolver."""
    pendientes = [
        m for m in movimientos
        if m.get("estado") in ["pendiente", "confirmada", "rechazada"]
    ]

    if not pendientes:
        return 0.0

    ahora = datetime.now(timezone.utc)
    dias_totales = 0

    for m in pendientes:
        fecha_creacion_str = m.get("fecha_creacion")
        if fecha_creacion_str:
            try:
                fecha_creacion = datetime.fromisoformat(fecha_creacion_str)
                dias = (ahora - fecha_creacion).days
                dias_totales += dias
            except (ValueError, TypeError):
                continue

    return dias_totales / len(pendientes) if pendientes else 0.0
