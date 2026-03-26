---
phase: 02-event-bus-refactoring
plan: "01"
subsystem: event-bus
tags: [event-bus, dlq, idempotency, permissions, scheduler, health-metrics]
dependency_graph:
  requires:
    - backend/event_models.py  # RoddosEvent, DLQEvent, EVENT_LABELS — Phase 1 output
    - backend/permissions.py   # validate_write_permission — Phase 1 output
  provides:
    - backend/services/event_bus_service.py  # EventBusService.emit(), retry_dlq(), get_bus_health()
    - GET /api/health/bus                    # live bus health endpoint
    - dlq_retry APScheduler job              # 5-minute DLQ retry cadence
  affects:
    - backend/services/scheduler.py
    - backend/server.py
tech_stack:
  added:
    - pymongo.errors.DuplicateKeyError — idempotency guard in emit()
  patterns:
    - Class-based async service (EventBusService) with Motor db reference injected in constructor
    - Dead Letter Queue pattern: MongoDB write failure → DLQ insert → APScheduler retry
    - Exponential backoff: 5m / 15m / 45m / 2h / 6h (max 5 retries)
    - Lazy imports inside APScheduler job functions (established project pattern)
    - app.state for singleton service instances at server startup
key_files:
  created:
    - backend/services/event_bus_service.py  # 278 lines — EventBusService class
  modified:
    - backend/services/scheduler.py          # Added _retry_dlq_events() + dlq_retry job
    - backend/server.py                      # Added import, app.state.event_bus, GET /api/health/bus
decisions:
  - "EventBusService takes db as constructor param (not singleton module-level) — matches existing service patterns (BankReconciliationEngine, CfoAgent)"
  - "DuplicateKeyError catch in retry_dlq() also removes stale DLQ entries when event already exists in roddos_events"
  - "DLQ retry cursor uses async for iteration instead of to_list() — avoids loading all pending DLQ docs into memory at once"
metrics:
  duration: "~18 minutes"
  completed_date: "2026-03-26"
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 2
---

# Phase 2 Plan 1: EventBusService — Core Publish Gateway Summary

**One-liner:** EventBusService with permission enforcement, DuplicateKeyError idempotency, MongoDB-failure DLQ, exponential backoff retry (5/15/45/120/360 min), and live health metrics at GET /api/health/bus.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Create EventBusService with emit(), retry_dlq(), get_bus_health() | 2188ce8 | backend/services/event_bus_service.py (created, 278 lines) |
| 2 | Register DLQ retry job in scheduler and expose bus in server.py | 30bed0f | backend/services/scheduler.py, backend/server.py |

## What Was Built

### EventBusService (`backend/services/event_bus_service.py`)

**`emit(event: RoddosEvent) -> None`**
- Calls `validate_write_permission(source_agent, "roddos_events")` — raises `PermissionError` immediately (not DLQ)
- Auto-populates `event.label` from `EVENT_LABELS` if empty
- Inserts to `roddos_events`; `DuplicateKeyError` caught silently (idempotent)
- Any other exception routes to `_send_to_dlq()` — caller never sees MongoDB errors

**`_send_to_dlq(event, error) -> None`**
- Creates `DLQEvent` with `next_retry = now + 5 minutes`, `retry_count = 0`
- Inserts to `roddos_events_dlq`; failure logged and swallowed (never blocks caller)

**`retry_dlq() -> int`**
- Queries `roddos_events_dlq` for docs with `retry_count < 5` and `next_retry <= now`
- Success: re-inserts to `roddos_events`, deletes DLQ doc
- Failure: increments `retry_count`, sets `next_retry` from backoff list `[5, 15, 45, 120, 360]` min
- At retry 5: sets `permanently_failed = True`, `next_retry = None`
- Returns count of successfully re-published events

**`get_bus_health() -> dict`**
- `dlq_pending`: `count_documents({"retry_count": {"$lt": 5}})`
- `events_last_hour`: `count_documents({"timestamp_utc": {"$gte": one_hour_ago}})`
- `status`: `"healthy"` (0 pending) | `"degraded"` (1-9) | `"down"` (10+)

### Scheduler (`backend/services/scheduler.py`)
- `_retry_dlq_events()` async job added — instantiates `EventBusService(db)` and calls `retry_dlq()`
- Job registered as `id="dlq_retry"`, `interval`, `minutes=5`, `max_instances=1`

### Server (`backend/server.py`)
- `from services.event_bus_service import EventBusService` imported at module level
- `app.state.event_bus = EventBusService(db)` set in `startup()` after `start_loanbook_scheduler()`
- `GET /api/health/bus` endpoint calls `app.state.event_bus.get_bus_health()`

## Deviations from Plan

### Auto-fixed Issues

None — plan executed exactly as written.

### Minor Implementation Choices (within Claude's discretion per CONTEXT.md)

1. **DLQ retry uses `async for` cursor iteration** instead of `to_list()` — avoids loading all pending DLQ documents into memory, consistent with Motor async patterns.

2. **`retry_dlq()` also catches `DuplicateKeyError`** during re-insert and removes the stale DLQ entry — not in the plan spec but logically correct: if the event already exists in `roddos_events`, the DLQ entry is obsolete.

3. **`target_entity` reconstructed as empty string during retry** — `DLQEvent` model does not store `target_entity` (by Phase 1 design). Reconstructed event uses empty string as safe default.

## Known Stubs

None — all methods wire to real MongoDB operations. No hardcoded empty values flowing to rendering.

## Self-Check: PASSED

- `backend/services/event_bus_service.py` FOUND
- Commit 2188ce8 FOUND
- Commit 30bed0f FOUND
- `grep -c "class EventBusService"` → 1
- `grep -c "async def emit"` → 1
- `grep -c "async def retry_dlq"` → 1
- `grep -c "async def get_bus_health"` → 1
- `grep -c "async def _send_to_dlq"` → 1
- `grep "validate_write_permission"` → called inside emit()
- `grep "DuplicateKeyError"` → silent catch in emit() and retry_dlq()
- `grep "roddos_events_dlq"` → DLQ collection used in 7 places
- `grep "permanently_failed"` → max 5 retries logic present
- `grep "healthy\|degraded\|down"` → 3 status levels present
- `grep "dlq_retry" backend/services/scheduler.py` → job registered
- `grep "health/bus" backend/server.py` → endpoint registered
- `python -c "from services.event_bus_service import EventBusService; print('OK')"` → OK
