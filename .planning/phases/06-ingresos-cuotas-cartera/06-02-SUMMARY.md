---
phase: 06-ingresos-cuotas-cartera
plan: 02
subsystem: cartera
tags: [tdd, anti-duplicado, cartera, cfo-agent, portfolio-summaries, mongodb]
dependency_graph:
  requires:
    - phase: 06-01
      provides: test-suite T1-T6 GREEN + T7 RED isolation pattern
  provides:
    - anti-duplicate guard in cartera.py (HTTP 409 on duplicate payment)
    - cartera_pagos.monto_pago field visible in CFO portfolio_summaries
    - full test suite T1-T8 GREEN (8 functional tests + resumen)
  affects:
    - backend/routers/cartera.py
    - backend/services/cfo_agent.py
    - backend/tests/test_build23_f7_ingresos_cartera.py
tech-stack:
  added: []
  patterns:
    - Anti-duplicate guard pattern: query cartera_pagos.find_one before calling Alegra
    - Field fallback chain: monto_pago > valor_pagado > monto for cartera payment amounts
    - _make_find_mock helper pattern for mocking MongoDB find().to_list() chains in tests
key-files:
  created: []
  modified:
    - backend/routers/cartera.py
    - backend/services/cfo_agent.py
    - backend/tests/test_build23_f7_ingresos_cartera.py
key-decisions:
  - "Guard placed after find oldest pending cuota (cuota_numero + fecha_pago resolved) but before income account lookup and AlegraService call"
  - "fecha_pago variable moved to guard block to avoid duplicate assignment later in journal creation"
  - "cfo_agent.py ingresos_reales sum uses monto_pago as primary field with fallback chain to valor_pagado and monto"
  - "T8 uses _make_find_mock helper and patches shared_state.get_portfolio_health to isolate consolidar_datos_financieros"
  - "Patch target for T8 is alegra_service.AlegraService (not services.cfo_agent.AlegraService) because AlegraService is imported inside the function"
patterns-established:
  - "Anti-duplicate: always query cartera_pagos.find_one({loanbook_id, cuota_numero, fecha_pago}) BEFORE calling Alegra"
  - "Field normalization fallback: p.get('monto_pago', p.get('valor_pagado', p.get('monto', 0))) for payment amounts"
requirements-completed: [CARTERA-02, CARTERA-03]
duration: 12min
completed: 2026-03-31
---

# Phase 06 Plan 02: Anti-Duplicate Guard + CFO Portfolio Wiring Summary

**HTTP 409 anti-duplicate guard in cartera.py + monto_pago field projection fix in cfo_agent.py, completing T7 GREEN and T8 GREEN (8/8 functional tests passing)**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-31T22:32:00Z
- **Completed:** 2026-03-31T22:44:00Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Implemented CARTERA-02: anti-duplicate guard in `registrar_pago_cartera()` — db.cartera_pagos.find_one queried before any Alegra call; HTTP 409 raised with "duplicado" detail if match found
- Implemented CARTERA-03: fixed field projection in cfo_agent.py — `monto_pago` added to cartera_pagos query projection and to ingresos_reales sum fallback chain
- Full suite T1-T8 + test_resumen: 9/9 PASSED (8 functional tests, 0 failures)

## Task Commits

1. **Task 1: Anti-duplicate guard in cartera.py — T7 GREEN** - `554bcda` (feat)
2. **Task 2: cfo_agent cartera_pagos field fix + T8 GREEN** - `38bc26d` (feat)

**Plan metadata:** (docs commit follows)

## Files Created/Modified

- `backend/routers/cartera.py` — Added ANTI-DUPLICATE GUARD block: fecha_pago resolved early, cartera_pagos.find_one checked, HTTPException 409 raised on match; removed duplicate fecha_pago assignment in journal creation block
- `backend/services/cfo_agent.py` — Added `monto_pago` to cartera_pagos find() projection; updated ingresos_reales sum to use monto_pago as primary field with fallback chain
- `backend/tests/test_build23_f7_ingresos_cartera.py` — Added test_t8_cartera_pagos_visible_en_portfolio_summaries; fixed AlegraService patch target to `alegra_service.AlegraService`; added `_make_find_mock` helper; added inventario_motos mock; patched shared_state.get_portfolio_health

