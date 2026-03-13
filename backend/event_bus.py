"""Event Bus — emits and stores events in roddos_events MongoDB collection."""
import uuid
from datetime import datetime, timezone

MODULES_FOR_EVENT: dict[str, list[str]] = {
    "factura.venta.creada":       ["inventario", "loanbook", "cartera", "dashboard"],
    "factura.venta.anulada":      ["inventario", "loanbook", "cartera", "dashboard"],
    "pago.cuota.registrado":      ["cartera", "loanbook", "dashboard"],
    "inventario.moto.entrada":    ["dashboard", "modulo_motos"],
    "inventario.moto.baja":       ["dashboard", "modulo_motos"],
    "cliente.mora.detectada":     ["cartera", "dashboard"],
    "asiento.contable.creado":    ["dashboard"],
    "agente_ia.accion.ejecutada": ["dashboard"],
    "factura.compra.creada":      ["inventario", "dashboard"],
    "repuesto.vendido":           ["inventario", "dashboard"],
}

EVENT_LABELS: dict[str, str] = {
    "factura.venta.creada":       "Factura de venta creada",
    "factura.venta.anulada":      "Factura de venta anulada",
    "pago.cuota.registrado":      "Pago de cuota registrado",
    "inventario.moto.entrada":    "Moto ingresada al inventario",
    "inventario.moto.baja":       "Moto dada de baja",
    "cliente.mora.detectada":     "Cliente en mora detectado",
    "asiento.contable.creado":    "Asiento contable creado",
    "agente_ia.accion.ejecutada": "Agente IA ejecutó acción",
    "factura.compra.creada":      "Factura de compra creada",
    "repuesto.vendido":           "Repuesto vendido",
}


async def emit_event(
    db,
    source: str,
    event_type: str,
    payload: dict,
    alegra_synced: bool = False,
) -> dict:
    """Persist event to roddos_events and return it."""
    modules = MODULES_FOR_EVENT.get(event_type, ["dashboard"])
    event = {
        "event_id": str(uuid.uuid4()),
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "event_type": event_type,
        "label": EVENT_LABELS.get(event_type, event_type),
        "payload": payload,
        "modules_to_notify": modules,
        "processed_by": [],
        "alegra_synced": alegra_synced,
        "estado": "pending",
    }
    await db.roddos_events.insert_one(event)
    event.pop("_id", None)
    return event


async def get_recent_events(db, limit: int = 15) -> list:
    events = await db.roddos_events.find({}, {"_id": 0}).sort("timestamp", -1).limit(limit).to_list(limit)
    return events
