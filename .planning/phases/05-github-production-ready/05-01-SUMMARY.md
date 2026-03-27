---
phase: 05-github-production-ready
plan: 01
subsystem: testing
tags: [pytest, smoke-test, fastapi, mongodb, event-bus, health-check]

# Dependency graph
requires:
  - phase: 04-agents-router-scheduler
    provides: EventBusService with get_bus_health(), catalogo_planes collection seeded
provides:
  - Enhanced /api/health/smoke with collections_count, bus_status, indices_ok, catalogo_present fields
  - test_smoke_build24.py with 6 unit tests mocking DB and event bus (no live DB required)
affects:
  - 05-02-PLAN (CI yaml references test_smoke_build24.py in pytest job)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Smoke endpoint returns structured BUILD 24 checks: all 4 new fields alongside existing checks"
    - "Unit tests import server function directly and patch server.db, server.client, server.app.state"

key-files:
  created:
    - backend/tests/test_smoke_build24.py
  modified:
    - backend/server.py

key-decisions:
  - "Placed new BD checks (collections_count, indices_ok, catalogo_present) inside existing main try block — shares same 'critico' fallback on DB error"
  - "Bus health check placed in separate try block outside main DB block — bus errors set status='degradado' not 'critico', consistent with non-critical failures"
  - "Tests use unittest.TestCase with asyncio.run() pattern — consistent with test_event_bus.py and test_permissions.py in BUILD 24 suite"

patterns-established:
  - "Smoke health checks: wrap each new check in its own try/except so one failing check does not block others"
  - "Test mocking: patch server.db, server.client, server.app at function level via context manager"

requirements-completed:
  - GIT-04
  - TST-05

# Metrics
duration: 4min
completed: 2026-03-27
---

# Phase 5 Plan 1: GitHub Production-Ready — Smoke Endpoint Summary

**Enhanced /api/health/smoke to return 4 BUILD 24 structured checks (collections_count, bus_status, indices_ok, catalogo_present) plus 6 mocked unit tests in test_smoke_build24.py**

## Performance

- **Duration:** 4 min
- **Started:** 2026-03-27T03:20:58Z
- **Completed:** 2026-03-27T03:25:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Added `collections_count` (via `list_collection_names()`), `bus_status` (from `bus.get_bus_health()`), `indices_ok` (checks `roddos_events.event_id` index), and `catalogo_present` (checks `catalogo_planes` doc count) to smoke endpoint
- All existing smoke checks (loanbooks_activos, cartera_total, inventario_motos, cfo_configuracion, alegra_conectado, anthropic_disponible) remain untouched
- Created `test_smoke_build24.py` with exactly 6 test functions covering all 4 new fields plus critico-on-DB-down scenario, using mocks only (no live Atlas connection needed)

## Task Commits

Each task was committed atomically:

1. **Task 1: Improve /api/health/smoke with BUILD 24 checks** - `5bd9114` (feat)
2. **Task 2: Create test_smoke_build24.py with 6 unit tests** - `2a07e9f` (test)

## Files Created/Modified

- `backend/server.py` - Added 4 new fields to result dict and corresponding DB/bus checks in smoke_test()
- `backend/tests/test_smoke_build24.py` - 6 unit tests with mocked Motor db, client, and EventBus

## Decisions Made

- Bus health check placed outside the main DB try block so bus errors only cause "degradado" (not "critico") — bus failure should not fail the entire deploy health check
- `list_collection_names()` used instead of `listCollections` command — cleaner Motor async API
- Tests use `unittest.TestCase` + `asyncio.run()` pattern matching `test_event_bus.py` conventions

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- Local Python environment (3.14) lacks FastAPI/Motor — tests cannot be run locally. This is the same constraint affecting all BUILD 24 tests; they run in CI with Python 3.11 + `pip install -r requirements.txt`. Syntax verified via `ast.parse()` instead.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- `/api/health/smoke` is now ready to be the curl post-deploy target in plan 05-02
- `test_smoke_build24.py` is ready to be referenced in the expanded CI pytest job (plan 05-02)
- The 4 new fields (`collections_count >= 30`, `bus_status == "ok"`) are the exact curl check criteria in D-03/D-05

---
*Phase: 05-github-production-ready*
*Completed: 2026-03-27*