## Decisions Made

- Guard placed after `cuota_numero` and `fecha_pago` are resolved (after "FIND OLDEST PENDING CUOTA") but before `obtener_cuenta_ingreso`, `obtener_cuenta_bancaria`, and `AlegraService` — guarantees Alegra is never called on duplicates
- Moved `fecha_pago = payload.fecha_pago or datetime.now(timezone.utc).strftime("%Y-%m-%d")` to guard block (was defined ~30 lines later for journal_payload); removed the duplicate assignment
- T8 patches `alegra_service.AlegraService` not `services.cfo_agent.AlegraService` because the import is local (`from alegra_service import AlegraService` inside the function body)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] AlegraService patch target incorrect in T8**
- **Found during:** Task 2 (T8 execution)
- **Issue:** Plan specified `patch("services.cfo_agent.AlegraService")` but `AlegraService` is imported inside `consolidar_datos_financieros()` function body, not at module level — patch raises AttributeError
- **Fix:** Changed patch target to `patch("alegra_service.AlegraService")` which patches the source module
- **Files modified:** backend/tests/test_build23_f7_ingresos_cartera.py
- **Verification:** T8 passes GREEN
- **Committed in:** 38bc26d (Task 2 commit)

**2. [Rule 2 - Missing Critical] Added inventario_motos mock and shared_state patch for T8**
- **Found during:** Task 2 (T8 execution) — `db.inventario_motos.find().to_list()` called without try/except in consolidar_datos_financieros; shared_state.get_portfolio_health also needed patching
- **Issue:** Plan's T8 mock list did not include `inventario_motos` (required by cfo_agent.py line 127 without exception handler); `get_portfolio_health` from shared_state also raised a mock error
- **Fix:** Added `_make_find_mock` helper for clean cursor mock setup; added `inventario_motos` mock; added `patch("services.shared_state.get_portfolio_health", new_callable=AsyncMock, return_value={})`
- **Files modified:** backend/tests/test_build23_f7_ingresos_cartera.py
- **Verification:** T8 passes GREEN, full suite 9/9 passes
- **Committed in:** 38bc26d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix, 1 missing critical test infrastructure)
**Impact on plan:** Both fixes necessary for T8 to pass. No scope creep — fixes are strictly within test isolation requirements for the T8 behavior specified in the plan.

## Issues Encountered

None — both issues encountered in Task 2 were resolved via auto-fix rules.

## Known Stubs

None — all fields are wired to real MongoDB data (monto_pago is stored by cartera.py and projected by cfo_agent.py).

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- CARTERA-01, CARTERA-02, CARTERA-03 all complete
- Phase 06 feature F7 (Ingresos por Cuotas de Cartera) is fully implemented and tested
- POST /cartera/registrar-pago creates journal in Alegra, guards against duplicates (409), and feeds CFO reports via cartera_pagos_mes
- Ready for production deployment (smoke test recommended against Render)

## Self-Check: PASSED

- FOUND: backend/routers/cartera.py (modified — anti-duplicate guard)
- FOUND: backend/services/cfo_agent.py (modified — monto_pago field projection)
- FOUND: backend/tests/test_build23_f7_ingresos_cartera.py (modified — T8 added)
- FOUND: .planning/phases/06-ingresos-cuotas-cartera/06-02-SUMMARY.md (created)
- FOUND: commit 554bcda (feat: anti-duplicate guard T7 GREEN)
- FOUND: commit 38bc26d (feat: cfo_agent fix + T8 GREEN)
- Test suite verified: 9/9 PASSED (T1-T8 + test_resumen)

---
*Phase: 06-ingresos-cuotas-cartera*
*Completed: 2026-03-31*
