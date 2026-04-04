"""contabilidad_pendientes.py — Gestión de movimientos contables ambigua/pendientes.

Endpoints:
  GET  /api/contabilidad_pendientes/listado          — Obtener movimientos pendientes
  GET  /api/contabilidad_pendientes/{movimiento_id}  — Detalles de un movimiento
  POST /api/contabilidad_pendientes/{movimiento_id}/confirmar — Confirmar clasificación
  POST /api/contabilidad_pendientes/{movimiento_id}/resolver — Marcar como resuelto
  POST /api/contabilidad_pendientes/webhook/mercately — Webhook de Mercately (público)
  GET  /api/contabilidad_pendientes/estadisticas     — Resumen de pendientes
"""

import hashlib
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


# ══════════════════════════════════════════════════════════════════════════════
# BACKLOG DE MOVIMIENTOS — Nuevos endpoints (prefijo /backlog/)
# Para movimientos de baja confianza del motor matricial
# ══════════════════════════════════════════════════════════════════════════════

class BacklogMovimientoRequest(BaseModel):
    banco: str                              # "bbva" | "bancolombia" | "nequi" | "davivienda"
    extracto: str                           # "bbva_enero_2026"
    fecha: str                              # "2026-01-15"
    descripcion: str
    monto: float                            # negativo=egreso, positivo=ingreso
    tipo: str                               # "EGRESO" | "INGRESO"
    confianza_motor: float = 0.0
    cuenta_sugerida: Optional[int] = None
    razon_baja_confianza: str = ""


class CausarMovimientoRequest(BaseModel):
    cuenta_debito: int
    cuenta_credito: int
    observaciones: str = ""


class DescartarMovimientoRequest(BaseModel):
    razon: str


@router.post("/backlog/crear")
async def backlog_crear(
    payload: BacklogMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Crea movimiento en backlog con anti-dup por hash(banco+fecha+descripcion+monto)."""
    dup_key = f"{payload.banco}|{payload.fecha}|{payload.descripcion}|{payload.monto}"
    dup_hash = hashlib.md5(dup_key.encode()).hexdigest()

    existing = await db.contabilidad_pendientes.find_one({"backlog_hash": dup_hash})
    if existing:
        raise HTTPException(status_code=409, detail="Movimiento ya existe en backlog (anti-dup)")

    doc = {
        "backlog_hash": dup_hash,
        "banco": payload.banco,
        "extracto": payload.extracto,
        "fecha": payload.fecha,
        "descripcion": payload.descripcion,
        "monto": payload.monto,
        "tipo": payload.tipo,
        "confianza_motor": payload.confianza_motor,
        "cuenta_sugerida": payload.cuenta_sugerida,
        "razon_baja_confianza": payload.razon_baja_confianza,
        "estado": "pendiente",
        "journal_alegra_id": None,
        "resuelto_por": None,
        "creado_at": datetime.now(timezone.utc).isoformat(),
        "resuelto_at": None,
    }
    result = await db.contabilidad_pendientes.insert_one(doc)
    return {"success": True, "id": str(result.inserted_id)}


@router.get("/backlog/listado")
async def backlog_listado(
    banco: Optional[str] = Query(None),
    mes: Optional[str] = Query(None),   # YYYY-MM
    estado: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    current_user=Depends(get_current_user),
):
    """Lista movimientos de backlog con filtros: banco, mes, estado. Paginación 20/página."""
    query: dict = {"backlog_hash": {"$exists": True}}
    if banco:
        query["banco"] = banco.lower()
    if estado:
        query["estado"] = estado
    if mes:
        query["fecha"] = {"$regex": f"^{mes}"}

    skip = (page - 1) * 20
    docs = await db.contabilidad_pendientes.find(
        query, {"_id": 0}
    ).skip(skip).limit(20).to_list(20)

    total = await db.contabilidad_pendientes.count_documents(query)
    return {"total": total, "page": page, "items": docs}


@router.patch("/backlog/{id}/causar")
async def backlog_causar(
    id: str,
    payload: CausarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Crea journal en Alegra y marca movimiento como causado."""
    from bson import ObjectId
    from services.alegra_service import AlegraService

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    mov = await db.contabilidad_pendientes.find_one({"_id": oid})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")
    if mov.get("estado") != "pendiente":
        raise HTTPException(status_code=400, detail=f"Movimiento en estado '{mov.get('estado')}', no se puede causar")

    service = AlegraService(db)
    monto = abs(mov.get("monto", 0))
    journal_payload = {
        "date": mov.get("fecha", datetime.now(timezone.utc).isoformat()[:10]),
        "observations": payload.observaciones or mov.get("descripcion", ""),
        "entries": [
            {"id": payload.cuenta_debito, "debit": monto, "credit": 0},
            {"id": payload.cuenta_credito, "debit": 0, "credit": monto},
        ],
    }

    try:
        result = await service.request_with_verify("journals", "POST", journal_payload)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creando journal en Alegra: {str(e)}")

    if not result.get("_verificado"):
        raise HTTPException(status_code=500, detail="Journal creado pero no verificado en Alegra")

    journal_id = result.get("id")
    await db.contabilidad_pendientes.update_one(
        {"_id": oid},
        {"$set": {
            "estado": "causado",
            "journal_alegra_id": str(journal_id),
            "resuelto_por": current_user.get("email", ""),
            "resuelto_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "journal_alegra_id": str(journal_id), "estado": "causado"}


@router.patch("/backlog/{id}/descartar")
async def backlog_descartar(
    id: str,
    payload: DescartarMovimientoRequest,
    current_user=Depends(get_current_user),
):
    """Marca movimiento como descartado."""
    from bson import ObjectId

    try:
        oid = ObjectId(id)
    except Exception:
        raise HTTPException(status_code=400, detail="ID inválido")

    mov = await db.contabilidad_pendientes.find_one({"_id": oid})
    if not mov:
        raise HTTPException(status_code=404, detail="Movimiento no encontrado")

    await db.contabilidad_pendientes.update_one(
        {"_id": oid},
        {"$set": {
            "estado": "descartado",
            "razon_descarte": payload.razon,
            "resuelto_por": current_user.get("email", ""),
            "resuelto_at": datetime.now(timezone.utc).isoformat(),
        }}
    )
    return {"success": True, "estado": "descartado"}


@router.get("/backlog/stats")
async def backlog_stats(current_user=Depends(get_current_user)):
    """Retorna totales por estado y por banco."""
    # Incluye tanto documentos nuevos (backlog_hash) como schema viejo (pendiente_whatsapp)
    base_query = {"$or": [
        {"backlog_hash": {"$exists": True}},
        {"estado": "pendiente_whatsapp"},
    ]}

    total_pendientes = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": {"$in": ["pendiente", "pendiente_whatsapp"]}}
    )
    total_causados = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": "causado"}
    )
    total_descartados = await db.contabilidad_pendientes.count_documents(
        {**{"$or": base_query["$or"]}, "estado": "descartado"}
    )

    por_banco: dict = {}
    for banco in ["bbva", "bancolombia", "nequi", "davivienda"]:
        por_banco[banco] = await db.contabilidad_pendientes.count_documents(
            {"banco": banco, "estado": {"$in": ["pendiente", "pendiente_whatsapp"]}}
        )

    return {
        "total_pendientes": total_pendientes,
        "total_causados": total_causados,
        "total_descartados": total_descartados,
        "por_banco": por_banco,
    }


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
