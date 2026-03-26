# Phase 1: Models & Contracts - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Define Pydantic event models, event type catalog, and agent write permissions enforced in Python code. Every event and agent permission is validated by Python code before reaching the database or Alegra API. This is pure Python contracts — no bus refactoring, no MongoDB changes, no agent prompt changes.

</domain>

<decisions>
## Implementation Decisions

### Event Model Schema (RoddosEvent)
- **D-01:** RoddosEvent unifies both existing patterns (event_bus.py's `emit_event` and shared_state.py's `emit_state_change`) into a single Pydantic model
- **D-02:** 13 mandatory fields include both agent identity fields (source_agent, actor, target_entity) AND audit trail fields (correlation_id, version, alegra_synced)
- **D-03:** DLQEvent is a standalone model (no inheritance from RoddosEvent). It copies relevant fields and adds retry_count, next_retry, error_message, failed_at

### Event Type Catalog (EVENT_TYPES)
- **D-04:** Keep Spanish dot-notation naming convention (e.g., `factura.venta.creada`, `pago.cuota.registrado`) — consistent with existing codebase, no migration
- **D-05:** Consolidate existing ~22 types from event_bus.py (~8) and shared_state.py (~14), deduplicate, and fill gaps to reach 28 types
- **D-06:** Implement as Python `Literal` type (not StrEnum) — works directly with Pydantic validation, no `.value` needed

### Agent Permissions (WRITE_PERMISSIONS)
- **D-07:** Collection-level granularity: `WRITE_PERMISSIONS['contador'] = {'collections': [...], 'alegra_endpoints': [...]}`. Maps directly to MongoDB collections + Alegra API paths
- **D-08:** Permissions live in a new dedicated module: `backend/permissions.py`
- **D-09:** `validate_write_permission()` raises PermissionError only (no audit logging of violations in this phase)
- **D-10:** `validate_alegra_permission()` intercepts at HTTP client wrapper level (wraps httpx calls to Alegra), not at service function level. Cannot be bypassed.

### Claude's Discretion
- Exact 13 field names and types for RoddosEvent (as long as agent identity + audit trail fields are included)
- Which 6 gap event types to add to reach 28 (as long as they cover real operational needs)
- Exact permission mapping per agent (which collections/endpoints each of 4 agents gets)
- File organization for event models (backend/events.py, backend/models/events.py, etc.)
- Test structure for test_permissions.py (8 tests covering allowed + denied per agent)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Existing event patterns
- `backend/event_bus.py` — Current emit_event() shape and ~8 event types (MODULES_FOR_EVENT, EVENT_LABELS)
- `backend/services/shared_state.py` — Current emit_state_change() shape, 14 _STATE_RULES event types, cache invalidation logic

### Existing models
- `backend/models.py` — Current Pydantic models (BaseDocument, UserModel, etc.) — establishes model conventions

### Agent call sites (where permissions will be enforced)
- `backend/ai_chat.py` — execute_chat_action() runs agent writes as human user (line ~4990 emit_state_change)
- `backend/post_action_sync.py` — 5 emit_state_change calls, records source="agente_ia"
- `backend/dependencies.py` — Current auth model (get_current_user, require_admin, log_action)

### Alegra integration (where alegra_permission will wrap)
- `backend/services/alegra_service.py` — HTTP client for Alegra API, the target for permission wrapping

### Requirements
- `.planning/REQUIREMENTS.md` §Models & Contracts (MOD) — MOD-01 through MOD-06 + TST-02

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/models.py` BaseDocument: Has UUID auto-generation and to_mongo()/from_mongo() helpers — RoddosEvent can follow same pattern
- `backend/event_bus.py` MODULES_FOR_EVENT dict: Maps event types to module names — can inform the catalog design
- `backend/services/shared_state.py` _STATE_RULES: Maps 14 event types to collection+field+cache — source for consolidating event types

### Established Patterns
- Pydantic models with `class Config: json_schema_extra` for examples
- UUID string IDs (not ObjectId) for event_id
- Timestamp as `datetime.utcnow()` — existing events use this consistently
- Spanish field names in some places (estado), English in others (event_type) — mixed but functional

### Integration Points
- `validate_write_permission()` needs to be called from `execute_chat_action()` in ai_chat.py before any DB/Alegra write
- `validate_alegra_permission()` wraps httpx client used in alegra_service.py
- EVENT_TYPES Literal used as type annotation in RoddosEvent.event_type field
- 4 agents defined: Contador, CFO, RADAR, Loanbook — matches existing agent names in ai_chat.py

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

*Phase: 01-models-contracts*
*Context gathered: 2026-03-26*
