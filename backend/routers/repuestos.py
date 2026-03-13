"""Repuestos router — spare parts inventory (units + kits) + billing with Alegra."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from alegra_service import AlegraService
from database import db
from dependencies import get_current_user, require_admin, log_action

router = APIRouter(prefix="/repuestos", tags=["repuestos"])

# ─── Models ───────────────────────────────────────────────────────────────────

class ComponenteKit(BaseModel):
    repuesto_id: str
    referencia: str
    descripcion: str
    cantidad: int = 1

class RepuestoCreate(BaseModel):
    referencia: str
    descripcion: str
    marca: Optional[str] = ""
    modelos_compatibles: Optional[List[str]] = []
    tipo: str = "unidad"  # "unidad" | "kit"
    componentes: Optional[List[ComponenteKit]] = []
    precio_costo: float = 0
    precio_venta: float = 0
    stock: int = 0
    stock_minimo: int = 5
    unidad_medida: str = "und"

class AjusteStockRequest(BaseModel):
    cantidad: int   # positive = entrada, negative = salida
    motivo: str = ""

class FacturaRepuestoItem(BaseModel):
    repuesto_id: str
    referencia: str
    descripcion: str
    tipo: str = "unidad"
    cantidad: int = 1
    precio_unitario: float
    descuento_pct: float = 0
    iva_pct: float = 19.0

class FacturaRepuestoCreate(BaseModel):
    cliente_id: str
    cliente_nombre: str
    cliente_nit: Optional[str] = ""
    items: List[FacturaRepuestoItem]
    notas: Optional[str] = ""


# ─── Catalog CRUD ─────────────────────────────────────────────────────────────

@router.get("/catalogo")
async def get_catalogo(tipo: Optional[str] = None, current_user=Depends(get_current_user)):
    query = {}
    if tipo:
        query["tipo"] = tipo
    items = await db.repuestos_catalogo.find(query, {"_id": 0}).sort("referencia", 1).to_list(1000)
    # Enrich kits with virtual stock = min(component_stock / component_qty)
    for item in items:
        if item.get("tipo") == "kit" and item.get("componentes"):
            stocks = []
            for comp in item["componentes"]:
                c = await db.repuestos_catalogo.find_one({"id": comp["repuesto_id"]}, {"_id": 0, "stock": 1})
                if c:
                    qty = comp.get("cantidad", 1)
                    stocks.append(c["stock"] // qty)
            item["stock_virtual"] = min(stocks) if stocks else 0
    return items


@router.post("/catalogo")
async def create_repuesto(req: RepuestoCreate, current_user=Depends(get_current_user)):
    # Check unique referencia
    existing = await db.repuestos_catalogo.find_one({"referencia": req.referencia})
    if existing:
        raise HTTPException(status_code=400, detail=f"La referencia '{req.referencia}' ya existe")
    doc = req.model_dump()
    doc["id"] = str(uuid.uuid4())
    doc["alegra_item_id"] = None
    doc["activo"] = True
    doc["created_at"] = datetime.now(timezone.utc).isoformat()
    doc["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.repuestos_catalogo.insert_one(doc)
    doc.pop("_id", None)
    return doc


@router.put("/catalogo/{repuesto_id}")
async def update_repuesto(repuesto_id: str, body: dict, current_user=Depends(get_current_user)):
    body.pop("_id", None)
    body.pop("id", None)
    body["updated_at"] = datetime.now(timezone.utc).isoformat()
    result = await db.repuestos_catalogo.update_one({"id": repuesto_id}, {"$set": body})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    updated = await db.repuestos_catalogo.find_one({"id": repuesto_id}, {"_id": 0})
    return updated


@router.delete("/catalogo/{repuesto_id}")
async def delete_repuesto(repuesto_id: str, current_user=Depends(require_admin)):
    result = await db.repuestos_catalogo.delete_one({"id": repuesto_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    return {"message": "Repuesto eliminado"}


@router.post("/catalogo/{repuesto_id}/ajuste-stock")
async def ajustar_stock(repuesto_id: str, req: AjusteStockRequest, current_user=Depends(get_current_user)):
    rep = await db.repuestos_catalogo.find_one({"id": repuesto_id}, {"_id": 0})
    if not rep:
        raise HTTPException(status_code=404, detail="Repuesto no encontrado")
    if rep.get("tipo") == "kit":
        raise HTTPException(status_code=400, detail="El stock de un kit es calculado automáticamente a partir de sus componentes")
    nuevo_stock = rep["stock"] + req.cantidad
    if nuevo_stock < 0:
        raise HTTPException(status_code=400, detail=f"Stock insuficiente. Disponible: {rep['stock']}")
    await db.repuestos_catalogo.update_one(
        {"id": repuesto_id},
        {"$set": {"stock": nuevo_stock, "updated_at": datetime.now(timezone.utc).isoformat()}},
    )
    # Record movement
    await db.repuestos_movimientos.insert_one({
        "id": str(uuid.uuid4()),
        "repuesto_id": repuesto_id,
        "referencia": rep["referencia"],
        "cantidad": req.cantidad,
        "stock_anterior": rep["stock"],
        "stock_nuevo": nuevo_stock,
        "motivo": req.motivo,
        "usuario": current_user.get("email"),
        "fecha": datetime.now(timezone.utc).isoformat(),
    })
    return {"stock": nuevo_stock, "message": f"Stock actualizado a {nuevo_stock} {rep.get('unidad_medida','und')}"}


@router.get("/stats")
async def get_stats(current_user=Depends(get_current_user)):
    total = await db.repuestos_catalogo.count_documents({"activo": True})
    unidades = await db.repuestos_catalogo.count_documents({"activo": True, "tipo": "unidad"})
    kits = await db.repuestos_catalogo.count_documents({"activo": True, "tipo": "kit"})
    # Stock alerts
    low_stock = await db.repuestos_catalogo.count_documents(
        {"activo": True, "tipo": "unidad", "$expr": {"$lte": ["$stock", "$stock_minimo"]}}
    )
    facturas = await db.repuestos_facturas.count_documents({"estado": {"$ne": "anulada"}})
    return {
        "total_productos": total,
        "unidades": unidades,
        "kits": kits,
        "alertas_stock": low_stock,
        "facturas_emitidas": facturas,
    }


# ─── Facturación ──────────────────────────────────────────────────────────────

@router.get("/facturas")
async def get_facturas(current_user=Depends(get_current_user)):
    items = await db.repuestos_facturas.find({}, {"_id": 0}).sort("created_at", -1).to_list(500)
    return items


@router.post("/facturas")
async def create_factura(req: FacturaRepuestoCreate, current_user=Depends(get_current_user)):
    # 1. Validate and compute totals
    items_detalle = []
    total_subtotal = 0.0
    total_iva = 0.0
    total_descuento = 0.0

    for it in req.items:
        rep = await db.repuestos_catalogo.find_one({"id": it.repuesto_id}, {"_id": 0})
        if not rep:
            raise HTTPException(status_code=404, detail=f"Repuesto {it.referencia} no encontrado")

        # Stock check
        if rep["tipo"] == "unidad":
            if rep["stock"] < it.cantidad:
                raise HTTPException(status_code=400, detail=f"Stock insuficiente para {it.referencia}. Disponible: {rep['stock']}")
        elif rep["tipo"] == "kit":
            for comp in (rep.get("componentes") or []):
                c = await db.repuestos_catalogo.find_one({"id": comp["repuesto_id"]}, {"_id": 0, "stock": 1})
                if not c or c["stock"] < comp["cantidad"] * it.cantidad:
                    raise HTTPException(status_code=400, detail=f"Stock insuficiente para componente {comp['referencia']} del kit {it.referencia}")

        subtotal = it.precio_unitario * it.cantidad
        descuento = subtotal * (it.descuento_pct / 100)
        base_iva = subtotal - descuento
        iva = base_iva * (it.iva_pct / 100)
        total_line = base_iva + iva

        total_subtotal += base_iva
        total_iva += iva
        total_descuento += descuento
        items_detalle.append({**it.model_dump(), "subtotal_base": base_iva, "iva": iva, "total_line": total_line})

    total = total_subtotal + total_iva

    # 2. Create invoice in Alegra
    service = AlegraService(db)
    alegra_items = []
    for it in req.items:
        rep = await db.repuestos_catalogo.find_one({"id": it.repuesto_id}, {"_id": 0})
        alegra_item = {}
        if rep.get("alegra_item_id"):
            alegra_item["id"] = rep["alegra_item_id"]
        alegra_item_payload = {
            "description": it.descripcion,
            "quantity": it.cantidad,
            "price": it.precio_unitario,
            "discount": it.descuento_pct,
        }
        if it.iva_pct > 0:
            alegra_item_payload["tax"] = [{"percentage": it.iva_pct}]
        if rep.get("alegra_item_id"):
            alegra_item_payload["id"] = rep["alegra_item_id"]
        alegra_items.append(alegra_item_payload)

    alegra_payload = {
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "dueDate": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "client": {"id": req.cliente_id},
        "items": alegra_items,
        "observations": req.notas or f"Venta repuestos — {req.cliente_nombre}",
    }

    try:
        alegra_result = await service.request("invoices", "POST", alegra_payload)
        alegra_invoice_id = alegra_result.get("id")
        numero = alegra_result.get("numberTemplate", {}).get("fullNumber") or str(alegra_invoice_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Error creando factura en Alegra: {str(e)}")

    # 3. Deduct stock
    for it in req.items:
        rep = await db.repuestos_catalogo.find_one({"id": it.repuesto_id}, {"_id": 0})
        if rep["tipo"] == "unidad":
            await db.repuestos_catalogo.update_one(
                {"id": it.repuesto_id},
                {"$inc": {"stock": -it.cantidad}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
            )
        elif rep["tipo"] == "kit":
            for comp in (rep.get("componentes") or []):
                await db.repuestos_catalogo.update_one(
                    {"id": comp["repuesto_id"]},
                    {"$inc": {"stock": -(comp["cantidad"] * it.cantidad)}, "$set": {"updated_at": datetime.now(timezone.utc).isoformat()}},
                )

    # 4. Save invoice in MongoDB
    factura_doc = {
        "id": str(uuid.uuid4()),
        "numero": numero,
        "fecha": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "cliente_id": req.cliente_id,
        "cliente_nombre": req.cliente_nombre,
        "cliente_nit": req.cliente_nit,
        "items": items_detalle,
        "subtotal": total_subtotal,
        "descuento": total_descuento,
        "iva": total_iva,
        "total": total,
        "estado": "emitida",
        "alegra_invoice_id": str(alegra_invoice_id),
        "notas": req.notas,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "creado_por": current_user.get("email"),
    }
    await db.repuestos_facturas.insert_one(factura_doc)
    factura_doc.pop("_id", None)
    await log_action(current_user, "/repuestos/facturas", "POST", {"numero": numero, "total": total})
    return factura_doc


@router.post("/facturas/{factura_id}/anular")
async def anular_factura(factura_id: str, current_user=Depends(require_admin)):
    fac = await db.repuestos_facturas.find_one({"id": factura_id}, {"_id": 0})
    if not fac:
        raise HTTPException(status_code=404, detail="Factura no encontrada")
    if fac.get("estado") == "anulada":
        raise HTTPException(status_code=400, detail="La factura ya está anulada")

    # Restore stock
    for it in fac.get("items", []):
        rep = await db.repuestos_catalogo.find_one({"id": it["repuesto_id"]}, {"_id": 0})
        if rep and rep["tipo"] == "unidad":
            await db.repuestos_catalogo.update_one({"id": it["repuesto_id"]}, {"$inc": {"stock": it["cantidad"]}})
        elif rep and rep["tipo"] == "kit":
            for comp in (rep.get("componentes") or []):
                await db.repuestos_catalogo.update_one(
                    {"id": comp["repuesto_id"]}, {"$inc": {"stock": comp["cantidad"] * it["cantidad"]}}
                )

    # Void in Alegra
    service = AlegraService(db)
    try:
        await service.request(f"invoices/{fac['alegra_invoice_id']}/void", "POST")
    except Exception:
        pass

    await db.repuestos_facturas.update_one({"id": factura_id}, {"$set": {"estado": "anulada"}})
    return {"message": "Factura anulada y stock restaurado"}
