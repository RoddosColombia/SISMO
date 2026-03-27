# Phase 4: Agents, Router, Scheduler & Pipeline - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Differentiated system prompts for 4 agents, LLM-based confidence router (threshold 0.7), daily portfolio summaries, monthly P&L reports, and RAG injection from sismo_knowledge into all agent prompts. The CFO reads pre-computed summaries instead of calling Alegra directly.

</domain>

<decisions>
## Implementation Decisions

### Confidence Router
- **D-01:** LLM classification for intent scoring — send message to Claude with a short classification prompt returning agent name + confidence 0-1. One cheap API call (~100 tokens). Replaces keyword-based is_cfo_query().
- **D-02:** INTENT_THRESHOLD = 0.7. Confidence < 0.7 triggers a clarification question to the user ("Quieres que te ayude con contabilidad o con un analisis financiero?"). No routing until clear.
- **D-03:** 4 agent targets: contador, cfo, radar, loanbook. Router returns `{"agent": "cfo", "confidence": 0.85}`.

### System Prompts & RAG
- **D-04:** SYSTEM_PROMPTS dict stored in code, in a new `backend/agent_prompts.py` module. 4 keys: contador, cfo, radar, loanbook. Version controlled.
- **D-05:** Prompt caching via Anthropic's `cache_control: {"type": "ephemeral"}` on system prompt messages (AGT-03). Reduces cost for repeated conversations.
- **D-06:** RAG injection via tag matching — each sismo_knowledge rule has tags (e.g., "mora", "retenciones"). `build_agent_prompt()` matches agent type to relevant tags and appends matched rules to system prompt. Not all 10 rules for every agent.

### Portfolio Summaries & Reports
- **D-07:** compute_portfolio_summary() reuses existing `analizar_cartera()` + `generar_semaforo()` outputs. Persists as one document in portfolio_summaries with today's date. Runs daily at 11:30 PM via scheduler.
- **D-08:** CFO's get_portfolio_data_for_cfo() reads from portfolio_summaries first. Falls back to Alegra only if no summary exists for today.
- **D-09:** Monthly P&L (_compute_financial_report_mensual) calls Alegra + MongoDB on day 1 of each month. Persists in financial_reports collection. One-time monthly Alegra call.

### Claude's Discretion
- Router classification prompt design (exact prompt text for ~100 token call)
- Exact system prompt content for RADAR and Loanbook agents (Contador and CFO already exist)
- Tag mapping: which sismo_knowledge tags map to which agents
- portfolio_summaries document schema (which fields from semaforo + cartera to persist)
- financial_reports document schema
- Whether to add a /api/portfolio/latest endpoint or only internal use

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current agent/routing code (to modify)
- `backend/ai_chat.py` lines 141-200 — AGENT_SYSTEM_PROMPT (current accounting prompt)
- `backend/ai_chat.py` lines 2834-2836 — Current routing via is_cfo_query()
- `backend/services/cfo_agent.py` lines 71-78 — CFO_KEYWORDS (to replace with router)
- `backend/services/cfo_agent.py` lines 89-250 — consolidar_datos_financieros() (CFO data pipeline)
- `backend/services/cfo_agent.py` lines 594-655 — generar_semaforo() (reused by portfolio summary)
- `backend/services/cfo_agent.py` lines 315-451 — analizar_cartera() (reused by portfolio summary)

### Scheduler (to add new jobs)
- `backend/services/scheduler.py` lines 340-493 — Current 14 registered jobs

### Phase 1-3 outputs
- `backend/event_models.py` — RoddosEvent (bus.emit for portfolio events)
- `backend/services/event_bus_service.py` — EventBusService for publishing events
- `init_mongodb_sismo.py` — sismo_knowledge seed data (10 rules with tags for RAG)
- `init_mongodb_sismo.py` — portfolio_summaries + financial_reports collections created

### Requirements
- `.planning/REQUIREMENTS.md` §Agentes & Router (AGT-01 to AGT-04) + §Scheduler & Pipeline (SCH-01 to SCH-04) + TST-04 + TST-06

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `cfo_agent.py` generar_semaforo(): 5-color health scorecard — reused directly by compute_portfolio_summary()
- `cfo_agent.py` analizar_cartera(): Mora rate, roll_rate, top morosos — reused directly
- `cfo_agent.py` consolidar_datos_financieros(): Full Alegra+MongoDB aggregation — reused for monthly P&L
- `shared_state.py` get_portfolio_health(): Basic portfolio stats with 30s cache — augmented by daily snapshot
- Existing AGENT_SYSTEM_PROMPT in ai_chat.py: Contador prompt already well-crafted, can serve as template

### Established Patterns
- Scheduler uses APScheduler with cron triggers registered in start_scheduler()
- CFO analysis functions return dicts (pyg, cartera, semaforo, etc.)
- Anthropic SDK already integrated (ai_chat.py, cfo_agent.py) — cache_control is a SDK feature

### Integration Points
- Router replaces is_cfo_query() in ai_chat.py process_chat()
- build_agent_prompt() called before every LLM invocation in ai_chat.py
- compute_portfolio_summary() registered as new scheduler job
- get_portfolio_data_for_cfo() replaces direct Alegra calls in cfo_agent.py

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches within the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 04-agents-router-scheduler*
*Context gathered: 2026-03-26*
