---
phase: 04-agents-router-scheduler
plan: 05
subsystem: testing
tags: [tdd, accounting_engine, clasificar_gasto_chat, retenciones, autoretenedor, socios-cxc]

# Dependency graph
requires:
  - phase: 02-consolidacion-capa-alegra
    provides: request_with_verify() in AlegraService
  - phase: 03-mongodb-completo
    provides: accounting_engine.calcular_retenciones + execute_chat_action patterns

provides:
  - Failing test suite (RED phase) for clasificar_gasto_chat() behavioral contracts
  - Test for request_with_verify enforcement in crear_causacion
  - TDD contracts for Auteco autoretenedor detection (NIT 860024781)
  - TDD contracts for socios CXC detection (CC 80075452, 80086601)

affects:
  - 04-06 (GREEN phase — implements clasificar_gasto_chat to pass these tests)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD RED: try/except ImportError so test file is parseable before function exists"
    - "asyncio.run() for async test V1 (no @pytest.mark.asyncio — project convention)"
    - "Lazy import ai_chat inside test method to avoid anthropic missing in test env"

key-files:
  created:
    - backend/tests/test_chat_transactional_phase4.py
  modified: []

key-decisions:
  - "test_reteica_siempre_aplica_bogota passes in RED phase because calcular_retenciones already exists — this is correct and expected; 9/10 tests fail confirming RED"
  - "C3 honorarios PN uses cuenta 5475, C2 honorarios PJ uses cuenta 5476 — distinct accounts tested separately"
  - "V1 patches both request_with_verify AND request to detect which one crear_causacion calls"

patterns-established:
  - "Pattern: try/except ImportError at module level with None fallback for TDD RED phase imports"
  - "Pattern: assert function is not None as first line of each TDD test for clear failure message"

requirements-completed:
  - CHAT-01
  - CHAT-02
  - CHAT-04
  - CHAT-05

# Metrics
duration: 8min
completed: 2026-03-30
---

# Phase 04 Plan 05: Chat Transaccional Real — RED Phase TDD Summary

**10-test RED phase suite establishing behavioral contracts for clasificar_gasto_chat(): arriendo/honorarios PN+PJ/Auteco autoretenedor/socios CXC/servicios/compras + request_with_verify enforcement**

## Performance

- **Duration:** 8 min
- **Started:** 2026-03-30T03:00:00Z
- **Completed:** 2026-03-30T03:08:00Z
- **Tasks:** 1
- **Files modified:** 1

## Accomplishments

- Created `backend/tests/test_chat_transactional_phase4.py` with 10 tests (9 fail, 1 passes)
- RED phase confirmed: 9/10 tests fail because `clasificar_gasto_chat()` does not exist yet
- 1 test passes (`test_reteica_siempre_aplica_bogota`) — this is correct since `calcular_retenciones` already exists; the test validates existing behavior
- All 5 CHAT requirements covered: CHAT-01 through CHAT-05
- Auteco NIT `860024781` detection tested (C4)
- Socios CC `80075452` (Andres) and CC `80086601` (Ivan) detection tested (C5, C6)
- `request_with_verify` enforcement in `crear_causacion` tested (V1)

## Task Commits

1. **Task 1: Write failing test suite for clasificar_gasto_chat + special cases** - `cd0f1dc` (test)

## Files Created/Modified

- `backend/tests/test_chat_transactional_phase4.py` - 10-test RED phase suite covering C1-C8 + V1 + reteica

## Decisions Made

- `test_reteica_siempre_aplica_bogota` passes immediately because `calcular_retenciones` is already implemented — intentional, this test validates existing behavior is correct before implementing the new function
- V1 patches both `request_with_verify` AND `request` with separate mocks to precisely detect which one `crear_causacion` invokes — clearer failure message than patching only one
- C7 accepts `cuenta_debito in (5483, 5484, 5493)` to allow flexibility in tech services vs general fallback account

## Deviations from Plan

None — plan executed exactly as written. Test count is 10 (plan said 9+), which satisfies the minimum.

## Issues Encountered

None.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- RED phase complete: behavioral contracts established
- Plan 06 (GREEN phase) can now implement `clasificar_gasto_chat()` in `accounting_engine.py` and fix `crear_causacion` to use `request_with_verify()`
- All 10 test assertions are deterministic and non-flaky — safe to run in CI

---
*Phase: 04-agents-router-scheduler*
*Completed: 2026-03-30*
