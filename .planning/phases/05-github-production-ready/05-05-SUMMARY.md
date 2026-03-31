---
phase: 05-github-production-ready
plan: 05
subsystem: ventas
tags: [facturacion, alegra, tdd, format-fix, FACTURA-01]

# Dependency graph
requires:
  - phase: 05-github-production-ready
    provides: Test suite F6 with T6 RED on FACTURA-01 format (05-04)
provides:
  - Fixed crear_factura_venta with FACTURA-01 description format (no brackets, original case)
  - All 7 F6 tests GREEN (T1-T6 + resumen)
affects: [smoke-tests, alegra-invoices]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - Remove .upper() from Alegra product description to preserve original case from inventario_motos
    - observations field now contains full FACTURA-01 format instead of "Venta a..." string

key-files:
  created: []
  modified:
    - backend/routers/ventas.py
    - backend/tests/test_build23_f6_facturacion_venta.py

key-decisions:
  - "observations field now carries FACTURA-01 format (Modelo Color - VIN:x / Motor:x) instead of verbose 'Venta a...' string — enables traceability in Alegra invoice PDF"
  - "Test file updated to include sys.modules stubs from 05-04 (same commit, no separate apply needed)"

requirements-completed:
  - FACTURA-01
  - FACTURA-02
  - FACTURA-03
  - FACTURA-04

# Metrics
duration: 8min
completed: 2026-03-31
---

# Phase 05 Plan 05: FACTURA-01 Format Fix Summary

**Fixed crear_factura_venta to use original-case description without brackets — "TVS Raider 125 Negro - VIN:9FL25AF31VDB95058 / Motor:BF3AT18C2356" — all 7 F6 tests GREEN**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-31T13:58:00Z
- **Completed:** 2026-03-31T14:06:00Z
- **Tasks:** 1
- **Files modified:** 2

## Accomplishments

- Removed `.upper()` from `modelo` and `version` variables in `crear_factura_venta` — preserves original case from `inventario_motos` ("TVS Raider 125", not "TVS RAIDER 125")
- Updated `product_description` format: `f"{modelo} {color} - VIN:{chasis} / Motor:{motor}"` (no brackets, no space after colon)
- Updated `observations` field: same FACTURA-01 format replacing old "Venta a {nombre}. Plan {plan} - VIN: {chasis}" string
- Applied sys.modules stubs + SimpleNamespace + db patch from 05-04 to test file in this worktree (05-04 ran on different agent worktree)
- All 7 tests GREEN: T1 (VIN missing → 400), T2 (mutex anti-doble venta → 400), T3 (invoice ID returned), T4 (moto → Vendida), T5 (loanbook → pendiente_entrega), T6 (FACTURA-01 format exact match), resumen

## Task Commits

1. **Task 1: Fix description format in crear_factura_venta per FACTURA-01** - `ce6f788` (fix)

## Files Created/Modified

- `backend/routers/ventas.py` - Lines 363-371: removed .upper() from modelo/version, updated product_description format; Line 483: updated observations to FACTURA-01 format
- `backend/tests/test_build23_f6_facturacion_venta.py` - Applied 05-04 isolation fixes: sys.modules stubs (qrcode/pyotp/cryptography/motor/database), SimpleNamespace T1/T2, patch(routers.ventas.db) T2-T6, catalogo_planes fixture, T6 asserts FACTURA-01 format

## Decisions Made

- `observations` field changed from "Venta a {nombre}. Plan {plan} - VIN: {chasis}" to FACTURA-01 format — provides full vehicle traceability in Alegra invoice PDF without losing context (VIN + Motor in observations = verifiable)
- Test file in this worktree was at pre-05-04 state (05-04 ran in `worktree-agent-aaede127`); applied those changes via `git show 2514a48` checkout to unblock tests

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Applied 05-04 test isolation changes to this worktree's test file**
- **Found during:** Task 1 (running tests)
- **Issue:** Test file in `worktree-agent-a8664500` lacked sys.modules stubs + db patches from 05-04 commit `2514a48` (which ran in a different agent worktree); all 6 functional tests failed with `ModuleNotFoundError: No module named 'qrcode'`
- **Fix:** Checked out 05-04 version of test file with `git show 2514a48:backend/tests/test_build23_f6_facturacion_venta.py`
- **Files modified:** `backend/tests/test_build23_f6_facturacion_venta.py`
- **Verification:** All 7 tests pass

## Known Stubs

None — all test assertions verify real format output from ventas.py.

## Self-Check: PASSED

- `backend/routers/ventas.py`: FOUND, contains "VIN:" (no brackets), no `.upper()` on modelo in crear_factura_venta
- `backend/tests/test_build23_f6_facturacion_venta.py`: FOUND, has sys.modules stubs at top, T6 asserts FACTURA-01 format
- SUMMARY.md: FOUND at `.planning/phases/05-github-production-ready/05-05-SUMMARY.md`
- Commit `ce6f788`: FOUND in git history

---
*Phase: 05-github-production-ready*
*Completed: 2026-03-31*
