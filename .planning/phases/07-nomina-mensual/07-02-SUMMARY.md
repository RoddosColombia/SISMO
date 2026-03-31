---
phase: 07-nomina-mensual
plan: "02"
subsystem: nomina
tags: [tdd-green, nomina, alegra, journals, per-employee, anti-duplicate, fastapi]
dependency_graph:
  requires:
    - phase: 07-01
      provides: test_build23_f8_nomina_mensual (T1-T7 RED)
  provides:
    - registrar_nomina_mensual endpoint POST /nomina/registrar-mensual
    - per-employee Alegra journals with anti-duplicate guard
    - NOMINA-01, NOMINA-02, NOMINA-03 implemented and tested GREEN
  affects: [routers/nomina.py, server.py, nomina_registros collection]
tech-stack:
  added: []
  patterns:
    - per-employee-journal-loop
    - anti-duplicate-before-alegra-call
    - request-with-verify-safety-gate
    - fallback-account-5493
key-files:
  created: []
  modified:
    - backend/routers/nomina.py
key-decisions:
  - "Added registrar_nomina_mensual as new endpoint (POST /nomina/registrar-mensual) without removing legacy registrar_nomina (backward compat)"
  - "Renamed RegistrarNominaRequest to RegistrarNominaLegacyRequest to free name for F8 model"
  - "New RegistrarNominaRequest uses mes: int + anio: int + EmpleadoNomina (salario) matching T1-T7 expectations"
  - "Anti-duplicate check per empleado+mes+anio tuple BEFORE Alegra call — prevents P&L corruption"
  - "Only insert into nomina_registros after _verificado=True — T4 safety guarantee"
  - "Fallback gastos_nomina account 5493 (Gastos Generales) per CLAUDE.md rule (never 5495)"
patterns-established:
  - "Per-employee journal loop: iterate payload.empleados, check duplicate, call request_with_verify, insert on success"
  - "F8 pattern inherits F7 cartera.py structure: same imports, same router prefix, same anti-duplicate placement"
requirements-completed: [NOMINA-01, NOMINA-02, NOMINA-03]
duration: 15min
completed: "2026-03-31"
---

# Phase 07 Plan 02: Nomina Mensual Implementation Summary

**Per-employee Alegra journals (one journal per employee per month) with anti-duplicate guard per empleado+mes+anio, T1-T7 all GREEN**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-31T23:30:00Z
- **Completed:** 2026-03-31T23:46:34Z
- **Tasks:** 2 (Task 1 committed; Task 2 required no server.py changes)
- **Files modified:** 1

## Accomplishments

- `registrar_nomina_mensual` endpoint created with one Alegra journal per employee (NOMINA-01: 3 journals enero, NOMINA-02: 2 journals febrero)
- Anti-duplicate guard per `empleado+mes+anio` before Alegra call returns HTTP 409 (NOMINA-03)
- Alegra failure (`_verificado=False`) never inserts into `nomina_registros` (T4 safety guarantee)
- `nomina.mensual.registrada` event published to `roddos_events` with `total_nomina`, `empleados_count`, `journals` (T6)
- All 8 tests pass (T1-T7 functional + resumen)

## Task Commits

1. **Task 1: Create registrar_nomina_mensual with per-employee journals** - `bf36c75` (feat)
2. **Task 2: Wire nomina router + run T1-T7 GREEN** - no server.py changes needed (already registered)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/routers/nomina.py` - Added `EmpleadoNomina`, new `RegistrarNominaRequest` (mes: int, anio: int), renamed legacy model, added `registrar_nomina_mensual` endpoint, `obtener_cuenta_gastos_nomina()` helper, `ultimo_dia_mes()` helper, `MESES` dict

## Decisions Made

- Kept legacy `registrar_nomina` (F4) intact with renamed `RegistrarNominaLegacyRequest` — backward compatibility with existing UI/flows
- New `RegistrarNominaRequest` replaces the export name so tests can import it directly
- Server.py already had nomina router registered via try/except import block — no changes needed

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] RegistrarNominaRequest name conflict with legacy model**
- **Found during:** Task 1 (examining existing nomina.py)
- **Issue:** Existing `RegistrarNominaRequest` had `mes: str` + `banco_pago: str` + `Empleado.monto`; tests expect `mes: int`, `anio: int`, `banco_origen: str`, `EmpleadoNomina.salario`
- **Fix:** Renamed old model to `RegistrarNominaLegacyRequest`, updated `registrar_nomina` to use it, created new `RegistrarNominaRequest` with F8 fields
- **Files modified:** backend/routers/nomina.py
- **Verification:** Legacy endpoint still uses `RegistrarNominaLegacyRequest`; new endpoint uses `RegistrarNominaRequest`
- **Committed in:** bf36c75

---

**Total deviations:** 1 auto-fixed (Rule 1 - Bug — name conflict)
**Impact on plan:** Required renaming legacy model to free the export name for tests. No scope creep. Backward compatibility maintained.

## Issues Encountered

- Tests must run from `backend/` directory (not repo root) — `python -m pytest backend/tests/...` from root gives `ModuleNotFoundError: No module named 'routers'`. Running from `backend/` resolves it. This is pre-existing behavior consistent with all other BUILD 23 tests.

## Known Stubs

None — all data flows through real Alegra service calls (mocked in tests) and real MongoDB collections.

## User Setup Required

None — no external service configuration required. Nomina router was already registered in server.py.

## Next Phase Readiness

- NOMINA-01, NOMINA-02, NOMINA-03 all implemented and verified GREEN
- Phase 07 (nomina mensual) implementation complete
- Ready for phase 08 or production smoke test of F8 endpoint

## Self-Check: PASSED

- [x] `backend/routers/nomina.py` exists and contains `registrar_nomina_mensual`
- [x] Commit bf36c75 exists
- [x] 8 tests collected and all PASSED
- [x] `grep "status_code=409" backend/routers/nomina.py` → match (line 503)
- [x] `grep "ya registrada" backend/routers/nomina.py` → match (line 504)
- [x] `grep "request_with_verify" backend/routers/nomina.py` → match
- [x] `grep "nomina_registros" backend/routers/nomina.py` → match
- [x] `grep "5493" backend/routers/nomina.py` → match (line 425)
- [x] `grep "journal-entries" backend/routers/nomina.py` → 0 results (OK)
- [x] `grep "app.alegra.com/api/r1" backend/routers/nomina.py` → 0 results (OK)
- [x] `grep "5495" backend/routers/nomina.py` → 0 results (OK)
- [x] `grep "include_router.*nomina\|nomina_router" backend/server.py` → match

---
*Phase: 07-nomina-mensual*
*Completed: 2026-03-31*
