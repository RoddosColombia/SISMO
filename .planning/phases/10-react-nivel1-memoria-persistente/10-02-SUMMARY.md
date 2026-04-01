---
phase: 10-react-nivel1-memoria-persistente
plan: "02"
subsystem: backend/agent-memory
tags:
  - react-nivel1
  - agent-memory
  - persistent-memory
  - multi-tool-plan
  - haiku-extraction
  - tdd
dependency_graph:
  requires:
    - "10-01 (create_plan + execute_plan + cancel_plan + approve-plan endpoint)"
  provides:
    - "extract_and_save_memory() — persists user learnings to agent_memory without TTL"
    - "should_create_plan() — determines if tool_calls need agent_plans approval"
    - "_load_persistent_memory_section() — loads user memories into system_prompt"
    - "Memory injection in process_chat() system_prompt construction"
    - "Multi-tool_call detection in TOOL_USE_ENABLED branch"
  affects:
    - "backend/tool_executor.py"
    - "backend/ai_chat.py"
    - "backend/tests/test_phase10.py"
tech_stack:
  added:
    - "claude-haiku-4-5-20251001 — lightweight extraction model for agent_memory"
  patterns:
    - "agent_memory discriminator: 'source' field in [correction, pattern, preference] for new docs; 'tipo' field for legacy docs"
    - "upsert by {user_id, key} prevents duplicates in agent_memory"
    - "Memory injected into system_prompt just before LLM call (usage_count DESC, top 20)"
    - "should_create_plan: single read → direct execute; write or multi → create_plan + approval"
key_files:
  created: []
  modified:
    - "backend/tool_executor.py — added extract_and_save_memory(), should_create_plan()"
    - "backend/ai_chat.py — added _load_persistent_memory_section(), memory injection in process_chat(), multi-tool routing in TOOL_USE_ENABLED branch"
    - "backend/tests/test_phase10.py — replaced T5-T8 xfail with GREEN implementations"
decisions:
  - "extract_and_save_memory uses claude-haiku-4-5-20251001 (NOT Sonnet) — lightweight task per CLAUDE.md global rule"
  - "agent_memory new docs discriminated by 'source' field — legacy 'tipo' docs untouched"
  - "should_create_plan: READ_TOOLS = {consultar_facturas, consultar_cartera}; any write tool or 2+ tools → create plan"
  - "Memory injection wrapped in try/except (non-blocking) to prevent memory load failures from breaking chat"
  - "TOOL_USE_ENABLED branch refactored: all tool_blocks extracted first, then should_create_plan decides routing"
  - "T9 remains xpass (mock works fine) — no change from Phase 10A"
metrics:
  duration_minutes: 6
  completed_date: "2026-04-01"
  tasks_completed: 4
  tasks_total: 4
  files_created: 0
  files_modified: 3
---

# Phase 10 Plan 02: ReAct Nivel 1 — Memoria Persistente Summary

**One-liner:** Agent memory persistence using claude-haiku-4-5-20251001 for extraction with upsert-by-key deduplication and system_prompt injection.

## What Was Built

Implemented Phase 10B — Persistent Memory without TTL:

- `extract_and_save_memory()` in tool_executor.py: uses claude-haiku-4-5-20251001 to extract learnings from interactions (corrections, patterns, preferences). Only saves if confidence >= 0.7. Uses upsert by `{user_id, key}` to prevent duplicates.
- `should_create_plan()` in tool_executor.py: decides whether to create an agent_plans document. Single read tool (consultar_facturas/consultar_cartera) → direct execute. Any write tool or multiple tools → create_plan + approval flow.
- `_load_persistent_memory_section()` in ai_chat.py: loads top 20 agent_memory records with `source` field (the Phase 10B discriminator) ordered by usage_count DESC. Formats them as a MEMORIA PERSISTENTE section.
- Memory injection in `process_chat()`: injected just before the LLM call (after all system_prompt construction, before `_system_parts`). Non-blocking — errors are logged as warnings.
- TOOL_USE_ENABLED branch updated: extracts all `tool_blocks` from response first, then calls `should_create_plan()`. If True → `create_plan()` + return `pending_plan`. If False → existing single read-tool auto-execute behavior.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Implement extract_and_save_memory + should_create_plan | 00260ed | backend/tool_executor.py |
| 2 | GREEN T5-T8 — replace xfail tests | 5706485 | backend/tests/test_phase10.py |
| 3 | Add _load_persistent_memory_section + memory injection + multi-tool routing | f09aa1e | backend/ai_chat.py |
| 4 | Full verification (no separate commit) | — | verification only |

## Test Results

- T1: PASSED — create_plan() creates document in agent_plans with status pending_approval
- T2: PASSED — execute_plan() executes actions in order and marks completed
- T3: PASSED — execute_plan() stops on first failure with descriptive error
- T4: PASSED — cancel_plan() cancels plan setting status to cancelled
- T5: PASSED — extract_and_save_memory() saves with confidence >= 0.7 (mocked Haiku)
- T6: PASSED — extract_and_save_memory() uses upsert=True (no duplicates)
- T7: PASSED — _load_persistent_memory_section() returns MEMORIA PERSISTENTE section
- T8: PASSED — should_create_plan() returns False for single read, True for write/multi
- T9: XPASS — execute_plan with 2 actions (mock passes; marked xfail for semantic grouping)

BUILD tests (test_permissions + test_event_bus + test_phase4_agents): 48/48 PASSED.
test_mongodb_init.py: 2 pre-existing failures (P78S name mismatch + 37 vs 10 SISMO_KNOWLEDGE rules) — NOT caused by Phase 10B changes.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Restructured TOOL_USE_ENABLED branch indentation**
- **Found during:** Task 3
- **Issue:** Plan described adding `if not tool_block: pass; else:` construct which produced invalid Python structure — the `if tool_def...elif tool_def...` blocks were outside the `else:` clause, causing `UnboundLocalError` when `tool_block` is None.
- **Fix:** Changed to `if tool_block:` with all single-tool handling indented inside; no `else` needed since fallthrough to XML flow is natural.
- **Files modified:** backend/ai_chat.py
- **Commit:** f09aa1e

## Known Stubs

None — all functions are fully implemented for their intended scope. extract_and_save_memory() is not yet called automatically after every tool execution (that wiring is Phase 10C), but the function itself is complete and tested.

## Self-Check: PASSED

Files modified exist:
- backend/tool_executor.py — FOUND
- backend/ai_chat.py — FOUND
- backend/tests/test_phase10.py — FOUND

Commits exist:
- 00260ed — feat(10-02): add extract_and_save_memory + should_create_plan to tool_executor
- 5706485 — test(10-02): replace T5-T8 xfail with GREEN implementations
- f09aa1e — feat(10-02): add memory injection + multi-tool_call plan routing to ai_chat
