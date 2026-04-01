---
phase: 09-tool-use-agente-contador
plan: "01"
subsystem: agente-contador
tags: [tool-use, tdd, red-phase, tool-definitions, process-chat]
dependency_graph:
  requires: []
  provides:
    - tool_definitions.py TOOL_DEFS (6 MVP tools with input_schema)
    - test_phase9_tool_use.py RED suite (T5-T9 xfail contract)
  affects:
    - backend/ai_chat.py (Plan 09-02 will implement the tool_use branch)
tech_stack:
  added: []
  patterns:
    - "Tool definitions module: TOOL_DEFS dict + get_tool_schemas_for_api() Anthropic format"
    - "xfail TDD pattern: T1-T4 green (structure), T5-T9 xfail (behavior not yet implemented)"
    - "requires_confirmation metadata: true=write/confirm, false=read/auto-execute"
key_files:
  created:
    - backend/tool_definitions.py
    - backend/tests/test_phase9_tool_use.py
  modified: []
decisions:
  - "TOOL_DEFS is a standalone module (no ai_chat.py import) to avoid circular dependencies"
  - "requires_confirmation is metadata-only (not sent to Anthropic API) — stripped by get_tool_schemas_for_api()"
  - "T6 asserts MongoDB persistence of pending_action (agent_sessions.update_one) not just return dict — production-safety"
  - "T5-T9 use strict=True xfail so they fail loudly if accidentally passing before implementation"
  - "crear_causacion has 5 required fields per override constraints: monto, descripcion, cuenta_id, fecha, banco_id"
metrics:
  duration: "~8 minutes"
  completed_date: "2026-04-01"
  tasks_completed: 2
  tasks_total: 2
  files_created: 2
  files_modified: 0
---

# Phase 9 Plan 01: Tool Use Agente Contador — TDD RED Phase Summary

**One-liner:** TOOL_DEFS module with 6 MVP tool schemas + RED test suite (T1-T4 green, T5-T9 xfail) defining the contract for the tool_use loop migration.

## What Was Built

### Task 1: tool_definitions.py
Created `backend/tool_definitions.py` — standalone module with:

- `TOOL_DEFS` dict: 6 MVP tools with full input_schema (JSON Schema), requires_confirmation, description, endpoint, method
- `get_tool_schemas_for_api()`: returns Anthropic API-compatible list (strips internal fields)
- Module-level assertion validates exactly 6 tools are defined

**6 tools:**

| Tool | requires_confirmation | Purpose |
|------|-----------------------|---------|
| crear_causacion | True (write) | Journal entry in Alegra |
| registrar_pago_cartera | True (write) | Payment on loanbook |
| registrar_nomina | True (write) | Monthly payroll |
| crear_factura_venta | True (write) | Sales invoice (VIN+motor mandatory per ERROR-014) |
| consultar_facturas | False (read) | Query invoices from Alegra |
| consultar_cartera | False (read) | Query loanbook portfolio from MongoDB |

### Task 2: test_phase9_tool_use.py
Created `backend/tests/test_phase9_tool_use.py` with 10 tests (5 class-based + 5 module-level):

**GREEN (pass now):**
- T1: TOOL_DEFS has exactly 6 tools with correct names
- T2: All 4 write tools have requires_confirmation=True
- T3: Both read tools have requires_confirmation=False
- T4: crear_causacion.input_schema.required has exactly {monto, descripcion, cuenta_id, fecha, banco_id}
- T4b: get_tool_schemas_for_api() strips all internal fields

**xfail RED (fail now, will pass after Plan 09-02):**
- T5: TOOL_USE_ENABLED=true + write tool → pending_action returned, no Alegra execution
- T6: pending_action persisted to agent_sessions via update_one (MongoDB production-safety)
- T7: TOOL_USE_ENABLED=true + end_turn → XML fallback still parses action tag
- T8: TOOL_USE_ENABLED=false → tools= NOT passed to messages.create()
- T9: tools= present + system= has cache_control ephemeral when enabled

## Test Results

```
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t1_tool_defs_has_6_tools PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t2_write_tools_require_confirmation PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t3_read_tools_do_not_require_confirmation PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t4_crear_causacion_required_fields PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t4b_get_tool_schemas_strips_internal_fields PASSED
tests/test_phase9_tool_use.py::test_t5_tool_use_enabled_write_tool_returns_pending_action XFAIL
tests/test_phase9_tool_use.py::test_t6_write_tool_pending_action_persisted_to_mongodb XFAIL
tests/test_phase9_tool_use.py::test_t7_tool_use_enabled_end_turn_falls_back_to_xml XFAIL
tests/test_phase9_tool_use.py::test_t8_tool_use_disabled_no_tools_passed_to_api XFAIL
tests/test_phase9_tool_use.py::test_t9_tool_use_enabled_cache_control_preserved_in_system XFAIL

======================== 5 passed, 5 xfailed in 2.29s =========================
```

**Existing BUILD tests: 48 passed, 0 failed** (test_permissions, test_event_bus, test_phase4_agents — confirmed no regression).

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 062e1d3 | feat(09-01): add tool_definitions.py with 6 MVP tool schemas |
| Task 2 | 9ebc0c0 | test(09-01): add RED test suite for tool_use migration (T1-T4 green, T5-T9 xfail) |

## Decisions Made

1. **Standalone module:** TOOL_DEFS lives in its own `tool_definitions.py` to avoid circular imports with ai_chat.py.
2. **Metadata separation:** `requires_confirmation`, `endpoint`, `method` are internal metadata — `get_tool_schemas_for_api()` strips them before sending to Anthropic.
3. **MongoDB persistence (T6):** pending_action must be persisted to `agent_sessions` collection via `update_one()`, not just returned in the HTTP response dict. This ensures production safety if the frontend crashes after receiving the confirmation request.
4. **strict=True xfail:** Prevents false positives — tests will error loudly if they accidentally start passing before the implementation is ready.
5. **Tool field names:** Follow override constraints exactly — `cuenta_id` (not `account_id`), `banco_id` (not `banco_origen`), `banco` (not `banco_origen`) for registrar_pago_cartera.

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written (plus override constraint enforcement).

### CLAUDE.md Adjustments

- **ERROR-014 enforced:** `crear_factura_venta` has `vin` and `motor` as required fields per project constraint.
- **Override constraints applied:** All 6 tool field names match the exact schema specified in `<override_constraints>`.
- **T6 MongoDB persistence:** Per override constraint, T6 asserts `db.agent_sessions.update_one()` is called with `$set.pending_action`, not just that a dict is returned.

## Known Stubs

None — this plan creates a standalone definitions module. No data flows to UI. The xfail tests (T5-T9) define the contract for Plan 09-02.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/tool_definitions.py | FOUND |
| backend/tests/test_phase9_tool_use.py | FOUND |
| .planning/phases/09-tool-use-agente-contador/09-01-SUMMARY.md | FOUND |
| Commit 062e1d3 (tool_definitions) | FOUND |
| Commit 9ebc0c0 (test suite) | FOUND |
| T1-T4 passing | CONFIRMED (5 passed) |
| T5-T9 xfail | CONFIRMED (5 xfailed) |
| No existing test broken | CONFIRMED (48 passed in BUILD tests) |
