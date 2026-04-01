---
task_id: 260401-fq4
type: quick
description: "Admin seed endpoint — POST /api/admin/run-seed + GET /api/admin/seed-status"
status: complete
completed_date: "2026-04-01"
duration_minutes: 15
tasks_completed: 2
files_created: 2
files_modified: 1
commits:
  - hash: c682de1
    message: "feat(260401-fq4): add admin_seeds router + register in server.py"
  - hash: 567c8ed
    message: "test(260401-fq4): add 3 tests for admin seed endpoints"
key_files:
  created:
    - backend/routers/admin_seeds.py
    - backend/tests/test_admin_seeds.py
  modified:
    - backend/server.py
tech_stack:
  patterns:
    - FastAPI APIRouter with require_admin dependency
    - Motor async upsert pattern (update_one with upsert=True)
    - sys.path.insert to import from repo root (init_mongodb_sismo.py)
    - Conditional try/except import + include_router in server.py
    - FastAPI dependency_overrides for test isolation
---

# Quick Task 260401-fq4 Summary

## One-liner

Admin-only HTTP endpoints to re-seed MongoDB knowledge_base and plan_cuentas_roddos collections at runtime without SSH, using idempotent Motor upserts from SISMO_KNOWLEDGE and PLAN_CUENTAS_RODDOS arrays.

## Tasks Completed

| # | Task | Commit | Files |
|---|------|--------|-------|
| 1 | Create admin_seeds.py router + register in server.py | c682de1 | backend/routers/admin_seeds.py, backend/server.py |
| 2 | Tests for admin seed endpoints (3 tests, all pass) | 567c8ed | backend/tests/test_admin_seeds.py |

## What Was Built

**backend/routers/admin_seeds.py:**
- `POST /admin/run-seed` — accepts `{seed_name: "knowledge_base" | "plan_cuentas" | "all"}`, runs Motor upserts, returns `{seed_name, documentos_cargados, status, mensaje}`
- `GET /admin/seed-status` — returns `{sismo_knowledge: N, plan_cuentas_roddos: N}` document counts
- Both endpoints require `require_admin` dependency
- sys.path trick imports SISMO_KNOWLEDGE (37 docs) and PLAN_CUENTAS_RODDOS (26 docs) from repo root init_mongodb_sismo.py
- Invalid seed_name raises HTTP 400 with detail message listing valid values

**backend/server.py:**
- Conditional try/except import block for `admin_seeds_router` (same pattern as admin_kb_router, lines ~63-68)
- Conditional `app.include_router` right after admin_kb registration (line ~218-220)

**backend/tests/test_admin_seeds.py:**
- T1: POST run-seed knowledge_base → documentos_cargados == 37, status ok, update_one called 37 times
- T2: GET seed-status → returns sismo_knowledge=37 and plan_cuentas_roddos=26
- T3: POST run-seed invalid_name → HTTP 400

## Test Results

```
3 passed in 1.72s
```

All 3 tests pass with full mock isolation (qrcode/cryptography/pdfplumber stubs, AsyncMock for Motor operations, FastAPI dependency_overrides for require_admin).

## Deviations from Plan

None — plan executed exactly as written.

The only discovery was that `patch("routers.admin_seeds.require_admin", ...)` doesn't bypass FastAPI DI correctly; fixed by using `app.dependency_overrides[dependencies.require_admin]` instead. This is standard FastAPI testing practice, not a deviation from the plan's intent.

## Known Stubs

None — all endpoints wire to real Motor async operations. Mock only in tests.

## Self-Check: PASSED

- `backend/routers/admin_seeds.py` — FOUND
- `backend/tests/test_admin_seeds.py` — FOUND
- Commit c682de1 — FOUND
- Commit 567c8ed — FOUND
- 3 tests pass — CONFIRMED
