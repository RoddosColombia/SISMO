"""Budget router — presupuesto CRUD."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import db
from dependencies import get_current_user, require_admin

router = APIRouter(prefix="/presupuesto", tags=["budget"])


class PresupuestoItem(BaseModel):
    mes: str
    ano: int
    categoria: str
    concepto: str
    valor_presupuestado: float
    cuenta_alegra_id: Optional[str] = None
    cuenta_alegra_nombre: Optional[str] = None


@router.get("")
async def get_presupuesto(ano: int = 2025, current_user=Depends(get_current_user)):
    items = await db.presupuesto.find({"ano": ano}, {"_id": 0}).sort("mes", 1).to_list(500)
    return items


@router.post("")
async def save_presupuesto(items: List[PresupuestoItem], current_user=Depends(get_current_user)):
    for item in items:
        d = item.model_dump()
        d["updated_at"] = datetime.now(timezone.utc).isoformat()
        d["updated_by"] = current_user.get("email")
        existing = await db.presupuesto.find_one(
            {"mes": item.mes, "ano": item.ano, "concepto": item.concepto}, {"_id": 0, "id": 1}
        )
        if not existing:
            d["id"] = str(uuid.uuid4())
        await db.presupuesto.update_one(
            {"mes": item.mes, "ano": item.ano, "concepto": item.concepto},
            {"$set": d},
            upsert=True,
        )
    return {"message": f"{len(items)} ítems guardados"}


@router.delete("/{item_id}")
async def delete_presupuesto_item(item_id: str, current_user=Depends(require_admin)):
    await db.presupuesto.delete_one({"id": item_id})
    return {"message": "Ítem eliminado"}
