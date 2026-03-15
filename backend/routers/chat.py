"""Chat router — AI agent messaging and action execution."""
import logging
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Optional, List

from ai_chat import process_chat, execute_chat_action
from database import db
from dependencies import get_current_user
from models import ChatMessageRequest

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/message")
async def chat_message(req: ChatMessageRequest, current_user=Depends(get_current_user)):
    try:
        return await process_chat(
            req.session_id, req.message, db, current_user,
            file_content=req.file_content,
            file_name=req.file_name,
            file_type=req.file_type,
        )
    except Exception as e:
        logger.error(f"Chat error for user {current_user.get('email')}: {e}")
        raise HTTPException(
            status_code=503,
            detail="El asistente IA no está disponible momentáneamente. Por favor intenta de nuevo en unos segundos.",
        )


class ExecuteActionRequest(BaseModel):
    action: str
    payload: dict


@router.post("/execute-action")
async def chat_execute_action(req: ExecuteActionRequest, current_user=Depends(get_current_user)):
    try:
        return await execute_chat_action(req.action, req.payload, db, current_user)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Execute action error [{req.action}]: {e}")
        raise HTTPException(status_code=500, detail=f"Error ejecutando la acción: {str(e)}")


@router.get("/history/{session_id}")
async def chat_history(session_id: str, current_user=Depends(get_current_user)):
    msgs = await db.chat_messages.find(
        {"session_id": session_id}, {"_id": 0}
    ).sort("timestamp", 1).to_list(100)
    return msgs


@router.delete("/history/{session_id}")
async def clear_chat(session_id: str, current_user=Depends(get_current_user)):
    await db.chat_messages.delete_many({"session_id": session_id})
    return {"message": "Historial eliminado"}


# ── MEJORA 2: Endpoints de Tarea Activa ───────────────────────────────────────

class TareaActivaRequest(BaseModel):
    descripcion: str
    pasos_total: int
    pasos_pendientes: List[str]
    datos_contexto: Optional[dict] = {}


@router.post("/tarea")
async def crear_tarea_activa(req: TareaActivaRequest, current_user=Depends(get_current_user)):
    """Crea o reemplaza la tarea activa en agent_memory."""
    now = datetime.now(timezone.utc).isoformat()
    # Close any existing en_curso task
    await db.agent_memory.update_many(
        {"tipo": "tarea_activa", "estado": "en_curso"},
        {"$set": {"estado": "reemplazada", "updated_at": now}},
    )
    doc = {
        "id": str(uuid.uuid4()),
        "tipo": "tarea_activa",
        "descripcion": req.descripcion,
        "pasos_total": req.pasos_total,
        "pasos_completados": 0,
        "pasos_pendientes": req.pasos_pendientes,
        "datos_contexto": req.datos_contexto,
        "iniciada": now,
        "ultimo_avance": now,
        "estado": "en_curso",
        "creado_por": current_user.get("email", ""),
    }
    await db.agent_memory.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.get("/tarea")
async def get_tarea_activa(current_user=Depends(get_current_user)):
    """Retorna la tarea activa actual (en_curso o pausada)."""
    tarea = await db.agent_memory.find_one(
        {"tipo": "tarea_activa", "estado": {"$in": ["en_curso", "pausada"]}},
        {"_id": 0},
    )
    return tarea or {"estado": "ninguna"}


@router.patch("/tarea/avance")
async def avanzar_tarea(
    pasos_completados: Optional[int] = None,
    paso_completado: Optional[str] = None,
    accion: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    """Actualiza la tarea activa.
    - accion='pausar': pausa la tarea en_curso
    - accion='continuar': reanuda la tarea pausada
    - pasos_completados (int): avanza el progreso (comportamiento original sin cambios)
    """
    now = datetime.now(timezone.utc).isoformat()

    if accion == "pausar":
        result = await db.agent_memory.update_one(
            {"tipo": "tarea_activa", "estado": "en_curso"},
            {"$set": {"estado": "pausada", "ultimo_avance": now}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="No hay tarea activa en curso")
        return {"ok": True, "estado": "pausada"}

    if accion == "continuar":
        result = await db.agent_memory.update_one(
            {"tipo": "tarea_activa", "estado": "pausada"},
            {"$set": {"estado": "en_curso", "ultimo_avance": now}},
        )
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="No hay tarea pausada para reanudar")
        return {"ok": True, "estado": "en_curso"}

    # Comportamiento original: avanzar pasos_completados
    if pasos_completados is None:
        raise HTTPException(status_code=400, detail="Se requiere pasos_completados o accion=pausar|continuar")

    tarea = await db.agent_memory.find_one(
        {"tipo": "tarea_activa", "estado": "en_curso"}, {"_id": 0}
    )
    if not tarea:
        raise HTTPException(status_code=404, detail="No hay tarea activa en curso")

    updates: dict = {"pasos_completados": pasos_completados, "ultimo_avance": now}
    pendientes = tarea.get("pasos_pendientes", [])
    if paso_completado and paso_completado in pendientes:
        pendientes.remove(paso_completado)
        updates["pasos_pendientes"] = pendientes

    if pasos_completados >= tarea.get("pasos_total", 0):
        updates["estado"] = "completada"

    await db.agent_memory.update_one(
        {"tipo": "tarea_activa", "estado": "en_curso"},
        {"$set": updates},
    )
    return {"ok": True, "completada": updates.get("estado") == "completada"}
