---
phase: 07-nomina-mensual
plan: "01"
subsystem: nomina
tags: [tdd, testing, nomina, alegra, journals]
dependency_graph:
  requires: []
  provides: [test_build23_f8_nomina_mensual]
  affects: [routers/nomina.py]
tech_stack:
  added: []
  patterns: [tdd-red, per-employee-journals, isolation-stubs, anti-duplicate-409]
key_files:
  created:
    - backend/tests/test_build23_f8_nomina_mensual.py
  modified: []
decisions:
  - "One journal per employee (not one aggregate journal) — each employee needs independent Alegra record for audit trail"
  - "Fallback account ID 5493 (Gastos Generales) for gastos_nomina per CLAUDE.md directive"
  - "RegistrarNominaRequest uses mes: int + anio: int (not YYYY-MM string) for cleaner API and T7 duplicate guard per empleado+mes+anio"
  - "T7 anti-duplicate checks per empleado+mes+anio tuple (not aggregate hash like existing nomina.py)"
metrics:
  duration_seconds: 218
  completed_date: "2026-03-31"
  tasks_completed: 1
  files_created: 1
  files_modified: 0
---

# Phase 07 Plan 01: Nomina Mensual TDD Red Phase Summary

TDD test suite (T1-T7) for nomina mensual per-employee journals — one Alegra journal per employee with isolation stubs and anti-duplicate guard.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create test file T1-T7 for nomina mensual | 883cb55 | backend/tests/test_build23_f8_nomina_mensual.py |

## What Was Built

8-test suite covering NOMINA-01 (per-employee journal creation), NOMINA-02 (february variant with 2 employees), and NOMINA-03 (anti-duplicate 409 guard). All 7 functional tests (T1-T7) are RED with `ImportError: cannot import name 'registrar_nomina_mensual' from 'routers.nomina'` — as expected for TDD RED phase. The `test_resumen_f8_todos_los_tests` passes (no imports needed).

## Test Coverage

| Test | Behavior | Status |
|------|----------|--------|
| T1 | 3 journals created for enero (1 per employee), success=True | RED |
| T2 | Correct amounts: debit=5493(gastos_nomina), credit=5314(banco) per employee | RED |
| T3 | Journal observations contain employee name + month in Spanish | RED |
| T4 | Alegra failure (_verificado=False) → NO insert in nomina_registros | RED |
| T5 | Febrero with 2 employees creates 2 journals | RED |
| T6 | Event "nomina.mensual.registrada" published with mes, anio, total_nomina, empleados_count | RED |
| T7 | Duplicate empleado+mes+anio raises HTTPException 409 "ya registrada" | RED |
| resumen | Summary test (no imports) | PASSES |

## Key Account IDs Used

- **Gastos Nomina:** ID 5493 (Gastos Generales — fallback per CLAUDE.md)
- **Banco Bancolombia:** ID 5314 (same as cartera)

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None — test file contains no data stubs. All mock data is hardcoded test fixtures with explicit values.

## Self-Check: PASSED

- [x] `backend/tests/test_build23_f8_nomina_mensual.py` exists
- [x] Commit 883cb55 exists: `git log --oneline | grep 883cb55`
- [x] 8 tests collected by pytest --collect-only
- [x] T1-T7 RED with ImportError: cannot import name 'registrar_nomina_mensual'
- [x] qrcode isolation stub present
- [x] ID 5493 (gastos_nomina fallback) present
- [x] ID 5314 (Bancolombia) present
- [x] status_code=409 present (T7 anti-duplicate)
