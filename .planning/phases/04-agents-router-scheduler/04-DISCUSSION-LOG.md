# Phase 4: Agents, Router, Scheduler & Pipeline - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-26
**Phase:** 04-agents-router-scheduler
**Areas discussed:** Confidence router design, System prompts & RAG, Portfolio summaries & reports

---

## Confidence Router Design

| Option | Description | Selected |
|--------|-------------|----------|
| LLM classification (Recommended) | Claude classifies intent + confidence 0-1 | ✓ |
| Keyword scoring + heuristics | Weighted keyword matching, no API call | |

**User's choice:** LLM classification

| Option | Description | Selected |
|--------|-------------|----------|
| Ask clarification (Recommended) | Clarification question when confidence < 0.7 | ✓ |
| Default to Contador | Route to Contador as fallback | |

**User's choice:** Ask clarification

---

## System Prompts & RAG

| Option | Description | Selected |
|--------|-------------|----------|
| Code dict (Recommended) | SYSTEM_PROMPTS in backend/agent_prompts.py | ✓ |
| MongoDB collection | Store prompts in DB, editable at runtime | |

**User's choice:** Code dict

| Option | Description | Selected |
|--------|-------------|----------|
| Tag matching (Recommended) | Match agent type to sismo_knowledge tags | ✓ |
| Inject all 10 rules always | Every agent gets all rules | |

**User's choice:** Tag matching

---

## Portfolio Summaries & Reports

| Option | Description | Selected |
|--------|-------------|----------|
| Snapshot of semaforo + cartera (Recommended) | Reuse existing analysis, persist daily | ✓ |
| Full consolidar_datos_financieros | Persist entire aggregation | |

**User's choice:** Snapshot of semaforo + cartera

| Option | Description | Selected |
|--------|-------------|----------|
| Alegra + MongoDB (Recommended) | Monthly P&L calls Alegra once on day 1 | ✓ |
| MongoDB only | Use only local data | |

**User's choice:** Alegra + MongoDB

---

## Claude's Discretion

- Router classification prompt design
- RADAR and Loanbook system prompt content
- Tag mapping for sismo_knowledge → agents
- Portfolio/financial report document schemas

## Deferred Ideas

None.
