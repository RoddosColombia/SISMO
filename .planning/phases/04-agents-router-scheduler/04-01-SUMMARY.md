---
phase: 4
plan: 04-01
title: "Agent Prompts & RAG Builder"
status: completed
completed_date: "2026-03-27"
duration_minutes: 4
tasks_completed: 2
tasks_total: 2
files_created:
  - backend/agent_prompts.py
files_modified: []
commits:
  - hash: fef5ed7
    message: "feat(04-01): create agent_prompts.py with SYSTEM_PROMPTS + RAG builder"
requirements_satisfied:
  - AGT-01
  - AGT-03
  - AGT-04
key_decisions:
  - "Contador prompt kept verbatim from ai_chat.py to preserve production-tested behavior"
  - "build_agent_prompt uses graceful fallback for missing kwargs placeholders"
  - "sismo_knowledge query failure is logged as warning, not raised — agent can still respond"
tags:
  - agents
  - prompts
  - rag
  - anthropic
  - prompt-caching
dependency_graph:
  requires: []
  provides:
    - agent_prompts.SYSTEM_PROMPTS
    - agent_prompts.AGENT_KNOWLEDGE_TAGS
    - agent_prompts.build_agent_prompt
  affects:
    - backend/ai_chat.py (future: replace AGENT_SYSTEM_PROMPT usage)
    - backend/services/cfo_agent.py (future: replace inline CFO prompt)
tech_stack:
  added: []
  patterns:
    - "Anthropic prompt caching via cache_control ephemeral on system messages"
    - "MongoDB RAG injection: sismo_knowledge.find({tags: {$in: agent_tags}})"
    - "Graceful partial format fallback for missing template placeholders"
---

# Phase 4 Plan 01: Agent Prompts & RAG Builder Summary

**One-liner:** Differentiated system prompts for 4 SISMO agents (contador, cfo, radar, loanbook) with MongoDB RAG injection and Anthropic prompt caching via build_agent_prompt().

## What Was Built

Created `backend/agent_prompts.py` — the single source of truth for all SISMO agent system prompts. The module provides:

1. **SYSTEM_PROMPTS** — dict with 4 agent prompts, each containing `{knowledge_rules}` placeholder:
   - `contador` (9,916 chars): Production prompt from ai_chat.py, with Colombian accounting rules, ReteFuente/IVA tables, Alegra account IDs, and full transactional flows
   - `cfo` (3,273 chars): Portfolio-first analyst — reads portfolio_summaries before Alegra, P&L base caja vs devengado, semáforo thresholds
   - `radar` (3,169 chars): Collections specialist — DPD bucket classification, WhatsApp message templates per bucket, escalation rules
   - `loanbook` (3,690 chars): Loan origination — VIN verification, plan catalog cuotas, state machine (pendiente_entrega → activo), cartera calculation

2. **AGENT_KNOWLEDGE_TAGS** — tag mapping for sismo_knowledge RAG queries per agent:
   - contador: contabilidad, retefuente, honorarios, autoretenedor, iva, ica, fallback, impuestos, gastos_generales, alegra
   - cfo: cartera, mora, dpd, buckets, iva, impuestos, loanbook
   - radar: mora, dpd, buckets, cobranza, cartera, clasificacion, loanbook, estados
   - loanbook: loanbook, estados, frecuencias, multiplicadores, planes, cartera

3. **build_agent_prompt()** — async function that:
   - Fetches matching sismo_knowledge rules from MongoDB by agent tags (up to 50 rules)
   - Formats rules as bullet list and injects into `{knowledge_rules}` placeholder
   - Returns `[{"type": "text", "text": filled_prompt, "cache_control": {"type": "ephemeral"}}]` for Anthropic API

## Acceptance Criteria Results

| Criterion | Result |
|-----------|--------|
| `backend/agent_prompts.py` exists | PASS |
| SYSTEM_PROMPTS dict with exactly 4 keys | PASS |
| Each prompt >= 200 chars | PASS (min: 3,169 chars) |
| AGENT_KNOWLEDGE_TAGS with 4 keys | PASS |
| Each prompt contains `{knowledge_rules}` | PASS (5 occurrences) |
| `grep -c SYSTEM_PROMPTS` >= 1 | PASS (6) |
| `grep -c AGENT_KNOWLEDGE_TAGS` >= 1 | PASS (3) |
| `grep -c knowledge_rules` >= 4 | PASS (8) |
| `async def build_agent_prompt` found | PASS |
| Function queries `db.sismo_knowledge.find` with `{"tags": {"$in": tags}}` | PASS |
| Returns list with `cache_control: {"type": "ephemeral"}` | PASS |
| `grep "AGENT_KNOWLEDGE_TAGS.get"` returns 1 match | PASS |

## Plan Verification

```
04-01 verification PASSED
```

## Deviations from Plan

**None — plan executed exactly as written.**

Minor implementation notes (not deviations):
- The plan's verification script used `ast.Assign` only, which misses `ast.AnnAssign` (type-annotated assignments). The module uses `SYSTEM_PROMPTS: dict[str, str] = {...}` which is AnnAssign. The actual content is correct; the verification script from the plan needed encoding and AnnAssign handling on this Windows environment.
- Added graceful fallback in `build_agent_prompt()` for missing kwargs placeholders (Rule 2 — missing error handling). If a caller omits an optional placeholder, the function logs a warning and substitutes only the keys it has instead of raising a KeyError.
- Added try/except around the sismo_knowledge MongoDB query (Rule 2 — missing error handling). If the collection doesn't exist yet, the agent prompt still builds with the "no hay reglas" fallback.

## Known Stubs

None. All 4 agent prompts are substantive (>3,000 chars each) with real RODDOS business rules. The `{knowledge_rules}` placeholder will be populated at runtime by `build_agent_prompt()` from the seeded sismo_knowledge collection.

## Next Steps

This module is a dependency for:
- Plan 04-02: Agent Router (confidence-threshold routing using these prompts)
- Future refactor: Replace `AGENT_SYSTEM_PROMPT` in `ai_chat.py` with `SYSTEM_PROMPTS["contador"]`
- Future refactor: Replace inline CFO prompt in `cfo_agent.py` with `SYSTEM_PROMPTS["cfo"]`

## Self-Check: PASSED

Files verified:
- `backend/agent_prompts.py`: FOUND
- Commit `fef5ed7`: FOUND (`git log --oneline --all | grep fef5ed7`)
