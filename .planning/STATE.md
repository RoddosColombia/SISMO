---
gsd_state_version: 1.0
milestone: v2.0
milestone_name: milestone
status: In progress
stopped_at: Completed 09-02 TDD GREEN phase — tool_executor.py + TOOL_USE_ENABLED branch + all 10 tests GREEN
last_updated: "2026-04-01T18:57:00Z"
progress:
  total_phases: 9
  completed_phases: 5
  total_plans: 17
  completed_plans: 18
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Contabilidad automatizada sin intervencion humana + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos
**Current focus:** Phase 5 — GitHub Production-Ready

## Current Position

Phase: 9
Plan: 02 complete (Phase 9 complete — both waves done)

## Performance Metrics

**Velocity:**

- Total plans completed: 0
- Average duration: N/A
- Total execution time: 0 hours

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.

- [Phase 04]: Contador prompt kept verbatim from ai_chat.py AGENT_SYSTEM_PROMPT to preserve production-tested behavior
- [Phase 04]: build_agent_prompt uses graceful fallback for missing kwargs placeholders — prevents KeyError in production
- [Phase 04-02]: Used Claude Haiku for LLM-based intent routing with INTENT_THRESHOLD=0.7 replacing keyword-based is_cfo_query()
- [Phase 04-03]: Use portfolio.resumen.calculado event type from catalog; source_agent=cfo for pipeline events; datos_override pattern in process_cfo_query for cache-first CFO reads
- [Phase 04]: Stubbed anthropic module via sys.modules for tests without API key requirement
- [Phase 04]: SC1 test validates CFO router entry via P&L/semaforo terms (cartera routes to RADAR)
- [Phase 05]: Full README rewrite (not surgical cleanup) to eliminate Emergent/BUILD18/concesionario identity drift
- [Phase 05]: CLAUDE.md appended with bus.emit() protocol and known errors — existing content preserved
- [Phase 05-github-production-ready]: smoke_test bus health placed outside main DB try block — bus errors give 'degradado' not 'critico'
- [Phase 05-02]: pytest-build24 job depends on backend-check to fail fast on syntax errors before running tests
- [Phase 05-02]: smoke-post-deploy runs only on push to main to prevent hitting production on branch pushes
- [Phase 09-01]: TOOL_DEFS standalone module (no ai_chat.py import) to avoid circular dependencies
- [Phase 09-01]: requires_confirmation is metadata-only — stripped by get_tool_schemas_for_api() before Anthropic API call
- [Phase 09-01]: T6 xfail asserts MongoDB persistence of pending_action to agent_sessions (production-safety, not just return dict)
- [Phase 09-02]: TOOL_USE_ENABLED default=false ensures zero production behavior change until explicitly opted in
- [Phase 09-02]: pending_action persisted to MongoDB agent_sessions both in process_chat() and tool_executor.py (belt-and-suspenders for Render cold starts)
- [Phase 09-02]: timedelta local import at line 3467 removed — was causing UnboundLocalError via Python function scope shadowing of module-level import

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260330-fs8 | Hotfix ERROR-017: consolidar ALEGRA_BASE_URL, eliminar app.alegra.com/api/r1 (6 archivos) | 2026-03-30 | 26ceb5d | [260330-fs8-hotfix](./quick/260330-fs8-hotfix-cr-tico-error-017-la-url-base-de-/) |
| 260401-d5z | Knowledge Base Service RAG: service + 22 reglas seed + admin API + process_chat() integration | 2026-04-01 | 78f2764 | [260401-d5z](./quick/260401-d5z-knowledge-base-service-rag-para-agentes-/) |
| 260401-esw | Global66 webhook router: HMAC-SHA256 + MD5 anti-dup + confianza routing (Alegra /journals vs conciliacion_partidas) | 2026-04-01 | dcac02d | [260401-esw](./quick/260401-esw-global66-webhook-router-post-api-global6/) |
| 260401-fq4 | Admin seed endpoints: POST /api/admin/run-seed + GET /api/admin/seed-status, 3 tests (knowledge_base/plan_cuentas/invalid) | 2026-04-01 | 567c8ed | [260401-fq4](./quick/260401-fq4-admin-seed-endpoint-post-api-admin-run-s/) |

## Session Continuity

Last session: 2026-04-01
Stopped at: Completed 09-02 — TDD GREEN phase for tool_use migration (tool_executor.py + ai_chat.py TOOL_USE_ENABLED + 10 tests GREEN)
Resume file: None
