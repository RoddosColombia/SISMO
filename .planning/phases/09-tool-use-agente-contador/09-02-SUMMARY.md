---
phase: 09-tool-use-agente-contador
plan: "02"
subsystem: agente-contador
tags: [tool-use, tdd, green-phase, tool-executor, process-chat, feature-flag]
dependency_graph:
  requires:
    - 09-01 (tool_definitions.py TOOL_DEFS, RED test suite)
  provides:
    - backend/tool_executor.py execute_tool() dispatcher
    - backend/ai_chat.py TOOL_USE_ENABLED branch in process_chat()
    - All 10 tests in test_phase9_tool_use.py GREEN (0 xfail)
  affects:
    - backend/ai_chat.py (process_chat modified)
tech_stack:
  added: []
  patterns:
    - "Feature flag gating: TOOL_USE_ENABLED env var → tool_use loop or XML fallback"
    - "MongoDB persistence for pending_action in agent_sessions (belt-and-suspenders)"
    - "Agentic loop: tool_use → execute_tool → second LLM call for natural language response"
    - "Auto-mock _AsyncDb/_AsyncCollection for Motor cursor chaining in tests"
key_files:
  created:
    - backend/tool_executor.py
  modified:
    - backend/ai_chat.py
    - backend/tests/test_phase9_tool_use.py
decisions:
  - "Feature flag default=false: TOOL_USE_ENABLED absent from env = no behavior change in production"
  - "pending_action stored in MongoDB agent_sessions with 72h TTL to survive Render cold starts"
  - "Test mock strategy: patch gather_context/gather_accounts_context/get_pending_topics to avoid deep import chain via qrcode dependency"
  - "_AsyncDb/_AsyncCollection auto-mock classes eliminate need to enumerate every DB collection used in process_chat()"
metrics:
  duration: "~10 minutes"
  completed_date: "2026-04-01"
  tasks_completed: 3
  tasks_total: 3
  files_created: 1
  files_modified: 2
---

# Phase 9 Plan 02: Tool Use Agente Contador — TDD GREEN Phase Summary

**One-liner:** TOOL_USE_ENABLED feature flag routes process_chat() to Anthropic tool_use loop with MongoDB-persisted pending_action for write tools and inline execution for read tools.

## What Was Built

### Task 1: tool_executor.py + ai_chat.py modification

**Created `backend/tool_executor.py`:**
- `execute_tool(tool_name, tool_input, db, user, session_id)`: dispatches based on `requires_confirmation`
  - Write tools: persists `pending_action` to `agent_sessions` collection via `update_one($set)`, returns proposal dict
  - Read tools (`consultar_facturas`, `consultar_cartera`): executes immediately via AlegraService or MongoDB
- `confirm_pending_action(session_id, confirmed, db, user)`: loads and executes or cancels stored pending_action

**Modified `backend/ai_chat.py` — surgical edit in process_chat():**
- Added `TOOL_USE_ENABLED` feature flag check (line ~3812)
- Restructured `messages.create()` call to use `create_kwargs` dict with optional `tools=`
- Added `tool_use` detection block after the LLM call:
  - `stop_reason == "tool_use"` + `requires_confirmation=True` → persist to MongoDB + return pending_action
  - `stop_reason == "tool_use"` + `requires_confirmation=False` → execute inline + second LLM call
- XML fallback (`end_turn`) preserved intact for non-tool responses and TOOL_USE_ENABLED=false

### Task 2: Remove xfail markers + fix mock setup

Removed all 5 `@pytest.mark.xfail` decorators from T5-T9 and updated mock infrastructure:

**Mock improvements:**
- Added `_AsyncDb`/`_AsyncCollection` auto-mock classes — any unknown collection returns `AsyncMock` methods automatically
- Added `.sort()/.limit()/.skip()` chaining on `_make_async_cursor()` for Motor cursor patterns
- Added patches for `gather_context`, `gather_accounts_context`, `get_pending_topics` in each test to avoid the `qrcode` module import chain

### Task 3: Commit protocol verification

All checks passed:
- 0 `app.alegra.com/api/r1` in Python files
- 0 `journal-entries` in non-test Python files
- Existing BUILD tests: 48 passed, 0 failed

## Test Results

