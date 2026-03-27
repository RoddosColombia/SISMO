---
phase: 04-agents-router-scheduler
verified: 2026-03-26T22:30:00Z
status: human_needed
score: 4/5 must-haves verified
human_verification:
  - test: "Send 'cual es el saldo de cartera' through the chat API and observe which agent handles it"
    expected: "Route result agent == 'cfo' with confidence >= 0.7"
    why_human: "ROUTER_SYSTEM_PROMPT does not mention 'cartera' in the CFO entry (only P&L, semaforo, flujo de caja, margen, EBITDA). The word 'cartera' appears in the RADAR description implicitly. Actual LLM routing for this specific phrase cannot be verified statically — requires a live API call to claude-haiku-4-5-20251001."
  - test: "Send an ambiguous message (e.g., 'necesito ayuda con mis pagos') through the chat API"
    expected: "route[needs_clarification] == True and response contains the 4-option clarification menu"
    why_human: "Low-confidence path requires live LLM call; cannot be unit-tested without mocking the entire classification."
  - test: "Verify build_agent_prompt() is actually called in the live chat path for contador agent"
    expected: "sismo_knowledge rules are injected into the contador system prompt during real chat sessions"
    why_human: "ai_chat.py still uses AGENT_SYSTEM_PROMPT via .replace() pattern, not build_agent_prompt(). The function is built and tested in isolation but not wired into the production ai_chat.py contador flow. A human must confirm whether this is an intentional design decision (RAG for future use) or a gap."
---

# Phase 4: Agents, Router, Scheduler & Pipeline — Verification Report

**Phase Goal:** Each agent operates with its own system prompt, the router delegates with measurable confidence, and the CFO reads pre-computed summaries instead of calling Alegra directly.
**Verified:** 2026-03-26T22:30:00Z
**Status:** human_needed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | Each agent has a differentiated system prompt (not a stub) | VERIFIED | agent_prompts.py SYSTEM_PROMPTS has 4 keys, each prompt >= 200 chars (contador=72K chars, cfo=3.7K, radar=2.8K, loanbook=2.9K) |
| 2 | Router delegates with measurable confidence (INTENT_THRESHOLD=0.7) | VERIFIED | agent_router.py L17: `INTENT_THRESHOLD = 0.7`, classify_intent() implemented with LLM call to claude-haiku |
| 3 | Ambiguous messages trigger clarification (confidence < 0.7) | VERIFIED (structural) | RouteResult.needs_clarification set when confidence < 0.7; clarification_message with 4-option menu wired in ai_chat.py L2837-2838 |
| 4 | CFO reads portfolio_summaries before Alegra | VERIFIED | cfo_agent.py L793-808: get_portfolio_data_for_cfo() called first; datos_override used for semaforo/cartera if summary exists |
| 5 | build_agent_prompt() injects sismo_knowledge rules for any agent | PARTIAL | Function exists, queries db.sismo_knowledge, injects {knowledge_rules} — but NOT called in production ai_chat.py contador path |

**Score:** 4/5 truths fully verified (1 partial — build_agent_prompt wiring)

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `backend/agent_prompts.py` | SYSTEM_PROMPTS + AGENT_KNOWLEDGE_TAGS + build_agent_prompt() | VERIFIED | 567 lines, all three exports present, substantive content |
| `backend/agent_router.py` | classify_intent, INTENT_THRESHOLD=0.7, VALID_AGENTS, RouteResult | VERIFIED | 105 lines, all requirements met |
| `backend/services/portfolio_pipeline.py` | compute_portfolio_summary, compute_financial_report_mensual, get_portfolio_data_for_cfo | VERIFIED | 165 lines, all three functions present with real DB upserts |
| `backend/services/scheduler.py` | portfolio_summary_diario@23:30 + financial_report_mensual@day1 + dlq_retry | VERIFIED | All three jobs registered; hour=23 minute=30 for portfolio_summary |
| `backend/tests/test_phase4_agents.py` | 28 tests, 6 groups, all 5 success criteria | VERIFIED | 28 tests collected, 28 passed (0.08s) |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| ai_chat.py | agent_router.classify_intent | `from agent_router import classify_intent` | WIRED | L2834-2835, awaited before CFO/contador dispatch |
| ai_chat.py | cfo_agent.process_cfo_query | `route["agent"] == "cfo"` | WIRED | L2840-2842, CFO path preserved |
| ai_chat.py | agent_prompts.build_agent_prompt | not imported | NOT WIRED | ai_chat.py contador path uses `AGENT_SYSTEM_PROMPT` constant + `.replace()` directly. `build_agent_prompt()` is never called in production. |
| cfo_agent.process_cfo_query | portfolio_pipeline.get_portfolio_data_for_cfo | `from services.portfolio_pipeline import get_portfolio_data_for_cfo` | WIRED | L793-808, cached summary used when available |
| scheduler.start_scheduler | portfolio_pipeline.compute_portfolio_summary | `_compute_portfolio_summary` wrapper + cron job | WIRED | portfolio_summary_diario job at hour=23 minute=30 |
| scheduler.start_scheduler | portfolio_pipeline.compute_financial_report_mensual | `_compute_financial_report_mensual` wrapper + cron job | WIRED | financial_report_mensual job at day=1 hour=6 |

