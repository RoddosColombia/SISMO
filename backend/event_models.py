"""SISMO event models — RoddosEvent, DLQEvent, and EVENT_TYPES catalog.

Unifies both existing event patterns:
  - event_bus.py's emit_event() shape
  - shared_state.py's emit_state_change() shape

This is the typed foundation contract that Phase 2 (Event Bus) builds on.
Every event flowing through SISMO is validated by Python code before
reaching MongoDB or Alegra.
"""
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime, timezone
import uuid

# ── event type catalog ──

EventType = Literal[
    # Facturacion
    "factura.venta.creada",
    "factura.venta.anulada",
    "factura.compra.creada",
    # Pagos y cartera
    "pago.cuota.registrado",
    "cuota_pagada",
    "cliente.mora.detectada",
    "ptp.registrado",
    "protocolo_recuperacion",
    # Loanbook
    "loanbook.activado",
    "loanbook.creado",
    "loanbook.cerrado",
    "loanbook.bucket_change",
    # Inventario
    "inventario.moto.entrada",
    "inventario.moto.baja",
    "inventario.moto.actualizada",
    "repuesto.vendido",
    # Clientes
    "cliente.creado",
    "cliente.actualizado",
    # Contabilidad
    "asiento.contable.creado",
    "conciliacion.bancaria.ejecutada",
    "retencion.aplicada",
    "nomina.procesada",
    # Agentes IA y sistemas
    "agente_ia.accion.ejecutada",
    "cfo.reporte.generado",
    "portfolio.resumen.calculado",
    # WhatsApp
    "whatsapp.mensaje.enviado",
    "whatsapp.mensaje.recibido",
    # Sistema
    "sistema.health.check",
]

# Runtime iteration list (same 28 values)
EVENT_TYPES_LIST: list[str] = [
    "factura.venta.creada",
    "factura.venta.anulada",
    "factura.compra.creada",
    "pago.cuota.registrado",
    "cuota_pagada",
    "cliente.mora.detectada",
    "ptp.registrado",
    "protocolo_recuperacion",
    "loanbook.activado",
    "loanbook.creado",
    "loanbook.cerrado",
    "loanbook.bucket_change",
    "inventario.moto.entrada",
    "inventario.moto.baja",
    "inventario.moto.actualizada",
    "repuesto.vendido",
    "cliente.creado",
    "cliente.actualizado",
    "asiento.contable.creado",
    "conciliacion.bancaria.ejecutada",
    "retencion.aplicada",
    "nomina.procesada",
    "agente_ia.accion.ejecutada",
    "cfo.reporte.generado",
    "portfolio.resumen.calculado",
    "whatsapp.mensaje.enviado",
    "whatsapp.mensaje.recibido",
    "sistema.health.check",
]

# Spanish labels for UI display (migrated from event_bus.py + new types)
EVENT_LABELS: dict[str, str] = {
    "factura.venta.creada":           "Factura de venta creada",
    "factura.venta.anulada":          "Factura de venta anulada",
    "factura.compra.creada":          "Factura de compra creada",
    "pago.cuota.registrado":          "Pago de cuota registrado",
    "cuota_pagada":                   "Cuota pagada",
    "cliente.mora.detectada":         "Cliente en mora detectado",
    "ptp.registrado":                 "Promesa de pago registrada",
    "protocolo_recuperacion":         "Protocolo de recuperación iniciado",
    "loanbook.activado":              "Loanbook activado",
    "loanbook.creado":                "Loanbook creado",
    "loanbook.cerrado":               "Loanbook cerrado",
    "loanbook.bucket_change":         "Cambio de bucket en loanbook",
    "inventario.moto.entrada":        "Moto ingresada al inventario",
    "inventario.moto.baja":           "Moto dada de baja",
    "inventario.moto.actualizada":    "Moto actualizada en inventario",
    "repuesto.vendido":               "Repuesto vendido",
    "cliente.creado":                 "Cliente creado",
    "cliente.actualizado":            "Cliente actualizado",
    "asiento.contable.creado":        "Asiento contable creado",
    "conciliacion.bancaria.ejecutada": "Conciliación bancaria ejecutada",
    "retencion.aplicada":             "Retención aplicada",
    "nomina.procesada":               "Nómina procesada",
    "agente_ia.accion.ejecutada":     "Agente IA ejecutó acción",
    "cfo.reporte.generado":           "Reporte CFO generado",
    "portfolio.resumen.calculado":    "Resumen de portafolio calculado",
    "whatsapp.mensaje.enviado":       "Mensaje WhatsApp enviado",
    "whatsapp.mensaje.recibido":      "Mensaje WhatsApp recibido",
    "sistema.health.check":           "Health check del sistema",
}


