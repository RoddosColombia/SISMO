---
phase: 02-consolidacion-capa-alegra
plan: "01"
subsystem: alegra-layer
tags: [tdd, alegra, mock, journal-entries, test-suite]
dependency_graph:
  requires: []
  provides: [test-suite-alegra-service, mock-journals-fix]
  affects: [backend/alegra_service.py, backend/tests/test_alegra_service.py]
tech_stack:
  added: []
  patterns: [TDD red-green cycle, asyncio.run() helper for async tests, pytest fixtures]
key_files:
  created:
    - backend/tests/test_alegra_service.py
  modified:
    - backend/alegra_service.py
decisions:
  - "Tests usan asyncio.run() helper (no @pytest.mark.asyncio) — patron establecido en el proyecto"
  - "Mock db con alegra_credentials.find_one retornando is_demo_mode=True para activar path de demo"
  - "17 tests (superando minimo de 14) — incluye test_get_company_demo y test_request_with_verify_fuente_demo como cobertura adicional"
metrics:
  duration_seconds: 112
  completed_date: "2026-03-30"
  tasks_completed: 2
  files_modified: 2
---

# Phase 02 Plan 01: Test Suite AlegraService + Fix Mock journal-entries Summary

Suite de tests TDD para AlegraService cubriendo 5 endpoints en modo demo, errores HTTP en espanol, request_with_verify, y correccion del bug ALEGRA-03 que permitia que `_mock("journal-entries")` retornara datos de journals.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests para AlegraService — 5 endpoints + errores en espanol | 365eefc | backend/tests/test_alegra_service.py (+214 lines) |
| 2 | Fix mock journal-entries y hacer pasar todos los tests | d365955 | backend/alegra_service.py (1 line changed) |

## Success Criteria Verification

- [x] Suite de tests cubre GET para invoices, categories, payments, journals, contacts (ALEGRA-06)
- [x] Suite de tests cubre errores HTTP traducidos al espanol (401, 400-balance, 403, 404, 429, 500)
- [x] Suite de tests cubre request_with_verify POST+GET en modo demo (ALEGRA-03)
- [x] Mock corregido: journal-entries rechazado (retorna {}), journals funciona (ALEGRA-03)
- [x] Todos los 17 tests pasan (0 failures)

## Test Results

```
17 passed in 0.41s
```

Cobertura:
- `TestDemoModeEndpoints` (6 tests): GET invoices, categories/accounts, payments, journals, contacts, company
- `TestPostWithMock` (1 test): POST /journals retorna dict con `id`
- `TestRequestWithVerify` (2 tests): `_verificado=True` y `_fuente='demo'` en modo demo
- `TestTranslateErrors` (6 tests): 401, 400-balance, 403, 404, 429, 500
- `TestMockBugALEGRA03` (2 tests): journals retorna datos, journal-entries retorna {}

## Deviations from Plan

None — plan ejecutado exactamente como estaba escrito.

## Known Stubs

None — no hay stubs que afecten el objetivo del plan. Los tests pasan con datos reales del mock en alegra_service.py.

## Self-Check: PASSED
