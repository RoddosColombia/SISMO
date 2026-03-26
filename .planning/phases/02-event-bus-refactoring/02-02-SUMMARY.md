---
phase: 02-event-bus-refactoring
plan: 02
subsystem: event-bus
tags: [refactor, event-bus, migration, shared-state]
dependency_graph:
  requires: [02-01]
  provides: [unified-event-bus, handle-state-side-effects]
  affects: [backend/routers/loanbook.py, backend/post_action_sync.py, backend/services/crm_service.py, backend/services/loanbook_scheduler.py, backend/routers/dashboard.py]
tech_stack:
  added: []
  patterns: [bus.emit(RoddosEvent(...)), handle_state_side_effects per D-03]
key_files:
  created: []
  modified:
    - backend/services/shared_state.py
    - backend/services/event_bus_service.py
    - backend/routers/loanbook.py
    - backend/post_action_sync.py
    - backend/services/crm_service.py
    - backend/services/loanbook_scheduler.py
    - backend/routers/dashboard.py
  deleted:
    - backend/event_bus.py
decisions:
  - "D-03: handle_state_side_effects() added to shared_state.py as the DB update + cache invalidation layer; callers do bus.emit() then handle_state_side_effects() separately"
  - "event_type mapping: retoma.registrada -> inventario.moto.actualizada; moto.entregada -> inventario.moto.entrada (not in EventType catalog)"
  - "get_recent_events() moved to EventBusService as a method; dashboard.py updated accordingly"
metrics:
  duration: ~25 minutes
  completed: 2026-03-26
  tasks_completed: 2
  files_modified: 7
  files_deleted: 1
requirements:
  - BUS-06
  - BUS-07
  - BUS-08
---

# Phase 02 Plan 02: Event Bus Caller Migration Summary

All 14 callers migrated from emit_event()/emit_state_change() to bus.emit(RoddosEvent(...)) + handle_state_side_effects(); event_bus.py deleted and emit_state_change removed from shared_state.py.

## What Was Done

### Task 1: Delete event_bus.py, refactor shared_state.py

- Added `get_recent_events()` method to `EventBusService` (required by dashboard.py — deviation Rule 2)
- Updated `backend/routers/dashboard.py` to import from `EventBusService` instead of `event_bus`
- Deleted `backend/event_bus.py` entirely via `git rm`
- Removed `emit_state_change()` function from `shared_state.py`
- Removed `_EVENT_LABELS` dict from `shared_state.py` (consolidated into `event_models.py`)
- Added `handle_state_side_effects()` to `shared_state.py` as the D-03 side-effect layer
- Removed unused `uuid` import from `shared_state.py`
- Updated module docstring

### Task 2: Migrate all 14 callers

**backend/routers/loanbook.py** (5 calls):
- Replaced top-level `from event_bus import emit_event` with EventBusService + RoddosEvent + handle_state_side_effects imports
- `retoma.registrada` → `inventario.moto.actualizada` (retoma not in EventType catalog)
- `loanbook.activado` → bus.emit + handle_state_side_effects (state update to "activo")
- `moto.entregada` → `inventario.moto.entrada` (moto.entregada not in EventType catalog)
- `pago.cuota.registrado` → bus.emit + handle_state_side_effects
- `ptp.registrado` (was emit_state_change lazy import at line ~1511) → bus.emit + handle_state_side_effects

**backend/post_action_sync.py** (5 calls):
- Replaced `from services.shared_state import emit_state_change` with new imports
- Caso 1 (`factura.venta.creada`) → bus.emit + handle_state_side_effects
- Caso 2 (`pago.cuota.registrado`) → bus.emit + handle_state_side_effects
- Caso 3 (`asiento.contable.creado`) → bus.emit + handle_state_side_effects
- Caso 4 (`factura.compra.creada`) → bus.emit + handle_state_side_effects
- Caso 6 (`loanbook.activado`) → bus.emit + handle_state_side_effects

**backend/services/crm_service.py** (1 call):
- Replaced `from services.shared_state import emit_state_change` with new imports
- `ptp.registrado` → bus.emit + handle_state_side_effects

**backend/services/loanbook_scheduler.py** (2 calls, lazy imports):
- Replaced lazy `from services.shared_state import emit_state_change` with lazy EventBusService + RoddosEvent + handle_state_side_effects imports
- `loanbook.bucket_change` → bus.emit + handle_state_side_effects
- `protocolo_recuperacion` → bus.emit + handle_state_side_effects

**Note on ai_chat.py:** The plan referenced a call at line ~4990. Inspection confirmed no emit_state_change or emit_event calls exist in this file — it was either pre-cleaned or never had such a call.

## Commits

| Hash | Message |
|------|---------|
| 4bba0cf | refactor(02-02): delete event_bus.py, add handle_state_side_effects to shared_state |
| 5c31646 | refactor(02-02): migrate all callers to bus.emit(RoddosEvent(...)) |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Critical Functionality] Moved get_recent_events to EventBusService**
- **Found during:** Task 1
- **Issue:** `dashboard.py` imports `get_recent_events` from `event_bus`. Deleting `event_bus.py` without providing this function elsewhere would break the dashboard events feed endpoint.
- **Fix:** Added `get_recent_events()` method to `EventBusService` in `event_bus_service.py`. Updated `dashboard.py` to instantiate `EventBusService` and call the method.
- **Files modified:** `backend/services/event_bus_service.py`, `backend/routers/dashboard.py`
- **Commit:** 4bba0cf

**2. [Rule 1 - Bug] Event type mapping corrections for loanbook.py**
- **Found during:** Task 2
- **Issue:** `"retoma.registrada"` and `"moto.entregada"` are not in the `EventType` Literal catalog in `event_models.py`. Using them would cause Pydantic validation errors at runtime.
- **Fix:** Mapped `retoma.registrada` → `inventario.moto.actualizada` and `moto.entregada` → `inventario.moto.entrada` per plan instructions.
- **Files modified:** `backend/routers/loanbook.py`
- **Commit:** 5c31646

**3. [Observation] ai_chat.py had no emit calls**
- The plan referenced 1 emit_state_change at line ~4990 in ai_chat.py. Inspection found no such call. Task completed without modifying ai_chat.py. Not a deviation — the codebase was already clean for this file.

## Known Stubs

None — all event calls are wired to real EventBusService.

## Verification Results

```
from event_bus import ... count: 0
emit_state_change in production code (non-comment): 0
event_bus.py exists: NO (deleted)
handle_state_side_effects defined: YES
bus.emit calls in loanbook.py: 5
bus.emit calls in post_action_sync.py: 5 (actual await calls)
bus.emit calls in crm_service.py: 1
bus.emit calls in loanbook_scheduler.py: 2
Python imports: OK
```

## Self-Check: PASSED

- `backend/event_bus.py` deleted: CONFIRMED
- `handle_state_side_effects` in shared_state.py: CONFIRMED (1 definition)
- `emit_state_change` removed from shared_state.py: CONFIRMED (0 definitions)
- `_EVENT_LABELS` removed from shared_state.py: CONFIRMED (0 occurrences)
- All 5 caller files have `bus.emit` calls: CONFIRMED
- Commits 4bba0cf and 5c31646 exist: CONFIRMED
