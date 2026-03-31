---
phase: 03-mongodb-completo
plan: 02
subsystem: ai_chat + alegra_service
tags: [action-handlers, alegra, mongodb, execute_chat_action, tdd-green, mock-data]

# Dependency graph
requires:
  - phase: 03-mongodb-completo
    plan: 01
    provides: Failing test suite (RED phase) for 5 ACTION_MAP read actions
  - phase: 02-consolidacion-capa-alegra
    provides: AlegraService.request() consolidado, _mock() method, get_accounts_from_categories()
provides:
  - 5 read action handlers in execute_chat_action() (consultar_facturas, consultar_pagos, consultar_journals, consultar_cartera, consultar_plan_cuentas)
  - MOCK_PAYMENTS constant in mock_data.py (3 entries)
  - MOCK_PAYMENTS wired in AlegraService._mock()
  - ID 5493 (Gastos Generales) added to MOCK_ACCOUNTS
affects: [ai_chat.py execute_chat_action, alegra_service.py _mock, mock_data.py]

# Tech tracking
tech-stack:
  added: []
  patterns: [TDD green phase, special-case handlers before ACTION_MAP lookup, params dict passed to service.request()]

key-files:
  created: []
  modified:
    - backend/ai_chat.py
    - backend/alegra_service.py
    - backend/mock_data.py

key-decisions:
  - "MOCK_PAYMENTS placed in mock_data.py (not alegra_service.py) — consistent with all other MOCK_* constants in the project"
  - "ID 5493 (Gastos Generales fallback) added to MOCK_ACCOUNTS as subAccount of GASTOS DE ADMINISTRACIÓN — required by CLAUDE.md and test_includes_id_5493"
  - "anthropic installed in Python 3.14 worktree env to unblock lazy-import test execution (was ModuleNotFoundError)"
  - "5 handlers inserted as special-case ifs BEFORE the ACTION_MAP lookup — consistent with consultar_saldo_socio pattern already in file"

requirements-completed: [ACTION-01, ACTION-02, ACTION-03, ACTION-04, ACTION-05]

# Metrics
duration: 20min
completed: 2026-03-30
---

# Phase 03 Plan 02: MongoDB Completo — 5 Read Action Handlers (TDD Green Phase) Summary

**5 read action handlers implemented in execute_chat_action() — consultar_facturas (limit=50), consultar_pagos (type filter), consultar_journals (/journals not /journal-entries), consultar_cartera (MongoDB only), consultar_plan_cuentas (/categories) — all 9 TDD tests pass**

## Performance

- **Duration:** ~20 min
- **Started:** 2026-03-30
- **Completed:** 2026-03-30
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- MOCK_PAYMENTS constant (3 entries: pay-001 out, pay-002 in, pay-003 out) added to mock_data.py
- MOCK_PAYMENTS imported and wired in AlegraService._mock() with type and date filters
- ID 5493 (Gastos Generales — CLAUDE.md fallback account) added to MOCK_ACCOUNTS
- 5 read action handlers added to execute_chat_action() before ACTION_MAP check:
  - ACTION-01 consultar_facturas: GET /invoices, limit=50, date filter yyyy-MM-dd
  - ACTION-02 consultar_pagos: GET /payments, type in/out filter
  - ACTION-03 consultar_journals: GET /journals (NOT /journal-entries)
  - ACTION-04 consultar_cartera: db.loanbook.find() MongoDB ONLY, no Alegra call
  - ACTION-05 consultar_plan_cuentas: service.get_accounts_from_categories() via /categories
- All 9 tests in test_phase3_actions.py PASS (TDD green phase complete)
- All 19 tests in test_alegra_service.py PASS (no regressions)

## Task Commits

1. **Task 1: Add MOCK_PAYMENTS and wire payments in _mock()** - `c472d95` (feat)
2. **Task 2: Implement 5 read action handlers** - `0829fdb` (feat)

## Files Created/Modified

- `backend/mock_data.py` - Added MOCK_PAYMENTS (3 entries), ID 5493 to MOCK_ACCOUNTS
- `backend/alegra_service.py` - Added MOCK_PAYMENTS import, wired payments handler in _mock()
- `backend/ai_chat.py` - Added 111 lines: 5 read action handler blocks before ACTION_MAP check

## Decisions Made

- MOCK_PAYMENTS placed in mock_data.py alongside all other MOCK_* constants — single source of truth for demo data
- ID 5493 added to MOCK_ACCOUNTS to satisfy CLAUDE.md constraint "Fallback cuentas Alegra: ID 5493 (Gastos Generales) — NUNCA ID 5495" and test_includes_id_5493
- Installed anthropic package in Python 3.14 worktree to enable lazy-import tests to execute (was failing with ModuleNotFoundError at import time)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing critical functionality] ID 5493 not present in MOCK_ACCOUNTS**
- **Found during:** Task 1 (preparing for test_includes_id_5493)
- **Issue:** test_includes_id_5493 requires ID 5493 (Gastos Generales — CLAUDE.md mandatory fallback) to appear in the cuentas list returned by consultar_plan_cuentas. MOCK_ACCOUNTS had no such entry.
- **Fix:** Added `{"id": 5493, "code": "5493", "name": "Gastos Generales", ...}` as subAccount under GASTOS DE ADMINISTRACIÓN in MOCK_ACCOUNTS in mock_data.py.
- **Files modified:** backend/mock_data.py
- **Commit:** c472d95

**2. [Rule 3 - Blocking issue] ModuleNotFoundError: anthropic not installed in Python 3.14**
- **Found during:** Task 2 verification (running tests)
- **Issue:** Despite lazy-import pattern, `from ai_chat import execute_chat_action` triggered `import anthropic` at the top of ai_chat.py — module not installed in this Python environment.
- **Fix:** Ran `pip install anthropic` to install the module. Tests immediately passed.
- **Files modified:** None (environment fix)
- **Commit:** N/A (environment change)

## Issues Encountered

- anthropic not installed in Python 3.14.3 worktree environment. Lazy import pattern in tests defers `from ai_chat import execute_chat_action` to function body, but ai_chat.py itself imports anthropic at the top level — lazy import in test defers the error to test execution time, not collection time. Fixed by installing anthropic.

## Known Stubs

None — all 5 handlers call real AlegraService.request() (which routes to _mock() in demo mode) or db.loanbook.find() directly. No hardcoded empty return values.

## Self-Check: PASSED

- `backend/ai_chat.py` - FOUND (111 lines added, handlers before ACTION_MAP check)
- `backend/alegra_service.py` - FOUND (MOCK_PAYMENTS import + payments handler in _mock)
- `backend/mock_data.py` - FOUND (MOCK_PAYMENTS + ID 5493)
- commit `c472d95` — FOUND (feat(03-02): add MOCK_PAYMENTS)
- commit `0829fdb` — FOUND (feat(03-02): implement 5 read action handlers)
- All 9 tests test_phase3_actions.py — PASS
- All 19 tests test_alegra_service.py — PASS

---
*Phase: 03-mongodb-completo*
*Completed: 2026-03-30*
