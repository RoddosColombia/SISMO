"""Inventory router — Auteco motos (upload, CRUD, register in Alegra, sell)."""
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel

from alegra_service import AlegraService
from inventory_service import extract_motos_from_pdf, register_moto_in_alegra
from database import db
from dependencies import get_current_user, require_admin, log_action

router = APIRouter(prefix="/inventario", tags=["inventory"])


@router.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), current_user=Depends(get_current_user)):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Solo se admiten archivos PDF")
    content = await file.read()
    if len(content) > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="El archivo no puede superar 20MB")
    try:
        motos = await extract_motos_from_pdf(content, file.filename)
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))

    if not motos:
        raise HTTPException(status_code=422, detail="No se encontraron motos en el PDF")

    inserted = []
    for m in motos:
        chasis = m.get("chasis")
        if chasis:
            existing = await db.inventario_motos.find_one({"chasis": chasis}, {"_id": 0})
            if existing:
                continue
        await db.inventario_motos.insert_one({k: v for k, v in m.items()})
        inserted.append(m)

    await log_action(current_user, "/inventario/upload-pdf", "POST", {"filename": file.filename, "motos_found": len(motos)})
    return {"inserted": len(inserted), "total_found": len(motos), "motos": inserted}


@router.get("/motos")
async def get_inventario(
    estado: Optional[str] = None,
    marca: Optional[str] = None,
    current_user=Depends(get_current_user),
):
    query = {}
    if estado:
        query["estado"] = estado
    if marca:
        query["marca"] = {"$regex": marca, "$options": "i"}
    motos = await db.inventario_motos.find(query, {"_id": 0}).sort("created_at", -1).to_list(500)
    return motos


@router.get("/stats")
async def get_inventario_stats(current_user=Depends(get_current_user)):
    total = await db.inventario_motos.count_documents({})
    disponibles      = await db.inventario_motos.count_documents({"estado": "Disponible"})
    vendidas         = await db.inventario_motos.count_documents({"estado": "Vendida"})
    entregadas       = await db.inventario_motos.count_documents({"estado": "Entregada"})
    pendiente_datos  = await db.inventario_motos.count_documents({"estado": "Pendiente datos"})
    pipeline = [{"$group": {"_id": None, "total_inversion": {"$sum": "$total"}, "total_costo": {"$sum": "$costo"}}}]
    agg = await db.inventario_motos.aggregate(pipeline).to_list(1)
    totals = agg[0] if agg else {"total_inversion": 0, "total_costo": 0}
    return {
        "total": total,
        "disponibles": disponibles,
        "vendidas": vendidas,
        "entregadas": entregadas,
        "pendiente_datos": pendiente_datos,
        "total_inversion": totals.get("total_inversion", 0),
        "total_costo": totals.get("total_costo", 0),
    }


@router.put("/motos/{moto_id}")
async def update_moto(moto_id: str, body: dict, current_user=Depends(get_current_user)):
    body.pop("_id", None)
    body.pop("id", None)
    result = await db.inventario_motos.update_one({"id": moto_id}, {"$set": body})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    updated = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    return updated


@router.delete("/motos/{moto_id}")
async def delete_moto(moto_id: str, current_user=Depends(require_admin)):
    result = await db.inventario_motos.delete_one({"id": moto_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    return {"message": "Moto eliminada"}


@router.post("/motos/{moto_id}/register-alegra")
async def register_in_alegra(moto_id: str, current_user=Depends(get_current_user)):
    moto = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    if not moto:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    if moto.get("alegra_item_id"):
        raise HTTPException(status_code=400, detail="Esta moto ya está registrada en Alegra")
    service = AlegraService(db)
    result = await register_moto_in_alegra(moto, service)
    alegra_id = result.get("id")
    await db.inventario_motos.update_one({"id": moto_id}, {"$set": {"alegra_item_id": alegra_id}})
    await log_action(current_user, f"/inventario/motos/{moto_id}/register-alegra", "POST", {"alegra_id": alegra_id})
    return {"alegra_item_id": alegra_id, "result": result}


class VentaMotoRequest(BaseModel):
    cliente_id: str
    cliente_nombre: str
    precio_venta: float
    tipo_pago: str = "contado"
    cuotas: int = 1
    valor_cuota: Optional[float] = None
    include_iva: bool = True
    ipoc_pct: float = 8.0


@router.post("/motos/{moto_id}/vender")
async def vender_moto(moto_id: str, req: VentaMotoRequest, current_user=Depends(get_current_user)):
    moto = await db.inventario_motos.find_one({"id": moto_id}, {"_id": 0})
    if not moto:
        raise HTTPException(status_code=404, detail="Moto no encontrada")
    if moto.get("estado") != "Disponible":
        raise HTTPException(status_code=400, detail=f"Moto no disponible (estado: {moto.get('estado')})")

    service = AlegraService(db)

    items = [{
        "description": f"{moto.get('marca')} {moto.get('version')} — Chasis: {moto.get('chasis')} Motor: {moto.get('motor')}",
        "quantity": 1,
        "price": req.precio_venta,
        "account": {"id": "4105"},
    }]
    if req.include_iva:
        items[0]["tax"] = [{"percentage": 19}]

    invoice_payload = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "dueDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "client": {"id": req.cliente_id},
        "items": items,
        "observations": f"Venta moto {moto.get('marca')} {moto.get('version')} — {req.tipo_pago}",
    }

    result = await service.request("invoices", "POST", invoice_payload)
    invoice_id = result.get("id")
    invoice_number = (
        result.get("numberTemplate", {}).get("fullNumber")
        or result.get("number")
        or str(invoice_id)
    )

    sale_data = {
        "estado": "Vendida",
        "cliente_id": req.cliente_id,
        "cliente_nombre": req.cliente_nombre,
        "precio_venta": req.precio_venta,
        "tipo_pago": req.tipo_pago,
        "cuotas": req.cuotas,
        "valor_cuota": req.valor_cuota,
        "factura_id": invoice_id,
        "factura_numero": invoice_number,
        "fecha_venta": datetime.now(timezone.utc).isoformat(),
        "vendido_por": current_user.get("email"),
    }
    await db.inventario_motos.update_one({"id": moto_id}, {"$set": sale_data})

    if moto.get("alegra_item_id"):
        try:
            await service.request(f"items/{moto['alegra_item_id']}", "PUT", {"status": "inactive"})
        except Exception:
            pass

    await log_action(
        current_user, f"/inventario/motos/{moto_id}/vender", "POST",
        {"invoice_number": invoice_number, "cliente": req.cliente_nombre},
    )

    return {
        "success": True,
        "invoice_id": invoice_id,
        "invoice_number": invoice_number,
        "message": f"Moto vendida — Factura {invoice_number} creada en Alegra",
        "moto": {**moto, **sale_data},
    }
