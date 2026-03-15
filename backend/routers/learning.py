"""learning.py — GET /api/crm/{loanbook_id}/learning

Retorna la recomendación de contacto y la alerta de deterioro predictivo
para el cliente de un loanbook_id dado.
"""
from fastapi import APIRouter, Depends, HTTPException
from dependencies import get_current_user
from database import db
from services.learning_engine import get_recomendacion_contacto, get_alerta_deterioro

router = APIRouter(prefix="/crm", tags=["learning"])


@router.get("/{loanbook_id}/learning")
async def get_learning(loanbook_id: str, current_user=Depends(get_current_user)):
    """Recomendación de contacto + alerta predictiva para un cliente."""
    loan = await db.loanbook.find_one({"id": loanbook_id}, {"_id": 0, "id": 1})
    if not loan:
        raise HTTPException(status_code=404, detail="Loanbook no encontrado")

    recomendacion = await get_recomendacion_contacto(db, loanbook_id)
    alerta_deterioro = await get_alerta_deterioro(db, loanbook_id)

    return {
        "loanbook_id":      loanbook_id,
        "recomendacion":    recomendacion,
        "alerta_deterioro": alerta_deterioro,
    }