```
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t1_tool_defs_has_6_tools PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t2_write_tools_require_confirmation PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t3_read_tools_do_not_require_confirmation PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t4_crear_causacion_required_fields PASSED
tests/test_phase9_tool_use.py::TestToolDefsStructure::test_t4b_get_tool_schemas_strips_internal_fields PASSED
tests/test_phase9_tool_use.py::test_t5_tool_use_enabled_write_tool_returns_pending_action PASSED
tests/test_phase9_tool_use.py::test_t6_write_tool_pending_action_persisted_to_mongodb PASSED
tests/test_phase9_tool_use.py::test_t7_tool_use_enabled_end_turn_falls_back_to_xml PASSED
tests/test_phase9_tool_use.py::test_t8_tool_use_disabled_no_tools_passed_to_api PASSED
tests/test_phase9_tool_use.py::test_t9_tool_use_enabled_cache_control_preserved_in_system PASSED

======================== 10 passed in 0.97s =========================
```

**BUILD tests: 48 passed, 0 failed** (test_permissions, test_event_bus, test_phase4_agents — no regression).

Note: `test_mongodb_init.py` has 2 pre-existing failures (P78S plan name + SISMO_KNOWLEDGE count) that existed before this plan — out of scope per SCOPE BOUNDARY rule.

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | 23ceae2 | feat(09-02): add tool_executor.py + TOOL_USE_ENABLED branch in process_chat() |
| Task 2 | 2e512b5 | test(09-02): remove xfail markers + fix mock setup — all 10 tests GREEN |

## Decisions Made

1. **Feature flag default false:** `TOOL_USE_ENABLED` absent from env = `""` which is not `"true"` — zero behavior change in production until explicitly opted in.
2. **MongoDB persistence (belt-and-suspenders):** When `requires_confirmation=True`, the pending_action is persisted to `agent_sessions` directly in `process_chat()` — not delegating to `execute_tool()`. Both paths write to MongoDB for safety.
3. **Mock abstraction:** `_AsyncDb/_AsyncCollection` classes auto-create AsyncMock for any unknown collection attribute. This avoids fragile enumeration of every MongoDB collection name used in `process_chat()`.
4. **Context function patching:** `gather_context`, `gather_accounts_context`, `get_pending_topics` are patched in tests to avoid the deep import chain through `routers/__init__.py` → `security_service.py` → `qrcode` (not installed in test env).
5. **timedelta UnboundLocalError fix (Rule 1):** Removed redundant `from datetime import timedelta` at line 3467 inside process_chat(). The local import shadowed the module-level import, causing `UnboundLocalError` in Python's function scope resolution when the new tool_use code (later in the function) used `timedelta`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed UnboundLocalError for `timedelta` in process_chat()**
- **Found during:** Task 2 (T5, T6 test failures)
- **Issue:** `from datetime import timedelta` at line 3467 inside an `if` block within `process_chat()` created a local variable binding. Python's scoping marks `timedelta` as a local in the entire function, causing `UnboundLocalError` when the new tool_use code (line ~3864) used `timedelta` before the shadowing assignment was reached at runtime.
- **Fix:** Removed the redundant local import — `timedelta` is already available at module level (`from datetime import datetime, timezone, timedelta` at line 9).
- **Files modified:** `backend/ai_chat.py` (line 3467)
- **Commit:** 23ceae2

**2. [Rule 2 - Missing mock setup] Updated _make_mock_db() in tests**
- **Found during:** Task 2 test execution
- **Issue:** The original `_make_mock_db()` didn't cover all DB collections/methods called in `process_chat()` (e.g., `agent_memory.find_one`, `chat_messages.find().sort().to_list()`, etc.)
- **Fix:** Created `_AsyncDb/_AsyncCollection` auto-mock classes that return `AsyncMock` for any unknown collection attribute, and added `.sort()/.limit()` chaining to cursor mock.
- **Files modified:** `backend/tests/test_phase9_tool_use.py`
- **Commit:** 2e512b5

## Known Stubs

None — all tool_use behavior is fully implemented. The `execute_tool()` for confirmed actions delegates to existing `execute_chat_action()` which already has full Alegra integration.

## Self-Check: PASSED

| Item | Status |
|------|--------|
| backend/tool_executor.py | FOUND |
| backend/ai_chat.py has TOOL_USE_ENABLED | FOUND (grep -c = 3) |
| backend/tests/test_phase9_tool_use.py has no xfail | CONFIRMED |
| Commit 23ceae2 (tool_executor + ai_chat) | FOUND |
| Commit 2e512b5 (test xfail removal) | FOUND |
| All 10 tests passing | CONFIRMED (10 passed) |
| BUILD tests no regression | CONFIRMED (48 passed) |
| TOOL_DEFS has 6 tools | CONFIRMED |
| tool_executor imports | CONFIRMED |
