---
gsd_state_version: 1.0
milestone: v23.0
milestone_name: milestone
status: Phase complete — ready for verification
stopped_at: "Completed 08a-01-PLAN.md — CRM Robusto: score multidimensional + acuerdos_pago + 5 endpoints + 10 tests GREEN"
last_updated: "2026-04-05T17:46:00.502Z"
progress:
  total_phases: 11
  completed_phases: 11
  total_plans: 33
  completed_plans: 33
---

# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-26)

**Core value:** Contabilidad automatizada sin intervencion humana + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos
**Current focus:** Phase 08a — CRM Robusto

## Current Position

Phase: 08a (CRM Robusto) — EXECUTING
Plan: 1 of 1

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
- [Phase 10]: execute_plan() calls execute_chat_action_for_plan() wrapper — never calls Alegra directly (ERROR-004 prevention)
- [Phase 10]: cancel_plan() is a standalone function (not method) to allow direct import in routers/chat.py without circular dependencies
- [Phase 10]: extract_and_save_memory uses claude-haiku-4-5-20251001 for lightweight memory extraction (NOT Sonnet)
- [Phase 10]: should_create_plan: READ_TOOLS={consultar_facturas,consultar_cartera}; any write or 2+ tools → create plan for approval
- [Phase 10]: agent_memory new schema uses 'source' discriminator; legacy 'tipo' docs untouched
- [Phase 08a]: Score neutro para cliente nuevo = 70 almacenado en crm_clientes; calcular_score_roddos() es la función dinámica
- [Phase 08a]: T2 usa escenario sin contactabilidad para garantizar score<25 con fórmula exacta PRD

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

### Quick Tasks Completed

| # | Description | Date | Commit | Directory |
|---|-------------|------|--------|-----------|
| 260406-iju | Hotfix: conectar plan_id del backend con el ExecutionCard existente | 2026-04-06 | f15f9bb | [260406-iju-hotfix-conectar-plan-id-del-backend-con-](.planning/quick/260406-iju-hotfix-conectar-plan-id-del-backend-con-/) |
| 260330-fs8 | Hotfix ERROR-017: consolidar ALEGRA_BASE_URL, eliminar app.alegra.com/api/r1 (6 archivos) | 2026-03-30 | 26ceb5d | [260330-fs8-hotfix](./quick/260330-fs8-hotfix-cr-tico-error-017-la-url-base-de-/) |
| 260401-d5z | Knowledge Base Service RAG: service + 22 reglas seed + admin API + process_chat() integration | 2026-04-01 | 78f2764 | [260401-d5z](./quick/260401-d5z-knowledge-base-service-rag-para-agentes-/) |
| 260401-esw | Global66 webhook router: HMAC-SHA256 + MD5 anti-dup + confianza routing (Alegra /journals vs conciliacion_partidas) | 2026-04-01 | dcac02d | [260401-esw](./quick/260401-esw-global66-webhook-router-post-api-global6/) |
| 260401-fq4 | Admin seed endpoints: POST /api/admin/run-seed + GET /api/admin/seed-status, 3 tests (knowledge_base/plan_cuentas/invalid) | 2026-04-01 | 567c8ed | [260401-fq4](./quick/260401-fq4-admin-seed-endpoint-post-api-admin-run-s/) |
| 260402-1hh | Fase 1 auditoria Alegra: GET alegra-completo (paginacion real, clasificacion, duplicados Auteco) + POST aprobar-limpieza + POST anular-bill-duplicada, 7 tests GREEN | 2026-04-02 | f38bd70 | [260402-1hh](./quick/260402-1hh-fase-1-auditoria-completa-de-alegra-dete/) |
| Phase 08a P01 | 35 | 5 tasks | 6 files |

## Session Continuity

Last session: 2026-04-05T17:46:00.496Z
Stopped at: Completed 08a-01-PLAN.md — CRM Robusto: score multidimensional + acuerdos_pago + 5 endpoints + 10 tests GREEN
Resume file: None
