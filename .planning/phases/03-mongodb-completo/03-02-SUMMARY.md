---
phase: 03-mongodb-completo
plan: "02"
subsystem: mongodb-cleanup
tags: [mongodb, server-startup, loanbook, gastos, refactor, seed-data]
dependency_graph:
  requires:
    - 03-01 (init_mongodb_sismo.py with catalogo_planes and plan_cuentas_roddos seeded)
  provides:
    - Clean server.py startup (no index creation, no seed data)
    - loanbook.py reads catalogo_planes from MongoDB only
    - gastos.py reads plan_cuentas_roddos from MongoDB only
    - ai_chat.py reads plan_cuentas_roddos from MongoDB only
  affects:
    - backend/server.py (startup reduced to scheduler + event bus init)
    - backend/routers/loanbook.py (get_catalogo_planes now pure read)
    - backend/routers/gastos.py (all plan_cuentas lookups via DB)
    - backend/ai_chat.py (plan_cuentas context from MongoDB)
tech_stack:
  added: []
  patterns:
    - "async helper pattern: _get_plan_cuentas_db() fetches from MongoDB"
    - "Function refactor: _lookup_plan_cuentas(list, cat, sub) receives list as param"
    - "404 error pattern for unseeded collections (init_mongodb_sismo.py dependency)"
key_files:
  created: []
  modified:
    - backend/server.py
    - backend/routers/loanbook.py
    - backend/routers/gastos.py
    - backend/ai_chat.py
decisions:
  - "reset_catalogo admin endpoint retains seed data as local variable _catalogo_seed (not module constant) — keeps emergency reset functional without a module-level CATALOGO_DEFAULT"
  - "_CATEGORIAS_VALIDAS converted to static list matching init_mongodb_sismo.py categories — avoids DB call at module import time"
  - "ai_chat.py plan_cuentas read wrapped in try/except for graceful fallback if collection not seeded"
  - "_lookup_plan_cuentas_local renamed to _lookup_plan_cuentas with list parameter — callers fetch from DB then pass list"
metrics:
  duration: "~12 minutes"
  completed: "2026-03-26T00:00:00Z"
  tasks_completed: 2
  tasks_total: 2
  files_modified: 4
---

# Phase 03 Plan 02: Remove Inline Seed Data and Index Creation Summary

**One-liner:** server.py startup stripped to scheduler init only (180 lines removed); loanbook.py and gastos.py now read catalogo_planes and plan_cuentas_roddos from MongoDB, completing D-01 and D-04 from Phase 03 context.

## What Was Built

Cleanup of three production files to eliminate duplicate index creation and inline seed data constants now managed by `init_mongodb_sismo.py`.

### server.py Changes

Removed from startup():
- User seed block (users + alegra_credentials insert_many/insert_one)
- catalogo_motos seed block
- 30+ create_index calls across 15+ collections
- proveedores_config AUTECO KAWASAKI seed
- IVA bimestral-to-cuatrimestral migration block
- plan_cuentas_roddos seed/upsert block (which imported from routers.gastos)
- `hash_password` import (no longer needed)

Kept in startup():
- `await run_migration_v24(db)` — runtime migration logic
- `start_scheduler()` and `start_loanbook_scheduler()`
- `app.state.event_bus = EventBusService(db)`
- Comment referencing init_mongodb_sismo.py as single source of truth

Net result: startup() reduced from ~190 lines to 10 lines.

### loanbook.py Changes

- Removed module-level `CATALOGO_DEFAULT` constant (4 plans, ~38 lines)
- `get_catalogo_planes` endpoint: removed upsert logic, now a clean read with 404 if not seeded
- `reset_catalogo` admin endpoint: seed data moved to local `_catalogo_seed` variable inside the function — emergency reset still works

### gastos.py Changes

- Removed module-level `PLAN_CUENTAS_RODDOS` constant (25 entries, ~36 lines)
- Added `async def _get_plan_cuentas_db()` helper reading from `plan_cuentas_roddos` collection
- Renamed `_lookup_plan_cuentas_local(cat, sub)` to `_lookup_plan_cuentas(plan_list, cat, sub)` — callers fetch from DB then pass the list
- `_CATEGORIAS_VALIDAS` converted to static list (computed from known category set, no DB call at import time)
- `descargar_plantilla_gastos`, `cargar_gastos_csv`, `get_plan_cuentas` all updated to fetch plan_cuentas from DB
- Duplicate call on line 452 (`entry_pj = _lookup_plan_cuentas_local(...)` called twice) fixed to single call

### ai_chat.py Changes

- Replaced `from routers.gastos import PLAN_CUENTAS_RODDOS` with direct MongoDB read via `db.plan_cuentas_roddos.find({"activo": True})`
- Wrapped in try/except for graceful degradation if collection not seeded

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Duplicate honorarios lookup call**
- **Found during:** Task 2 (reading gastos.py lines 451-452)
- **Issue:** `entry_pj = _lookup_plan_cuentas_local(...)` was called twice identically (line 451 and 452 both set `entry_pj` to the same value — the second call overwrote the first with the same result)
- **Fix:** Collapsed to a single call `entry_pj = _lookup_plan_cuentas(plan_cuentas, raw_categoria, "Honorarios_PJ")`
- **Files modified:** backend/routers/gastos.py

**2. [Rule 2 - Missing critical functionality] ai_chat.py import of removed constant**
- **Found during:** Task 2 (grep search for PLAN_CUENTAS_RODDOS references)
- **Issue:** ai_chat.py had `from routers.gastos import PLAN_CUENTAS_RODDOS` — would fail at runtime after constant removal
- **Fix:** Replaced with MongoDB read, wrapped in try/except
- **Files modified:** backend/ai_chat.py

## Known Stubs

None — all endpoints serve real data from MongoDB (requires init_mongodb_sismo.py to have been run).

## Self-Check

**Files exist:**
- backend/server.py: FOUND
- backend/routers/loanbook.py: FOUND
- backend/routers/gastos.py: FOUND
- backend/ai_chat.py: FOUND
- .planning/phases/03-mongodb-completo/03-02-SUMMARY.md: FOUND (this file)

**Commits:**
- 652dcb1: refactor(03-02): remove index creation and seed data from server.py startup
- c4f6b84: refactor(03-02): remove CATALOGO_DEFAULT and PLAN_CUENTAS_RODDOS inline constants

## Self-Check: PASSED
