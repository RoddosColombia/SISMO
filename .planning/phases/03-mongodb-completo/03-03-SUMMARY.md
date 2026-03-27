---
phase: 03-mongodb-completo
plan: "03"
subsystem: testing
tags: [tdd, mongodb, init-script, pytest, mocks]
dependency_graph:
  requires: ["03-01"]
  provides: ["TST-03"]
  affects: ["Phase 4 agents relying on init correctness"]
tech_stack:
  added: []
  patterns: ["_MockDB/_MockCollection custom mock classes (avoids MagicMock __getattr__ limitation)"]
key_files:
  created:
    - backend/tests/test_mongodb_init.py
  modified: []
decisions:
  - "Used custom _MockDB/_MockCollection classes instead of MagicMock for db object because Python 3.14 disallows setting __getattr__ on MagicMock instances"
  - "All 13 tests use a single shared mock fixture (scope=module) that runs init_all twice to test idempotency"
  - "Tests for seed data constants (CATALOGO_DEFAULT, PLAN_CUENTAS_RODDOS, SISMO_KNOWLEDGE) assert directly on the data structures without calling the DB — ensures data integrity without mock complexity"
  - "create_index call inspection captures both positional args (index keys) and keyword args (unique, expireAfterSeconds, partialFilterExpression) from a single shared _MockCollection.create_index call list"
metrics:
  duration: "~15 minutes"
  completed: "2026-03-26"
  tasks: 1
  files: 1
---

# Phase 03 Plan 03: MongoDB Init Tests Summary

**One-liner:** 13 pytest tests validating init_mongodb_sismo.py via _MockDB/_MockCollection classes — no real MongoDB connection required.

## What Was Built

Created `backend/tests/test_mongodb_init.py` with 13 tests covering all 5 ROADMAP success criteria for TST-03. Tests use custom mock classes to simulate pymongo sync operations, allowing full test coverage without requiring a MongoDB Atlas connection.

## Tests Created (13 total)

### Idempotency (2)
- `test_init_idempotent_no_errors` — Second call to init_all raises no exceptions
- `test_init_idempotent_same_result` — Both calls return identical collections/indexes counts

### roddos_events Indices (3)
- `test_roddos_events_unique_event_id` — create_index called with event_id + unique=True
- `test_roddos_events_compound_index` — create_index called with [(event_type, 1), (timestamp_utc, -1)]
- `test_roddos_events_ttl_90_days` — create_index called with timestamp_utc + expireAfterSeconds=7776000

### catalogo_planes Seed (2)
- `test_catalogo_planes_has_plans` — P39S, P52S, P78S, Contado present in CATALOGO_DEFAULT
- `test_catalogo_planes_multipliers` — Each financed plan has {semanal: 1.0, quincenal: 2.2, mensual: 4.4}

### plan_cuentas_roddos Seed (2)
- `test_plan_cuentas_no_5495` — Zero entries with alegra_id == 5495
- `test_plan_cuentas_has_5493_fallback` — At least one entry with alegra_id == 5493

### sismo_knowledge (1)
- `test_sismo_knowledge_10_rules` — Exactly 10 rules with unique rule_ids

### loanbook ESR Indices (1)
- `test_loanbook_esr_indices` — Compound (estado, dpd, score_pago) + partial morosos index

### New Collections (2)
- `test_portfolio_summaries_exists` — In COLLECTIONS + unique index on 'date'
- `test_roddos_events_dlq_exists` — In COLLECTIONS + index on 'next_retry'

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed MagicMock.__getattr__ incompatibility with Python 3.14**

- **Found during:** Task 1, first test run
- **Issue:** Python 3.14's unittest.mock raises `AttributeError: Attempting to set unsupported magic method '__getattr__'` when trying to configure dynamic attribute access on MagicMock instances. The planned approach of `db.__getattr__ = MagicMock(...)` fails.
- **Fix:** Replaced MagicMock-based db mock with custom `_MockDB` and `_MockCollection` classes that implement `__getattr__` and `__getitem__` natively, returning a shared `_MockCollection` instance for all collection accesses.
- **Files modified:** backend/tests/test_mongodb_init.py (init approach only)
- **Commit:** 216bdfb

## Known Stubs

None — tests are fully functional and verify real data constants from init_mongodb_sismo.py.

## Self-Check: PASSED

- backend/tests/test_mongodb_init.py: FOUND
- Commit 216bdfb: FOUND
- 13 tests pass: CONFIRMED (13 passed in 0.43s)