# ── models ──

class RoddosEvent(BaseModel):
    """Canonical SISMO event — unifies emit_event and emit_state_change patterns.

    13 mandatory fields covering agent identity + full audit trail.
    event_type is validated against the EventType Literal catalog.
    """
    # Identity
    event_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    event_type: EventType  # Validated against 28-value Literal

    # Timing
    timestamp_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    # Agent identity (D-02: required for auditability)
    source_agent: str   # Agent that created the event (e.g. "contador", "cfo", "radar", "loanbook", "sistema")
    actor: str          # User or system identity (e.g. email or "scheduler")
    target_entity: str  # Entity ID affected (e.g. loanbook ID, invoice ID, "global")

    # Event data
    payload: dict = Field(default_factory=dict)
    modules_to_notify: list[str] = Field(default_factory=list)

    # Audit trail (D-02)
    correlation_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    version: int = 1
    alegra_synced: bool = False
    estado: str = "processed"  # Always "processed" per BUS-01 (no more "pending")
    label: str = ""

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "pago.cuota.registrado",
                    "timestamp_utc": "2026-03-26T10:00:00+00:00",
                    "source_agent": "contador",
                    "actor": "andres@roddos.co",
                    "target_entity": "LB-001",
                    "payload": {"monto": 150000, "metodo": "transferencia"},
                    "modules_to_notify": ["cartera", "loanbook", "dashboard"],
                    "correlation_id": "660e8400-e29b-41d4-a716-446655440001",
                    "version": 1,
                    "alegra_synced": False,
                    "estado": "processed",
                    "label": "Pago de cuota registrado",
                }
            ]
        }
    }

    def to_mongo(self) -> dict:
        """Serialize to MongoDB-compatible dict."""
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict | None) -> "RoddosEvent | None":
        """Deserialize from MongoDB document (strips _id)."""
        if doc is None:
            return None
        doc.pop("_id", None)
        return cls(**doc)


class DLQEvent(BaseModel):
    """Dead Letter Queue event — standalone model (no inheritance from RoddosEvent).

    Captures failed event processing with retry metadata.
    Per D-03: copies relevant RoddosEvent fields + adds retry_count, next_retry,
    error_message, failed_at.
    """
    # Copied from original RoddosEvent
    event_id: str          # Original event's ID
    event_type: EventType
    timestamp_utc: str
    source_agent: str
    payload: dict = Field(default_factory=dict)
    correlation_id: str = ""
    original_actor: str = ""

    # Retry metadata
    error_message: str
    failed_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    retry_count: int = 0
    next_retry: Optional[str] = None  # ISO datetime of next retry attempt

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "event_id": "550e8400-e29b-41d4-a716-446655440000",
                    "event_type": "pago.cuota.registrado",
                    "timestamp_utc": "2026-03-26T10:00:00+00:00",
                    "source_agent": "contador",
                    "payload": {"monto": 150000},
                    "correlation_id": "660e8400-e29b-41d4-a716-446655440001",
                    "original_actor": "andres@roddos.co",
                    "error_message": "MongoDB timeout after 30s",
                    "failed_at": "2026-03-26T10:00:05+00:00",
                    "retry_count": 1,
                    "next_retry": "2026-03-26T10:05:00+00:00",
                }
            ]
        }
    }

    def to_mongo(self) -> dict:
        """Serialize to MongoDB-compatible dict."""
        return self.model_dump()

    @classmethod
    def from_mongo(cls, doc: dict | None) -> "DLQEvent | None":
        """Deserialize from MongoDB document (strips _id)."""
        if doc is None:
            return None
        doc.pop("_id", None)
        return cls(**doc)
