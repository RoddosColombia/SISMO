# Roadmap: SISMO v2.0 BUILD 24 -- Cimientos Definitivos

## Overview

BUILD 24 establishes the structural foundations for SISMO to scale as a fintech platform: a typed event bus with DLQ, agent write permissions enforced in code, 30+ MongoDB collections with ESR indices and seeded data, differentiated system prompts with confidence-based routing, pre-computed portfolio summaries, and expanded CI/CD with pytest. Five phases execute in strict dependency order (A through E), each delivering a complete, testable capability that the next phase builds upon.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Models & Contracts** - Pydantic event models, event type catalog, and agent write permissions enforced in Python code
- [ ] **Phase 2: Event Bus Refactoring** - EventBusService with DLQ and retry replaces fake event_bus.py; all callers migrated
- [ ] **Phase 3: MongoDB Completo** - 30+ collections with ESR indices, schema validation, and seeded production data
- [ ] **Phase 4: Agents, Router, Scheduler & Pipeline** - Differentiated system prompts, confidence router, portfolio summaries, financial reports, and RAG
- [ ] **Phase 5: GitHub Production-Ready** - Expanded CI/CD with pytest, smoke test, anti-pending check, Dependabot, and updated docs

## Phase Details

### Phase 1: Models & Contracts
**Goal**: Every event and agent permission is validated by Python code before reaching the database or Alegra API
**Depends on**: Nothing (first phase)
**Requirements**: MOD-01, MOD-02, MOD-03, MOD-04, MOD-05, MOD-06, TST-02
**Success Criteria** (what must be TRUE):
  1. Constructing a RoddosEvent with missing or invalid fields raises a Pydantic ValidationError
  2. Only the 28 event types defined in EVENT_TYPES are accepted; any other string is rejected at model level
  3. An agent attempting to write to a collection or Alegra endpoint not in its WRITE_PERMISSIONS gets a PermissionError before any I/O happens
  4. All 8 permission tests pass (test_permissions.py) covering each agent's allowed and denied operations
**Plans**: 3 plans

Plans:
- [ ] 01-01-PLAN.md -- Event models (RoddosEvent, DLQEvent) and EVENT_TYPES catalog
- [ ] 01-02-PLAN.md -- Agent write permissions (WRITE_PERMISSIONS, validate functions)
- [ ] 01-03-PLAN.md -- Permission and model tests (test_permissions.py, 8 tests)

### Phase 2: Event Bus Refactoring
**Goal**: All event publishing flows through a single EventBusService with idempotency, DLQ, and health metrics -- the old event_bus.py and emit_state_change() no longer exist
**Depends on**: Phase 1
**Requirements**: BUS-01, BUS-02, BUS-03, BUS-04, BUS-05, BUS-06, BUS-07, BUS-08, TST-01
**Success Criteria** (what must be TRUE):
  1. bus.emit() persists an event with status='processed' and rejects duplicate event_ids silently
  2. A failing emit sends the event to DLQ instead of blocking the caller's operation
  3. get_bus_health() returns live metrics (dlq_pending, events_last_hour, status) from MongoDB
  4. Searching the codebase for "from backend.event_bus import" or "emit_state_change" returns zero results
  5. All 11 event bus tests pass (test_event_bus.py)
**Plans**: TBD

### Phase 3: MongoDB Completo
**Goal**: MongoDB has all 30+ collections with ESR indices, schema validation, and seeded production data -- the single source of truth for SISMO's data layer
**Depends on**: Phase 2
**Requirements**: MDB-01, MDB-02, MDB-03, MDB-04, MDB-05, MDB-06, MDB-07, MDB-08, MDB-09, TST-03
**Success Criteria** (what must be TRUE):
  1. Running init_mongodb_sismo.py twice produces identical results (idempotent) with no errors on the second run
  2. roddos_events has a unique index on event_id plus a compound index on (event_type, timestamp_utc) and a 90-day TTL
  3. catalogo_planes contains real weekly/biweekly/monthly plans with correct multipliers (1.0, 2.2, 4.4)
  4. plan_cuentas_roddos contains 28 real account IDs, ID 5495 is absent, and fallback defaults to 5493
  5. All 13 MongoDB init tests pass (test_mongodb_init.py)
**Plans**: TBD

### Phase 4: Agents, Router, Scheduler & Pipeline
**Goal**: Each agent operates with its own system prompt, the router delegates with measurable confidence, and the CFO reads pre-computed summaries instead of calling Alegra directly
**Depends on**: Phase 3
**Requirements**: AGT-01, AGT-02, AGT-03, AGT-04, SCH-01, SCH-02, SCH-03, SCH-04, TST-04, TST-06
**Success Criteria** (what must be TRUE):
  1. Sending "cual es el saldo de cartera" routes to CFO agent (not Contador) with confidence >= 0.7
  2. Sending an ambiguous message with confidence < 0.7 triggers a clarification question instead of routing
  3. compute_portfolio_summary() produces a snapshot document in portfolio_summaries with today's date
  4. CFO agent's get_portfolio_data_for_cfo() reads from portfolio_summaries before falling back to Alegra
  5. build_agent_prompt() injects relevant sismo_knowledge rules into the system prompt for any agent
**Plans**: TBD

### Phase 5: GitHub Production-Ready
**Goal**: Every push is validated by CI (pytest + smoke test + anti-pending check), dependencies are monitored, and documentation reflects BUILD 24
**Depends on**: Phase 4
**Requirements**: GIT-01, GIT-02, GIT-03, GIT-04, GIT-05, GIT-06, TST-05
**Success Criteria** (what must be TRUE):
  1. A push to any branch triggers ci.yml which runs pytest, checks for no "pending" status markers, and runs smoke test
  2. /api/health/smoke returns checks for collections, bus health, indices, and catalogo presence -- not just "ok"
  3. dependabot.yml exists and monitors both pip and npm dependencies
  4. README.md contains no references to "Emergent" or "BUILD 18" and reflects BUILD 24 architecture
  5. All 6 smoke tests pass (test_smoke_build24.py)
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Models & Contracts | 0/3 | Planned | - |
| 2. Event Bus Refactoring | 0/TBD | Not started | - |
| 3. MongoDB Completo | 0/TBD | Not started | - |
| 4. Agents, Router, Scheduler & Pipeline | 0/TBD | Not started | - |
| 5. GitHub Production-Ready | 0/TBD | Not started | - |
