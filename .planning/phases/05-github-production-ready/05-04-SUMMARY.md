---
phase: 05-github-production-ready
plan: 04
subsystem: testing
tags: [pytest, tdd, ventas, facturacion, mocks, qrcode, sys-modules]

# Dependency graph
requires:
  - phase: 05-github-production-ready
    provides: ventas.py with crear_factura_venta + CrearFacturaVentaRequest
provides:
  - Test suite for F6 facturacion venta motos with correct isolation (7 tests)
  - T6 RED target asserting FACTURA-01 format without .upper(), no brackets, no spaces after VIN:/Motor:
  - sys.modules stub pattern for qrcode/pyotp/cryptography/motor/database in test env
affects: [05-05-PLAN]

# Tech tracking
tech-stack:
  added: [python-multipart (installed for FastAPI form data in test env)]
  patterns:
    - sys.modules stubs at file top for transitive import chain (qrcode, pyotp, cryptography, motor, database)
    - SimpleNamespace for payload bypass of Pydantic validation in isolation tests (T1, T2)
    - patch(routers.ventas.db, mock_db) to override module-level db in function-level tests (T2-T6)
    - mock_db fixture with explicit AsyncMock per collection (inventario_motos, loanbook, roddos_events, catalogo_planes)

key-files:
  created: []
  modified:
    - backend/tests/test_build23_f6_facturacion_venta.py

key-decisions:
  - "SimpleNamespace used for T1/T2 payloads — avoids Pydantic validation for isolation tests that test pre-validation logic"
  - "patch(routers.ventas.db) required for all tests touching DB — module-level db import is stubbed at file top"
  - "sys.modules stubs for cryptography, motor, database — routers/__init__.py eager-imports all routers which transitively pull all these"
  - "T3/T4/T5 pass with mock wiring — T6 RED is the clean target for plan 05-05"

patterns-established:
  - "Rule: stub routers/__init__.py transitive imports at file top to avoid eager import chain"
  - "Rule: always patch routers.ventas.db explicitly when testing endpoint functions directly"

requirements-completed:
  - FACTURA-01
  - FACTURA-02
  - FACTURA-03
  - FACTURA-04

# Metrics
duration: 25min
completed: 2026-03-31
---

# Phase 05 Plan 04: F6 Facturacion Venta Motos — Test Isolation Summary

**Test suite with sys.modules stubs + SimpleNamespace T1/T2 fixes enabling 6/7 pass, T6 RED on FACTURA-01 format mismatch (brackets + .upper() in ventas.py)**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-31T13:30:00Z
- **Completed:** 2026-03-31T13:55:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Fixed test isolation: all 7 tests now collect without ImportError
- T1 and T2 PASS: VIN missing = HTTP 400, moto Vendida = HTTP 400
- T3, T4, T5 PASS: full invoice creation flow with mock wiring
- T6 FAILS RED precisely: got `[TVS RAIDER 125] [Negro] - VIN: 9FL...` vs expected `TVS Raider 125 Negro - VIN:9FL...`
- T6 asserts FACTURA-01 format: original case, no brackets, no space after VIN:/Motor:

## Task Commits

1. **Task 1: Fix test isolation and update T6 for FACTURA-01 format** - `2514a48` (test)

## Files Created/Modified

- `backend/tests/test_build23_f6_facturacion_venta.py` - sys.path + 10 module stubs at top; T1/T2 use SimpleNamespace; T2-T6 patch routers.ventas.db; mock_db adds catalogo_planes; T6 asserts FACTURA-01 format

## Decisions Made

- Used SimpleNamespace (not MagicMock) for T1/T2 payloads to have attribute access without triggering Pydantic validators — the validation under test happens before DB access
- patch(routers.ventas.db) needed in T2-T6 because ventas.py uses module-level `db = import.database.db`, which was MagicMock at import time
- Stubbed `database` module directly in sys.modules to prevent MONGO_URL KeyError during routers/__init__.py eager import chain
- Added `python-multipart` install as Rule 3 deviation (blocking: FastAPI raises RuntimeError without it in test env)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Installed python-multipart missing in test environment**
- **Found during:** Task 1 (running tests after stubs added)
- **Issue:** FastAPI raises RuntimeError("Form data requires python-multipart") when routers are imported without it
- **Fix:** pip install python-multipart
- **Files modified:** None (env install)
- **Verification:** RuntimeError gone, tests proceed past import
- **Committed in:** 2514a48

**2. [Rule 1 - Bug] T2 required patch(routers.ventas.db) not mentioned in plan**
- **Found during:** Task 1 (T2 failing with MagicMock can't be awaited)
- **Issue:** ventas.py uses module-level `db` from database module; database was stubbed as MagicMock at top of test file, making `db.inventario_motos.find_one` non-awaitable
- **Fix:** Added `with patch("routers.ventas.db", mock_db):` in T2
- **Files modified:** backend/tests/test_build23_f6_facturacion_venta.py
- **Verification:** T2 passes, moto Vendida returns HTTP 400
- **Committed in:** 2514a48

**3. [Rule 1 - Bug] mock_db missing catalogo_planes collection**
- **Found during:** Task 1 (T3-T6 failing with MagicMock can't be awaited on catalogo_planes.find_one)
- **Issue:** ventas.py calls `db.catalogo_planes.find_one({"plan": payload.plan})` but mock_db fixture only had inventario_motos, loanbook, roddos_events
- **Fix:** Added `db.catalogo_planes = AsyncMock()` and `db.catalogo_planes.find_one = AsyncMock(return_value=None)` to fixture
- **Files modified:** backend/tests/test_build23_f6_facturacion_venta.py
- **Verification:** T3/T4/T5 pass
- **Committed in:** 2514a48

---

**Total deviations:** 3 auto-fixed (1 Rule 3 blocking install, 2 Rule 1 bugs in mock wiring)
**Impact on plan:** All fixes necessary for test isolation. No scope creep. T6 RED target is clean and precisely matches the format bug in ventas.py line 371.

## Issues Encountered

The full transitive import chain from `routers/__init__.py` was deeper than anticipated: auth.py -> security_service.py -> qrcode/pyotp/cryptography; auth.py -> database.py -> MONGO_URL; inventory.py -> pdfplumber; etc. Required stubbing 10+ modules. This is the standard pattern for this codebase test environment.

## Next Phase Readiness

- Plan 05-05 has a clean RED target: T6 fails with exact format diff showing `.upper()` and bracket issues in ventas.py line 371
- Fix needed in ventas.py: `producto_description = f"{modelo} {color} - VIN:{chasis} / Motor:{motor}"` (remove `.upper()`, remove brackets, remove spaces after colons)
- No blockers

## Self-Check: PASSED

- test file: FOUND at backend/tests/test_build23_f6_facturacion_venta.py
- SUMMARY.md: FOUND at .planning/phases/05-github-production-ready/05-04-SUMMARY.md
- Commit 2514a48: FOUND in git history

---
*Phase: 05-github-production-ready*
*Completed: 2026-03-31*
