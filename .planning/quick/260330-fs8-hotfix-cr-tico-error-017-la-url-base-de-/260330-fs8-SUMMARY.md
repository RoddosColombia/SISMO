---
type: quick
id: 260330-fs8
title: "Hotfix ERROR-017: Corregir URL base de Alegra en todo el codebase"
completed: "2026-03-30T16:28:26Z"
duration_min: 15
tasks_completed: 2
tasks_total: 3
commit: dec35ef
---

# Quick Task 260330-fs8: Hotfix Alegra Base URL

## One-liner

Eliminated all `app.alegra.com/api/r1` wrong URLs across 6 files, consolidating to a single `ALEGRA_BASE_URL` constant imported from `alegra_service.py`.

## Tasks Executed

| # | Task | Status | Commit |
|---|------|--------|--------|
| 1 | Fix wrong URLs and consolidate all Alegra base URL references | DONE | dec35ef |
| 2 | Run verification greps and confirm clean state | DONE | (no code change) |
| 3 | Live verification — GET /invoices from Alegra API | SKIPPED — no credentials in env | — |

## Files Modified

| File | Change |
|------|--------|
| `backend/routers/alegra_webhooks.py` | Removed `ALEGRA_BASE = "https://app.alegra.com/api/r1"` and `ALEGRA_API_V1 = "https://api.alegra.com/api/v1"`. Added `from alegra_service import ALEGRA_BASE_URL`. Updated 3 usages. |
| `backend/migrations/migrate_inventario_tvs.py` | Replaced `ALEGRA_BASE = "https://app.alegra.com/api/r1"` with `try/except ImportError` pattern importing `ALEGRA_BASE_URL`. Updated 2 usages. |
| `backend/services/dian_service.py` | Added `from alegra_service import ALEGRA_BASE_URL`. Replaced 2 hardcoded `"https://app.alegra.com/api/r1/bills"` with `f"{ALEGRA_BASE_URL}/bills"`. |
| `backend/routers/auditoria.py` | Added `from alegra_service import ALEGRA_BASE_URL`. Replaced 2 inline `base_url = "https://api.alegra.com/api/v1"` with `base_url = ALEGRA_BASE_URL`. |
| `backend/routers/conciliacion.py` | Added `from alegra_service import ALEGRA_BASE_URL`. Replaced 2 inline hardcoded URLs in f-strings. |
| `backend/services/bank_reconciliation.py` | Added `from alegra_service import ALEGRA_BASE_URL`. Replaced `base_url = "https://api.alegra.com/api/v1"` with `base_url = ALEGRA_BASE_URL`. |

## Verification Results

| Check | Result |
|-------|--------|
| `grep -rn "app.alegra.com/api/r1" backend/` | PASS — 0 results |
| `grep -rn "ALEGRA_BASE_URL\s*=" backend/` | 2 results — `alegra_service.py:16` (canonical) + `migrate_inventario_tvs.py:32` (fallback inside `except ImportError` block — intentional) |
| `grep -rn "api/r1" backend/` | PASS — 0 results |
| `grep -rn "isoformat" backend/alegra_service.py` | PASS — 0 results |
| Live GET /invoices | SKIPPED — ALEGRA_EMAIL/ALEGRA_TOKEN not available in execution environment |

## Deviations from Plan

None. The try/except fallback in `migrate_inventario_tvs.py` is exactly what the plan specified for standalone script execution.

## Auth Gate — Task 3

**Task 3 (Live verification)** was not executed because `ALEGRA_EMAIL` and `ALEGRA_TOKEN` are not available as environment variables in the execution context and no `.env` file was found.

**To verify manually:**
```bash
export ALEGRA_EMAIL=your@email.com
export ALEGRA_TOKEN=your_token
python -c "
import httpx, base64, os
creds = base64.b64encode(f\"{os.environ['ALEGRA_EMAIL']}:{os.environ['ALEGRA_TOKEN']}\".encode()).decode()
r = httpx.get('https://api.alegra.com/api/v1/invoices?limit=5', headers={'Authorization': f'Basic {creds}'}, timeout=15)
print(f'Status: {r.status_code}, Invoices: {len(r.json()) if isinstance(r.json(), list) else len(r.json().get(\"data\", []))}')
"
```

Expected: HTTP 200 with at least 1 invoice.

## Known Stubs

None.

## Self-Check: PASSED

All 6 modified files verified present. Commit dec35ef verified in git log.
