# Phase 1: Models & Contracts - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 01-models-contracts
**Areas discussed:** Event model schema, Event type catalog, Agent identity & permissions

---

## Event Model Schema

| Option | Description | Selected |
|--------|-------------|----------|
| Unify both (Recommended) | One RoddosEvent model that covers both emit_event and emit_state_change use cases | ✓ |
| Replace event_bus only | RoddosEvent replaces event_bus.py shape, shared_state keeps its own shape | |

**User's choice:** Unify both
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Agent identity fields | source_agent, actor, target_entity | |
| Audit trail fields | correlation_id, version, alegra_synced | |
| Both agent + audit | Include agent identity AND audit trail fields in the 13 mandatory | ✓ |

**User's choice:** Both agent + audit
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Extend RoddosEvent (Recommended) | DLQEvent inherits from RoddosEvent, adds retry_count, next_retry, error_message, failed_at | |
| Separate model | DLQEvent is standalone, no inheritance | ✓ |

**User's choice:** Separate model
**Notes:** User explicitly chose standalone DLQEvent over inheritance

---

## Event Type Catalog

| Option | Description | Selected |
|--------|-------------|----------|
| Keep Spanish dot-notation (Recommended) | Consistent with existing: factura.venta.creada | ✓ |
| Switch to English snake_case | invoice.sale.created — cleaner but requires migration | |

**User's choice:** Keep Spanish dot-notation
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Consolidate existing + fill gaps | Merge ~22 types, deduplicate, add missing to reach 28 | ✓ |
| Start fresh with clean taxonomy | Design all 28 from scratch | |

**User's choice:** Consolidate existing + fill gaps
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| Literal type (Recommended) | EVENT_TYPES = Literal[...] — works with Pydantic directly | ✓ |
| StrEnum class | class EventType(StrEnum) — more discoverable, IDE autocomplete | |

**User's choice:** Literal type
**Notes:** None

---

## Agent Identity & Permissions

| Option | Description | Selected |
|--------|-------------|----------|
| Collection-level (Recommended) | WRITE_PERMISSIONS['contador'] = {'collections': [...], 'alegra_endpoints': [...]} | ✓ |
| Operation-level | More fine-grained: 'loanbooks.update_estado': True | |

**User's choice:** Collection-level
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| New backend/permissions.py (Recommended) | Dedicated module for permissions | ✓ |
| In backend/models.py | Co-locate with Pydantic models | |

**User's choice:** New backend/permissions.py
**Notes:** None

| Option | Description | Selected |
|--------|-------------|----------|
| PermissionError + audit log (Recommended) | Raise PermissionError AND log violation to roddos_events | |
| PermissionError only | Just raise exception, caller handles logging | ✓ |

**User's choice:** PermissionError only
**Notes:** User chose simpler enforcement — no audit logging of permission violations in this phase

| Option | Description | Selected |
|--------|-------------|----------|
| HTTP client wrapper (Recommended) | Wrap httpx calls to Alegra — can't be bypassed | ✓ |
| Service function level | Check in each alegra_service.py method | |

**User's choice:** HTTP client wrapper
**Notes:** None

---

## Claude's Discretion

- Exact 13 field names/types for RoddosEvent
- Which 6 gap event types to add
- Exact permission mapping per agent
- File organization for models
- Test structure for test_permissions.py

## Deferred Ideas

None — discussion stayed within phase scope.
