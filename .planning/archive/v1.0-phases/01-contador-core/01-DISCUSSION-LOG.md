# Phase 1: Contador Core - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-24
**Phase:** 01-contador-core
**Areas discussed:** ai_chat.py decomposition, Idempotency strategy, Dead-letter & retry, Cache invalidation

---

## Session 1: Initial Context (2026-03-24)

### Gray Area Selection

| Option | Description | Selected |
|--------|-------------|----------|
| ai_chat.py decomposition | How to split 5,217 lines: module boundaries, migration strategy | |
| Idempotency strategy | Key generation, storage, retry behavior | |
| Dead-letter & retry | Queue design, retry policy, alerting | |
| Cache invalidation | Event-driven approach, event-to-cache mapping | |

**User's choice:** [No preference] — selected twice, interpreted as Claude's discretion on all areas
**Notes:** Phase 1 is purely technical debt elimination. User deferred all implementation decisions to Claude's judgment. CONT-00 was added mid-session as a strategic mandate (cobertura total de 32 flujos contables).

### Claude's Discretion

All 4 gray areas were resolved at Claude's discretion:
- **ai_chat.py decomposition**: Incremental extraction to `backend/agents/` modules
- **Idempotency**: MongoDB collection with TTL, hash-based keys, decorator on alegra_service.py
- **Dead-letter**: MongoDB collection, 5 retries with exponential backoff, APScheduler processing
- **Cache invalidation**: Event bus subscriptions invalidate specific cache keys, TTL as fallback

### Mid-Session Addition

- **CONT-00** added to REQUIREMENTS.md: Mandato estrategico de cobertura total de flujos contables (32 flujos del SVG)
- **ROADMAP.md** updated to include CONT-00 in Phase 1 requirements
- **SALES-01a/01b/02/03/04** added to REQUIREMENTS.md (Agente de Ventas y CRM)

---

## Session 2: User Context Update (2026-03-24)

### User-Provided Decisions

User viewed existing context and chose to update with specific decisions:

**1. SVG Flujos Contables — Structure Confirmed**
- SVG disponible en directorio del proyecto (pendiente agregar al repo)
- 32 flujos en 4 categorias: Ingresos, Egresos, Bancario, Analisis
- CONT-00 completado = 32 flujos con endpoint o accion que envia journal correcto a Alegra

**2. Prioridad de Ejecucion — LOCKED**

| Priority | Requirement | Rationale |
|----------|-------------|-----------|
| PRIMERO | CONT-01 (fix proveedor) | Desbloquea conciliacion bancaria (mayor volumen) |
| SEGUNDO | CONT-06 (smoke test 20/20) | Gate de calidad pre-decomposicion |
| TERCERO | CONT-02 (decomposicion) | Refactoring seguro con smoke test como gate |
| PARALELO | CONT-03, 04, 05 | En paralelo con CONT-02 |

**User's choice:** Orden explicito definido por usuario
**Notes:** CONT-06 esta en Phase 2 del roadmap pero el usuario lo requiere en Phase 1. Smoke test primero, decomposicion despues.

**3. Reglas de Negocio Inviolables — LOCKED**

| Rule | Description | Selected |
|------|-------------|----------|
| R-01: HTTP 200 verificacion | NUNCA reportar exito sin verificar HTTP 200 en Alegra | Mandatory |
| R-02: /journals endpoint | NUNCA usar /journal-entries (403) | Mandatory |
| R-03: plan_cuentas_roddos | IDs de cuentas SIEMPRE desde MongoDB | Mandatory |
| R-04: Auteco autoretenedor | NIT 860024781, NUNCA ReteFuente | Mandatory |

**User's choice:** All 4 rules are inviolable constraints from production experience
**Notes:** These are hard-learned production rules that must be enforced in every plan and test

## Deferred Ideas

None — discussion stayed within phase scope
