"""Proveedores Config — gestión de autoretenedores y configuración por proveedor."""
import re
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from database import db
from dependencies import get_current_user

router = APIRouter(prefix="/proveedores", tags=["proveedores"])


class ProveedorConfigIn(BaseModel):
    nombre: str
    nit: Optional[str] = None
    es_autoretenedor: bool = False
    tipo_retencion: str = "compras_2.5"
    notas: Optional[str] = None


@router.get("/config")
async def get_proveedores_config(user=Depends(get_current_user)):
    docs = await db.proveedores_config.find({}, {"_id": 0}).sort("nombre", 1).to_list(500)
    return {"proveedores": docs, "total": len(docs)}


@router.post("/config")
async def save_proveedor_config(body: ProveedorConfigIn, user=Depends(get_current_user)):
    doc = body.model_dump()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_by"] = user.get("email")
    await db.proveedores_config.update_one(
        {"nombre": {"$regex": f"^{re.escape(body.nombre)}$", "$options": "i"}},
        {"$set": doc},
        upsert=True,
    )
    return {"ok": True, "proveedor": body.nombre, "es_autoretenedor": body.es_autoretenedor}


@router.get("/config/{nombre}")
async def get_proveedor_by_name(nombre: str, user=Depends(get_current_user)):
    doc = await db.proveedores_config.find_one(
        {"nombre": {"$regex": f"^{re.escape(nombre)}$", "$options": "i"}}, {"_id": 0}
    )
    if not doc:
        return {"found": False}
    return {"found": True, **doc}
