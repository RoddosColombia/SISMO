# Phase 2: Event Bus Refactoring - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 02-event-bus-refactoring
**Areas discussed:** EventBusService API, DLQ & retry strategy, Caller migration scope

---

## EventBusService API

| Option | Description | Selected |
|--------|-------------|----------|
| Publish only (Recommended) | bus.emit() only validates + persists RoddosEvent. Side effects move to handlers. | ✓ |
| Keep 3-step atomic | bus.emit() does DB update + event insert + cache bust (like emit_state_change today) | |

**User's choice:** Publish only

| Option | Description | Selected |
|--------|-------------|----------|
| backend/services/event_bus_service.py (Recommended) | New file in services/. Old event_bus.py deleted. Class-based. | ✓ |
| Replace backend/event_bus.py in-place | Rewrite event_bus.py with new class | |

**User's choice:** New file in services/

| Option | Description | Selected |
|--------|-------------|----------|
| Keep in shared_state.py as handlers (Recommended) | _STATE_RULES logic as handler functions. Clean migration path. | ✓ |
| Inline at call sites | Each caller handles own DB update + cache invalidation | |

**User's choice:** Keep in shared_state.py as handlers

| Option | Description | Selected |
|--------|-------------|----------|
| Yes, enforce in emit() (Recommended) | bus.emit() calls validate_write_permission() | ✓ |
| No, caller's responsibility | Callers must validate themselves | |

**User's choice:** Enforce in emit()

---

## DLQ & Retry Strategy

| Option | Description | Selected |
|--------|-------------|----------|
| MongoDB write failure only (Recommended) | Only DB insert failure triggers DLQ | ✓ |
| Any exception in emit() | All exceptions go to DLQ | |

**User's choice:** MongoDB write failure only

| Option | Description | Selected |
|--------|-------------|----------|
| Exponential backoff, max 5 retries (Recommended) | 5min→15min→45min→2h→6h. APScheduler every 5 min. | ✓ |
| Fixed interval, max 3 retries | Every 5 min, 3 attempts max | |

**User's choice:** Exponential backoff, max 5 retries

---

## Caller Migration Scope

| Option | Description | Selected |
|--------|-------------|----------|
| All at once (Recommended) | Replace all 14 callers in one phase. Delete old files. | ✓ |
| Staged: emit_event first, emit_state_change later | Two-step migration | |

**User's choice:** All at once

| Option | Description | Selected |
|--------|-------------|----------|
| Live MongoDB aggregation (Recommended) | get_bus_health() queries roddos_events and DLQ collections | ✓ |
| Cached metrics updated on emit | In-memory counters, lost on restart | |

**User's choice:** Live MongoDB aggregation

---

## Claude's Discretion

- EventBusService constructor signature
- Handler function signatures in shared_state.py
- RoddosEvent construction patterns at call sites
- Test structure for test_event_bus.py (11 tests)
- Bus initialization in server.py

## Deferred Ideas

None — discussion stayed within phase scope.
