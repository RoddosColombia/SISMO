"""Chat router — AI agent messaging and action execution."""
import logging
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from ai_chat import process_chat, execute_chat_action
from database import db
from dependencies import get_current_user
from models import ChatMessageRequest

router = APIRouter(prefix="/chat", tags=["chat"])
logger = logging.getLogger(__name__)


@router.post("/message")
async def chat_message(req: ChatMessageRequest, current_user=Depends(get_current_user)):
    try:
        return await process_chat(req.session_id, req.message, db, current_user)
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
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


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