---

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| portfolio_pipeline.compute_portfolio_summary | cartera, semaforo | consolidar_datos_financieros() → analizar_cartera() + generar_semaforo() | Yes — calls cfo_agent functions which query MongoDB + Alegra | FLOWING |
| portfolio_pipeline.get_portfolio_data_for_cfo | portfolio doc | db.portfolio_summaries.find_one({"fecha": today}) | Yes — reads from MongoDB | FLOWING |
| cfo_agent.process_cfo_query | cached_summary | get_portfolio_data_for_cfo(db) | Yes — real DB read; Alegra fallback if None | FLOWING |
| agent_prompts.build_agent_prompt | knowledge_text | db.sismo_knowledge.find({"tags": {"$in": tags}}) | Yes — real DB query | FLOWING (but function not called in production path) |

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| 28 phase 4 tests pass | `python -m pytest tests/test_phase4_agents.py -v` | 28 passed in 0.08s | PASS |
| agent_prompts.py parses as valid Python AST | `python -c "import ast; ast.parse(open('agent_prompts.py').read()); print('OK')"` | OK (implied by test imports) | PASS |
| is_cfo_query removed from cfo_agent.py | grep CFO_KEYWORDS / is_cfo_query | 0 matches | PASS |
| classify_intent integrated in ai_chat.py | grep classify_intent | 1 match at L2834 | PASS |
| dlq_retry job still registered | grep dlq_retry scheduler.py | 1 match (id="dlq_retry") | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AGT-01 | 04-01 | SYSTEM_PROMPTS dict with 4 differentiated agents | SATISFIED | agent_prompts.py L476-481: SYSTEM_PROMPTS with "contador", "cfo", "radar", "loanbook" |
| AGT-02 | 04-02 | Router with INTENT_THRESHOLD 0.7 — confidence < 0.7 asks user | SATISFIED | agent_router.py INTENT_THRESHOLD=0.7; classify_intent sets needs_clarification; wired in ai_chat.py L2837 |
| AGT-03 | 04-01 | Prompt caching via cache_control ephemeral on system prompts | SATISFIED (partial) | build_agent_prompt() returns cache_control ephemeral — but not called in production contador path |
| AGT-04 | 04-01 | RAG from sismo_knowledge in build_agent_prompt() for all agents | SATISFIED (partial) | build_agent_prompt() queries sismo_knowledge by AGENT_KNOWLEDGE_TAGS — but not called in production contador path |
| SCH-01 | 04-03 | compute_portfolio_summary() at 11:30 PM, persists to portfolio_summaries | SATISFIED | scheduler.py: portfolio_summary_diario job at hour=23 minute=30; upserts to portfolio_summaries |
| SCH-02 | 04-03 | compute_financial_report_mensual() on day 1 of each month | SATISFIED | scheduler.py: financial_report_mensual job at day=1 hour=6; upserts to financial_reports |
| SCH-03 | 04-03 | dlq_retry job registered every 5 minutes | SATISFIED | scheduler.py: dlq_retry job with trigger="interval" minutes=5 confirmed present |
| SCH-04 | 04-03 | CFO reads portfolio_summaries before Alegra | SATISFIED | cfo_agent.py L793-808: get_portfolio_data_for_cfo() called first, datos_override pattern |
| TST-04 | 04-04 | test_agent_router.py — routing, clarification, system prompts | SATISFIED | test_phase4_agents.py TestIntentRouter (5 tests) + TestAgentPrompts (9 tests) |
| TST-06 | 04-04 | test_usage_integration.py — 15 tests (portfolio summary, RAG, events) | PARTIALLY SATISFIED | 5 success criteria tests present in TestSuccessCriteria; full integration tests (28 total) but no live API/DB tests |

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `backend/ai_chat.py` | 3019-3027 | `AGENT_SYSTEM_PROMPT.replace(...)` — old constant used, `build_agent_prompt()` not called | Warning | build_agent_prompt() is built and tested but the production contador path does not use it. {knowledge_rules} is never populated from sismo_knowledge in the real chat. AGT-04 RAG injection is functionally present in the new module but not active for contador agent in production. |
| `backend/ai_chat.py` | 141 | `AGENT_SYSTEM_PROMPT` constant does not include `{knowledge_rules}` placeholder | Warning | Confirms build_agent_prompt() cannot be a drop-in replacement for current contador path without additional work |

