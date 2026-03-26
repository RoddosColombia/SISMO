# Phase 2: Event Bus Refactoring - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Replace event_bus.py and emit_state_change() with a single EventBusService class. All event publishing flows through bus.emit() with idempotency (duplicate event_id rejection), DLQ for failed writes, and a health metrics endpoint. The old event_bus.py file is deleted and emit_state_change() is removed from shared_state.py. All ~14 callers migrated.

</domain>

<decisions>
## Implementation Decisions

### EventBusService API
- **D-01:** bus.emit() is publish-only — validates RoddosEvent, persists to roddos_events collection. No DB updates, no cache invalidation in emit(). Side effects stay in handlers.
- **D-02:** EventBusService lives in `backend/services/event_bus_service.py` as a new class-based async service. Old `backend/event_bus.py` gets deleted entirely.
- **D-03:** DB updates and cache invalidation from _STATE_RULES stay in `backend/services/shared_state.py` as handler functions. Callers do: `bus.emit()` then call handler if needed. shared_state.py becomes the side-effect handler layer.
- **D-04:** bus.emit() enforces agent permissions — calls `validate_write_permission(source_agent, 'roddos_events')` before persisting. Centralized enforcement point, cannot be bypassed.
- **D-05:** bus.emit() rejects duplicate event_ids silently (DuplicateKeyError caught, not propagated). Idempotent by design.

### DLQ & Retry Strategy
- **D-06:** DLQ triggers on MongoDB write failure only (network error, timeout). Since bus.emit() is publish-only, this is the only I/O it does. Validation/permission errors are raised immediately, not sent to DLQ.
- **D-07:** Exponential backoff with max 5 retries: 5min → 15min → 45min → 2h → 6h. After 5 retries, mark as permanently_failed. APScheduler job checks DLQ every 5 minutes.
- **D-08:** DLQ events stored in `roddos_events_dlq` collection using the DLQEvent model from Phase 1.

### Caller Migration
- **D-09:** All ~14 callers migrated at once — both emit_event (4 callers in loanbook.py) and emit_state_change (10 callers across post_action_sync.py, crm_service.py, loanbook_scheduler.py, loanbook.py). Clean cut, no staged migration.
- **D-10:** After migration, `backend/event_bus.py` is deleted. `emit_state_change()` is removed from shared_state.py. Searching codebase for old imports returns zero results.

### Health Metrics
- **D-11:** get_bus_health() runs live MongoDB aggregation queries on roddos_events and roddos_events_dlq. Returns: dlq_pending count, events_last_hour count, status (healthy/degraded/down).

### Claude's Discretion
- EventBusService constructor signature (db param, singleton pattern, etc.)
- Exact handler function signatures in shared_state.py
- How callers construct RoddosEvent (inline or helper factory)
- Test structure for test_event_bus.py (11 tests per TST-01)
- Whether to add a bus initialization step in server.py startup

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Phase 1 outputs (foundation contracts)
- `backend/event_models.py` — RoddosEvent, DLQEvent, EventType, EVENT_TYPES_LIST used by EventBusService
- `backend/permissions.py` — validate_write_permission() called by bus.emit()

### Existing code to replace
- `backend/event_bus.py` — Old emit_event() + MODULES_FOR_EVENT + EVENT_LABELS. DELETE this file.
- `backend/services/shared_state.py` — emit_state_change() + _STATE_RULES to refactor. Keep cache/read functions, remove emit_state_change.

### Callers to migrate (all files importing old functions)
- `backend/routers/loanbook.py` — 4x emit_event calls (lines ~768, 1233, 1244, 1451) + 1x emit_state_change (line ~1529)
- `backend/post_action_sync.py` — 5x emit_state_change calls (cases 1, 2, 3, 4, 6)
- `backend/services/crm_service.py` — 1x emit_state_change (line ~213)
- `backend/services/loanbook_scheduler.py` — 2x emit_state_change (lines ~168, 175)
- `backend/ai_chat.py` — 1x emit_state_change (line ~4990)

### Requirements
- `.planning/REQUIREMENTS.md` §Bus de Eventos (BUS) — BUS-01 through BUS-08 + TST-01

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `backend/event_models.py` RoddosEvent: 13-field Pydantic model with EventType Literal validation — used directly by bus.emit()
- `backend/event_models.py` DLQEvent: Standalone model with retry metadata — used for DLQ persistence
- `backend/permissions.py` validate_write_permission(): Permission enforcement — called inside bus.emit()
- `backend/services/shared_state.py` _STATE_RULES: Maps event types to collection/field/cache rules — refactored into handler functions
- `backend/services/shared_state.py` cache functions (get_loanbook_snapshot, etc.): Cache read layer stays intact

### Established Patterns
- All event operations are async (awaited in all callers)
- emit_event pattern: `await emit_event(db, source, event_type, payload, alegra_synced)`
- emit_state_change pattern: `await emit_state_change(db, event_type, entity_id, new_state, actor, metadata)`
- APScheduler already used for background jobs (loanbook_scheduler.py) — DLQ retry job follows same pattern
- MongoDB operations use Motor async driver throughout

### Integration Points
- EventBusService instantiated in server.py startup (or as singleton accessible via db reference)
- APScheduler needs new job registration for DLQ retry (scheduler.py)
- get_bus_health() exposed via health endpoint in server.py
- All 5 caller files need import changes + call pattern updates

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

*Phase: 02-event-bus-refactoring*
*Context gathered: 2026-03-26*
