# Phase 3: MongoDB Completo - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite init_mongodb_sismo.py as the single source of truth for all MongoDB collections, indices, schema validation, and seed data. 30+ collections with ESR indices, seeded production data (catalogo_planes, plan_cuentas_roddos, sismo_knowledge), and idempotent execution. Remove index creation from server.py startup.

</domain>

<decisions>
## Implementation Decisions

### Init Script Architecture
- **D-01:** init_mongodb_sismo.py is the SINGLE source of truth for ALL collections, indices, schema validation, and seed data. server.py startup only connects to MongoDB — no index creation, no seeding.
- **D-02:** Use sync pymongo driver (not async Motor). The init script runs as a standalone CLI command, no event loop needed. Already uses pymongo today.
- **D-03:** Script must be fully idempotent — running twice produces identical results with no errors on the second run. Use create_index (idempotent by nature) and upsert patterns for seed data.

### Seed Data Organization
- **D-04:** ALL seed data consolidated into init_mongodb_sismo.py. Remove seed data from router files (loanbook.py CATALOGO_DEFAULT, gastos.py PLAN_CUENTAS_RODDOS, server.py startup seeds). Single source of truth.
- **D-05:** plan_cuentas_roddos: keep all valid entries, ensure ID 5495 is NOT included, fallback defaults to 5493. The "28" in requirements is approximate — seed whatever real IDs exist minus 5495.
- **D-06:** catalogo_planes: seed real weekly/biweekly/monthly plans with correct multipliers (Semanal x1.0, Quincenal x2.2, Mensual x4.4) from existing CATALOGO_DEFAULT in loanbook.py.
- **D-07:** sismo_knowledge: seed 10 critical business rules (mora, retenciones, autoretenedor, etc.) — these are the RAG base for Phase 4 agents.

### Collections & Indices
- **D-08:** roddos_events: unique index on event_id, compound index on (event_type, timestamp_utc), 90-day TTL index on timestamp_utc
- **D-09:** roddos_events_dlq: indices for retry (next_retry, retry_count) — supports Phase 2 DLQ retry job
- **D-10:** loanbook: ESR indices (estado+dpd+score compound, morosos partial, cola_cobranza partial, chasis unique)
- **D-11:** portfolio_summaries and financial_reports: new collections created for Phase 4 pre-computed data

### Claude's Discretion
- Exact list of 30+ collections (consolidate from server.py startup + add new ones)
- Schema validation rules (JSON Schema for critical collections)
- Exact sismo_knowledge 10 rules content (derived from business context in PROJECT.md)
- Index naming conventions
- Whether to add a `--dry-run` flag to init script
- How to remove seed code from router files without breaking existing functionality

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing init & database code
- `init_mongodb_sismo.py` — Current init script to REWRITE (16 collections, basic indexes, user seeds)
- `backend/database.py` — Motor async connection setup (stays unchanged)
- `backend/server.py` lines 93-278 — Current startup index creation (30+ indexes) to MOVE into init script then REMOVE from server.py

### Existing seed data (to consolidate into init script)
- `backend/routers/loanbook.py` lines 274-332 — CATALOGO_DEFAULT (4 plans with multipliers, pricing)
- `backend/routers/gastos.py` lines 48-83 — PLAN_CUENTAS_RODDOS (36 entries, 6 categories, Alegra IDs)

### Phase 1 & 2 outputs (collections to index)
- `backend/event_models.py` — RoddosEvent fields define roddos_events collection shape
- `backend/services/event_bus_service.py` — Uses roddos_events + roddos_events_dlq collections

### Requirements
- `.planning/REQUIREMENTS.md` §MongoDB Completo (MDB) — MDB-01 through MDB-09 + TST-03

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `init_mongodb_sismo.py`: Basic structure (connect, create indexes, seed) can be expanded
- `server.py` startup: 30+ index definitions already written — move to init script
- `loanbook.py` CATALOGO_DEFAULT: Real plan data with multipliers (1.0, 2.2, 4.4)
- `gastos.py` PLAN_CUENTAS_RODDOS: Real account chart with Alegra IDs

### Established Patterns
- create_index is idempotent (MongoDB ignores if index exists)
- Upsert pattern for seed data (update_one with upsert=True)
- pymongo for sync operations (init script), Motor for async (backend)

### Integration Points
- init_mongodb_sismo.py runs standalone (CLI) before app starts
- server.py startup needs index creation code REMOVED after migration
- Router files need seed data code REMOVED (loanbook.py, gastos.py)
- Phase 4 will read from portfolio_summaries and financial_reports collections

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

*Phase: 03-mongodb-completo*
*Context gathered: 2026-03-26*
