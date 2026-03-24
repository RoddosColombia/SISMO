# Phase 1: Contador Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 01-contador-core
**Areas discussed:** ai_chat.py decomposition, Idempotency strategy, Dead-letter & retry, Cache invalidation

---

## Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| ai_chat.py decomposition | How to split 5,217 lines: module boundaries, migration strategy | |
| Idempotency strategy | Key generation, storage, retry behavior | |
| Dead-letter & retry | Queue design, retry policy, alerting | |
| Cache invalidation | Event-driven approach, event-to-cache mapping | |

**User's choice:** [No preference] — selected twice, interpreted as Claude's discretion on all areas
**Notes:** Phase 1 is purely technical debt elimination. User deferred all implementation decisions to Claude's judgment. CONT-00 was added mid-session as a strategic mandate (cobertura total de 32 flujos contables).

---

## Claude's Discretion

All 4 gray areas were resolved at Claude's discretion:
- **ai_chat.py decomposition**: Incremental extraction to `backend/agents/` modules
- **Idempotency**: MongoDB collection with TTL, hash-based keys, decorator on alegra_service.py
- **Dead-letter**: MongoDB collection, 5 retries with exponential backoff, APScheduler processing
- **Cache invalidation**: Event bus subscriptions invalidate specific cache keys, TTL as fallback

## Deferred Ideas

None — discussion stayed within phase scope

## Mid-Session Addition

- **CONT-00** added to REQUIREMENTS.md: Mandato estrategico de cobertura total de flujos contables (32 flujos del SVG)
- **ROADMAP.md** updated to include CONT-00 in Phase 1 requirements
- **Git config** set: user.name="RODDOS SAS", user.email="info@roddos.com"
