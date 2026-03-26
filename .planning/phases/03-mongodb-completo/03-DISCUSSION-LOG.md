# Phase 3: MongoDB Completo - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.

**Date:** 2026-03-26
**Phase:** 03-mongodb-completo
**Areas discussed:** Init script architecture, Seed data sources

---

## Init Script Architecture

| Option | Description | Selected |
|--------|-------------|----------|
| init owns everything (Recommended) | Single source of truth for all collections, indices, seeds. server.py just connects. | ✓ |
| Split: init for setup, server for runtime | init creates collections + seeds, server ensures indices | |

**User's choice:** init owns everything

| Option | Description | Selected |
|--------|-------------|----------|
| Sync pymongo (Recommended) | Standalone CLI, no event loop | ✓ |
| Async Motor | Same driver as app, needs asyncio.run() | |

**User's choice:** Sync pymongo

---

## Seed Data Sources

| Option | Description | Selected |
|--------|-------------|----------|
| All in init_mongodb_sismo.py (Recommended) | Consolidate all seed data into init script. Remove from routers. | ✓ |
| Separate seed_data.py module | backend/seed_data.py with constants, imported by both | |

**User's choice:** All in init script

| Option | Description | Selected |
|--------|-------------|----------|
| Keep all valid, ensure 5495 absent (Recommended) | Seed real IDs, just exclude 5495, fallback 5493 | ✓ |
| Trim to exactly 28 | Curate exactly 28 IDs | |

**User's choice:** Keep all valid, ensure 5495 absent

---

## Claude's Discretion

- Exact list of 30+ collections
- Schema validation rules
- sismo_knowledge 10 rules content
- Index naming conventions
- --dry-run flag

## Deferred Ideas

None.
