"""Chat router — AI agent messaging and action execution."""
import logging
import traceback
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


async def _log_agent_error(error_type: str, error_message: str, tb: str, user_message: str, fase: str):
    """Registra errores del agente en MongoDB para diagnóstico posterior."""
    try:
        await db.agent_errors.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "error_type": error_type,
            "error_message": error_message,
            "stack_trace": tb,
            "user_message": user_message[:500] if user_message else "",
            "fase": fase,
            "resuelto": False,
        })
    except Exception:
        pass  # logging never breaks the flow


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
        tb = traceback.format_exc()
        logger.error(f"Chat error for user {current_user.get('email')}: {e}\n{tb}")
        await _log_agent_error(
            error_type=type(e).__name__,
            error_message=str(e),
            tb=tb,
            user_message=req.message or "",
            fase="process_chat",
        )
        # Provide a descriptive error instead of the generic one
        err_detail = str(e)
        if "anthropic" in err_detail.lower() or "litellm" in err_detail.lower() or "llm" in err_detail.lower():
            detail = f"Error en la API de IA: {err_detail}. Intenta de nuevo en unos segundos."
        elif "mongo" in err_detail.lower() or "motor" in err_detail.lower():
            detail = f"Error de base de datos: {err_detail}."
        elif "alegra" in err_detail.lower():
            detail = f"Error al conectar con Alegra: {err_detail}."
        else:
            detail = f"Error inesperado: {err_detail}. Por favor reporta este mensaje al equipo técnico."
        raise HTTPException(status_code=503, detail=detail)


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


# ── BUILD 21 MODULE 4: Endpoints de Temas Pendientes ─────────────────────────

@router.get("/pendientes")
async def get_pendientes(current_user=Depends(get_current_user)):
    """Retorna los temas pendientes activos del usuario (TTL 72h).

    Usado por el badge en el header del chat.
    """
    from ai_chat import get_pending_topics
    user_id = current_user.get("id", "")
    if not user_id:
        return {"pendientes": []}
    topics = await get_pending_topics(db, user_id)
    return {"pendientes": topics, "total": len(topics)}


@router.post("/pendientes/{topic_key}/retomar")
async def retomar_pendiente(topic_key: str, current_user=Depends(get_current_user)):
    """Inyecta el tema pendiente como contexto en la próxima sesión del agente.

    Retorna el contexto del tema para que el frontend lo use como mensaje inicial.
    """
    user_id = current_user.get("id", "")
    topic = await db.agent_pending_topics.find_one(
        {"user_id": user_id, "topic_key": topic_key, "estado": "pendiente"},
        {"_id": 0},
    )
    if not topic:
        raise HTTPException(status_code=404, detail="Tema pendiente no encontrado")

    # Mark as in_progress (being retaken)
    await db.agent_pending_topics.update_one(
        {"user_id": user_id, "topic_key": topic_key},
        {"$set": {"estado": "retomando", "retomado_en": datetime.now(timezone.utc).isoformat()}},
    )
    return {
        "topic_key": topic_key,
        "descripcion": topic.get("descripcion", ""),
        "datos_contexto": topic.get("datos_contexto", {}),
        "mensaje_inicial": f"Retomando el tema pendiente: {topic.get('descripcion','')}. ¿Continuamos?",
    }


@router.delete("/pendientes/{topic_key}")
async def descartar_pendiente(topic_key: str, current_user=Depends(get_current_user)):
    """Descarta un tema pendiente individual (lo marca como descartado, no elimina)."""
    user_id = current_user.get("id", "")
    await db.agent_pending_topics.update_one(
        {"user_id": user_id, "topic_key": topic_key},
        {"$set": {"estado": "descartado", "descartado_en": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "topic_key": topic_key}


@router.delete("/pendientes")
async def descartar_todos_pendientes(current_user=Depends(get_current_user)):
    """Descarta TODOS los temas pendientes del usuario."""
    user_id = current_user.get("id", "")
    result = await db.agent_pending_topics.update_many(
        {"user_id": user_id, "estado": "pendiente"},
        {"$set": {"estado": "descartado", "descartado_en": datetime.now(timezone.utc).isoformat()}},
    )
    return {"ok": True, "descartados": result.modified_count}


# ── ReAct Nivel 1: Aprobación / Cancelación de Planes Multi-Acción ────────────

class ApprovePlanRequest(BaseModel):
    plan_id: str
    session_id: str
    confirmed: bool


@router.post("/approve-plan")
async def approve_plan(
    req: ApprovePlanRequest,
    current_user=Depends(get_current_user),
):
    """
    Aprueba o cancela un plan multi-acción.

    - confirmed=True  → ejecuta el plan via execute_plan()
    - confirmed=False → cancela el plan via cancel_plan()

    Retorna el resultado con summary y alegra_ids como evidencia de ejecución.
    """
    from tool_executor import execute_plan, cancel_plan
    if not req.confirmed:
        result = await cancel_plan(req.plan_id, db)
        return result
    result = await execute_plan(req.plan_id, db, current_user)
    return result
