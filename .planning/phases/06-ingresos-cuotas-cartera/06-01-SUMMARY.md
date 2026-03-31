---
phase: 06-ingresos-cuotas-cartera
plan: 01
subsystem: cartera
tags: [tdd, test-isolation, cartera, anti-duplicado, red-green]
dependency_graph:
  requires: []
  provides: [test-suite-T1-T7, cartera-isolation-pattern]
  affects: [backend/tests/test_build23_f7_ingresos_cartera.py]
tech_stack:
  added: []
  patterns: [qrcode-stub-isolation, db-patch-pattern, mock_db-fixture-expansion]
key_files:
  created: []
  modified:
    - backend/tests/test_build23_f7_ingresos_cartera.py
decisions:
  - Module stubs loop pattern (qrcode/cryptography/pdfplumber) over individual sys.modules lines — more maintainable
  - patch('routers.cartera.db', mock_db) added to each test to isolate global db from test mock_db
  - T7 uses patch('routers.cartera.db') only (no AlegraService mock) so cartera.py reaches network and fails 500 != 409
metrics:
  duration: "~12 minutes"
  completed: "2026-03-31T22:30:48Z"
  tasks_completed: 1
  files_modified: 1
---

# Phase 06 Plan 01: Fix Test Isolation T1-T6 GREEN + T7 RED Summary

Test isolation fixed for cartera payment suite: T1-T6 now pass (previously all failing with ModuleNotFoundError), and T7 added in RED state confirming the anti-duplicado guard is not yet implemented.

## What Was Done

### Task 1: Fix import isolation en T1-T6 y confirmar RED de T7

**Root cause:** `from routers.cartera import` in each test function triggered `routers/__init__.py` → `routers/auth.py` → `security_service.py` which imports `qrcode` and `cryptography` (not installed in CI). This caused all T1-T6 to fail with `ModuleNotFoundError`.

**Fix applied:**
1. Added module stubs block at top of test file (before all imports) for `qrcode`, `qrcode.image`, `qrcode.image.svg`, `cryptography`, `cryptography.fernet`, `pdfplumber`
2. Added `os.environ.setdefault()` calls for `MONGO_URL`, `DB_NAME`, `ALEGRA_EMAIL`, `ALEGRA_TOKEN`, `JWT_SECRET`
3. Expanded `mock_db` fixture to include `plan_ingresos_roddos.find_one` (returns `alegra_id=5455`) and `plan_cuentas_roddos.find_one` (returns `alegra_id=5314`), plus `cartera_pagos.find_one=None` default
4. Added `patch("routers.cartera.db", mock_db)` to all T1-T6 tests (the global `db` in cartera.py must be replaced by `mock_db` for DB calls to resolve correctly)
5. Added `test_t7_duplicado_detectado` in RED state: asserts HTTPException 409 but cartera.py has no guard yet → gets 500 instead → `AssertionError: Esperado 409, recibido 500` (RED confirmed)

## Test Results

| Test | Status | Notes |
|------|--------|-------|
| T1: registrar_pago_crea_journal | PASSED | Journal ID JE-2026-005678 returned |
| T2: journal_debito_credito_correcto | PASSED | Bancolombia 5314 debit, 5455 credit |
| T3: cuota_marcada_pagada_tras_http_200 | PASSED | cuotas[1].estado="pagada" confirmed |
| T4: fallo_alegra_no_modifica_loanbook | PASSED | loanbook.update_one NOT called on 500 |
| T5: saldo_pendiente_actualizado | PASSED | 7500000 - 192307.69 = 7307692.31 |
| T6: evento_pago_cuota_registrado | PASSED | event_type="pago.cuota.registrado" |
| test_resumen | PASSED | Summary test |
| T7: duplicado_detectado | FAILED (RED) | AssertionError: Esperado 409, recibido 500 |

**Result: 7 PASSED, 1 FAILED (T7 RED — expected, plan 06-02 implements guard)**

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Extended stub list beyond qrcode**
- **Found during:** Task 1 — after adding qrcode stub, next error was `ModuleNotFoundError: No module named 'cryptography'`, then `pdfplumber`
- **Issue:** routers/__init__.py chain required more stubs than just qrcode
- **Fix:** Added `cryptography`, `cryptography.fernet`, `pdfplumber` to stubs loop
- **Files modified:** backend/tests/test_build23_f7_ingresos_cartera.py
- **Commit:** 4dedcd7

**2. [Rule 2 - Missing critical] Added `patch("routers.cartera.db", mock_db)` to each test**
- **Found during:** Task 1 — after import isolation, T1 still failed because cartera.py's global `db` was real but mock_db was a separate fixture object
- **Issue:** Plan's action section described qrcode stub + mock_db fixture but did not explicitly mention db patching; test code sets mock_db collections but function uses global `db`
- **Fix:** Added `with patch("routers.cartera.db", mock_db):` wrapping the AlegraService patch in each test
- **Files modified:** backend/tests/test_build23_f7_ingresos_cartera.py
- **Commit:** 4dedcd7

**3. [Rule 1 - Bug] Used loop pattern for sys.modules stubs instead of direct assignments**
- **Reason:** More maintainable and extensible pattern; functionally identical to direct `sys.modules["qrcode"] = MagicMock()` lines
- **Note:** Plan's done criteria grep `sys.modules\[.qrcode.\]` won't match our loop pattern but the behavior is equivalent

## Known Stubs

None — T7 is deliberately RED (anti-duplicado guard not implemented) and is tracked for plan 06-02.

## Self-Check: PASSED

- FOUND: backend/tests/test_build23_f7_ingresos_cartera.py (modified)
- FOUND: .planning/phases/06-ingresos-cuotas-cartera/06-01-SUMMARY.md (created)
- FOUND: commit 4dedcd7
- Test suite verified: 7 PASSED, 1 FAILED (T7 RED as intended)