---

### Human Verification Required

#### 1. "cual es el saldo de cartera" Routing Test

**Test:** Send the message "cual es el saldo de cartera" via the chat API (POST /api/chat or equivalent) while monitoring logs or adding a debug return for the route object.

**Expected:** `route["agent"] == "cfo"` with confidence >= 0.7

**Why human:** The ROUTER_SYSTEM_PROMPT CFO entry describes "P&L, semaforo, flujo de caja, margen, EBITDA, estado general de la empresa" — it does not explicitly list "cartera" as a CFO keyword. The RADAR entry covers cobranza/mora/DPD. "Cual es el saldo de cartera" is a financial analysis query that should go to CFO, but the routing depends on claude-haiku-4-5-20251001's interpretation. There is ambiguity in the prompt that may cause it to return confidence < 0.7 (triggering clarification) instead of routing cleanly to CFO.

#### 2. Low-Confidence Clarification Flow

**Test:** Send "ayúdame con mis pagos" or "quiero saber algo" and confirm the clarification menu is returned to the frontend.

**Expected:** Response body has `{"message": "No estoy seguro...", "source": "router"}` with the 4-option menu visible to the user.

**Why human:** Cannot be verified without a live API call to claude-haiku. The structural code is correct but the actual LLM confidence threshold behavior needs runtime confirmation.

#### 3. build_agent_prompt() Production Wiring Decision

**Test:** Confirm with the engineering team whether the intent is to keep the old `AGENT_SYSTEM_PROMPT` path for contador indefinitely, or whether build_agent_prompt() should replace it.

**Expected (if AGT-04 should be fully active):** ai_chat.py's contador path should call `await build_agent_prompt("contador", db, context=..., accounts_context=..., ...)` instead of `AGENT_SYSTEM_PROMPT.replace(...)`. AGENT_SYSTEM_PROMPT in ai_chat.py should also include `{knowledge_rules}` placeholder.

**Why human:** The SUMMARY for 04-01 documents "Contador prompt kept verbatim from ai_chat.py to preserve production-tested behavior" — this suggests the disconnect was intentional. But if AGT-04 requires live RAG injection in production, this is a gap, not just a design decision.

---

### Gaps Summary

All 5 new artifacts exist and are substantive. The test suite passes 28/28. The primary finding is a **wiring gap** for `build_agent_prompt()`:

- `build_agent_prompt()` (AGT-04 RAG injection) is implemented correctly and tested, but `ai_chat.py` still uses the old `AGENT_SYSTEM_PROMPT` constant via `.replace()` for the contador agent flow. The function is never called in production.
- The `AGENT_SYSTEM_PROMPT` constant in `ai_chat.py` does not have a `{knowledge_rules}` placeholder, so even if `build_agent_prompt()` were imported, it could not replace the current pattern without modification.
- AGT-03 (prompt caching) is in the same situation: cache_control is returned by `build_agent_prompt()` but not applied to actual Anthropic API calls in `ai_chat.py`.

This is classified as `human_needed` rather than `gaps_found` because the SUMMARY explicitly documents the design choice to "keep contador prompt verbatim from ai_chat.py to preserve production-tested behavior." Whether this is a fully acceptable trade-off for AGT-03 and AGT-04 requires human confirmation.

The phase goal is substantially achieved: agents have differentiated prompts, the router delegates with measurable confidence (INTENT_THRESHOLD=0.7), and the CFO reads pre-computed summaries.

---

_Verified: 2026-03-26T22:30:00Z_
_Verifier: Claude Sonnet 4.6 (gsd-verifier)_
