---
phase: 01-models-contracts
plan: "01"
subsystem: event-models
tags: [pydantic, event-bus, models, contracts, typed]
dependency_graph:
  requires: []
  provides: [RoddosEvent, DLQEvent, EventType, EVENT_TYPES_LIST, EVENT_LABELS]
  affects: [event_bus.py, shared_state.py, Phase 2 Event Bus]
tech_stack:
  added: []
  patterns: [Pydantic BaseModel, Literal type, to_mongo/from_mongo convention]
key_files:
  created:
    - backend/event_models.py
  modified: []
decisions:
  - "EventType implemented as Literal (not StrEnum) — direct Pydantic integration, no .value needed (D-06)"
  - "DLQEvent is standalone BaseModel, no inheritance from RoddosEvent (D-03)"
  - "28 event types: 15 existing from event_bus.py+shared_state.py consolidated, 13 gap types added for real operational coverage"
  - "estado always set to 'processed' in RoddosEvent defaults — eliminates 'pending' state per BUS-01"
  - "File placed at backend/event_models.py to avoid naming conflict with existing backend/models.py"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-03-26"
  tasks_completed: 2
  files_created: 1
  files_modified: 0
---

# Phase 01 Plan 01: Event Models & TYPE Catalog Summary

**One-liner:** Pydantic event contracts with 28-type Literal catalog, 13-field RoddosEvent, and standalone DLQEvent with retry metadata.

## What Was Built

`backend/event_models.py` (245 lines) is the typed foundation for all events in SISMO. It consolidates two previously separate event patterns (event_bus.py's `emit_event` and shared_state.py's `emit_state_change`) into a single Pydantic model that Phase 2 (Event Bus) will build on.

### EventType Catalog (28 types)

Consolidated from existing sources (~15 unique types) plus 13 operational gap types:

| # | Type | Source |
|---|------|--------|
| 1-10 | factura.venta.creada, factura.venta.anulada, factura.compra.creada, pago.cuota.registrado, cuota_pagada, cliente.mora.detectada, ptp.registrado, protocolo_recuperacion, loanbook.activado, loanbook.bucket_change | Existing (event_bus.py + shared_state.py) |
| 11-15 | inventario.moto.entrada, inventario.moto.baja, repuesto.vendido, asiento.contable.creado, agente_ia.accion.ejecutada | Existing (event_bus.py) |
| 16-28 | loanbook.creado, loanbook.cerrado, inventario.moto.actualizada, cliente.creado, cliente.actualizado, conciliacion.bancaria.ejecutada, retencion.aplicada, nomina.procesada, cfo.reporte.generado, portfolio.resumen.calculado, whatsapp.mensaje.enviado, whatsapp.mensaje.recibido, sistema.health.check | New gap types |

### RoddosEvent (13 fields)

```
event_id, event_type, timestamp_utc,          # identity + timing
source_agent, actor, target_entity,            # agent identity (D-02)
payload, modules_to_notify,                   # event data
correlation_id, version, alegra_synced,       # audit trail (D-02)
estado, label                                 # status + display
```

### DLQEvent (11 fields, standalone)

Copies 6 fields from RoddosEvent + adds: `error_message`, `failed_at`, `retry_count`, `next_retry`, `original_actor`.

## Verification Results

```
Valid event: f6fa1698... type=pago.cuota.registrado
Correctly rejected invalid type: ValidationError
Correctly rejected missing fields: ValidationError
DLQ event: retry_count=0, error=timeout
EVENT_TYPES_LIST has 28 types
DLQEvent is standalone (no inheritance)
EVENT_LABELS has 28 entries
to_mongo/from_mongo round-trip OK
models.py is untouched
ALL CHECKS PASSED
```

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| Task 1+2 | 90ebc6d | feat(01-01): create RoddosEvent, DLQEvent, and EVENT_TYPES catalog |

## Deviations from Plan

### Auto-consolidation: Tasks 1 and 2 merged

The plan noted "Task 1 is conceptual scaffolding" and explicitly stated both tasks produce the same `backend/event_models.py` file. Both tasks were executed as a single implementation pass — this matches the plan's own guidance.

No other deviations.

## Known Stubs

None — all exported symbols are fully implemented with real validation logic.

## Self-Check: PASSED

- `backend/event_models.py` exists: FOUND
- Commit 90ebc6d exists: FOUND
- `backend/models.py` untouched: CONFIRMED
- `len(EVENT_TYPES_LIST) == 28`: CONFIRMED
- `RoddosEvent` field count == 13: CONFIRMED
- `DLQEvent` not inheriting from `RoddosEvent`: CONFIRMED
