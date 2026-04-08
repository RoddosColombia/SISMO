---
status: awaiting_human_verify
trigger: "create_plan() does not activate for multi-action request like 'Registra arrendamiento $3.614.953 e internet $180.000'"
created: 2026-04-01T00:00:00Z
updated: 2026-04-01T00:00:00Z
---

## Current Focus

hypothesis: TWO confirmed bugs — (1) should_create_plan() never sees 2 tool_calls because Anthropic returns 1 per turn for most prompts, and (2) "Confirmo" after a plan returns pending_plan, NOT pending_action, so the intercept in process_chat never fires for plan approval
test: Confirmed via code reading
expecting: Both bugs confirmed
next_action: Fix both bugs atomically

## Symptoms

expected: For "Registra arrendamiento $3.614.953 e internet $180.000", agent calls create_plan(), returns numbered plan, waits for approval
actual: create_plan() not activating. Either 1 tool_call returned and plan never shown, or falls to XML flow. After "Confirmo" intercept may not fire.
errors: No explicit error — silent wrong behavior
reproduction: Send "Registra arrendamiento $3.614.953 e internet $180.000" with TOOL_USE_ENABLED=true
started: Phase 10 (2026-04-01) — never verified end-to-end

## Eliminated

- hypothesis: should_create_plan() fails when exactly 1 write tool_call
  evidence: Code at line 412-418 shows: any single write tool returns True. So 1 write tool_call DOES trigger create_plan(). The actual bug is upstream.
  timestamp: 2026-04-01

## Evidence

- timestamp: 2026-04-01
  checked: tool_executor.py should_create_plan() lines 395-420
  found: Function only takes tool_calls list — no request text parameter. For 1 write tool_call it returns True. For 0 tool_calls returns False.
  implication: If Anthropic returns only 1 tool_call for a 2-operation request, create_plan() IS called but creates a 1-step plan, missing the second action entirely.

- timestamp: 2026-04-01
  checked: ai_chat.py lines 3921-3957 (TOOL_USE_ENABLED branch)
  found: tool_blocks = [b for b in _chat_resp.content if b.type == "tool_use"]. If Anthropic only returns 1 tool_use block, tool_calls_for_plan has len=1, should_create_plan returns True (write tool), create_plan is called with 1 step instead of 2.
  implication: ROOT CAUSE 1 — should_create_plan() must also detect from the original request text that there are multiple operations, so it can return True AND so callers know to ask the LLM to call tools for all operations. But deeper: the real issue is the plan only captures 1 of the 2 operations.

- timestamp: 2026-04-01
  checked: ai_chat.py lines 2879-2907 (pending_action intercept)
  found: The "Confirmo" intercept only checks _session.get("pending_action"). The plan flow (lines 3952-3957) returns "pending_plan" NOT "pending_action" and does NOT store anything in agent_sessions. So when user types "Confirmo", the intercept finds no pending_action and falls through to the LLM.
  implication: ROOT CAUSE 2 — After a plan is created, "Confirmo" from the user is never intercepted by process_chat. It goes to the LLM which doesn't know to call /approve-plan. The /approve-plan endpoint exists but is never invoked from the chat flow.

- timestamp: 2026-04-01
  checked: routers/chat.py lines 276-294
  found: /approve-plan endpoint exists and calls execute_plan(). But process_chat() intercept only handles pending_action (single-tool confirmation), not pending_plan.
  implication: The plan confirmation requires a SECOND intercept in process_chat for pending_plan — read pending_plan from agent_sessions and call execute_plan() directly.

## Resolution

root_cause: TWO bugs:
  1. When Anthropic returns 1 tool_call for a multi-operation request, should_create_plan() correctly returns True and creates a plan, but the plan only has 1 step — the second operation is silently dropped. Fix: should_create_plan(tool_calls, request) must detect multiple operations in request text; and when text indicates multi-op but only 1 tool_call returned, the plan description must warn that only 1 action was captured (or re-prompt the LLM with tool_choice to force multiple calls).
  2. After create_plan() returns pending_plan, process_chat() has no intercept for "Confirmo" targeting pending_plan. The /approve-plan endpoint exists but process_chat never stores plan_id in agent_sessions nor intercepts confirmation for it.

fix:
  1. should_create_plan(tool_calls, request="") — add request parameter. Detect multi-op keywords (e, más, y, también, además) to return True even for 0 tool_calls. Store plan_id in agent_sessions so it can be found on "Confirmo".
  2. Add pending_plan intercept block in process_chat() after existing pending_action intercept: if _session has pending_plan.plan_id and message is "confirmo", call execute_plan(plan_id, db, user) directly.
  3. When storing plan result (ai_chat.py line 3952), also persist pending_plan in agent_sessions so the intercept can find it.

verification:
files_changed: [backend/tool_executor.py, backend/ai_chat.py, backend/tests/test_phase10.py]
