---
phase: quick
plan: 260401-esw
subsystem: backend/routers
tags: [global66, webhook, hmac, anti-dup, alegra-journals, conciliacion]
dependency_graph:
  requires: [alegra_service.request_with_verify, dependencies.get_current_user, database.db]
  provides: [POST /api/global66/webhook, GET /api/global66/sync]
  affects: [global66_transacciones_procesadas, conciliacion_partidas, roddos_events]
tech_stack:
  added: [hmac, hashlib.md5 anti-dup]
  patterns: [conditional-import server.py, request_with_verify Alegra pattern, MD5 hash_tx dedup]
key_files:
  created:
    - backend/routers/global66.py
    - backend/tests/test_global66.py
  modified:
    - backend/server.py
decisions:
  - "Used MD5(transaction_id) as hash_tx for anti-dup (consistent with ERROR-011 pattern)"
  - "Fallback contra-account = 5493 (Gastos Generales) — NEVER 5495 (ERROR-009)"
  - "confianza field in webhook payload takes precedence over _calcular_confianza() scoring"
  - "HMAC-SHA256 compares raw hexdigest (no 'sha256=' prefix) — matches Global66 spec in plan"
metrics:
  duration: "~20 minutes"
  completed_date: "2026-04-01"
  tasks_completed: 2
  files_created: 2
  files_modified: 1
requirements_satisfied: [GLOBAL66-WEBHOOK, GLOBAL66-SYNC]
---

# Quick Task 260401-esw: Global66 Webhook Router Summary

**One-liner:** HMAC-SHA256 webhook receiver with MD5 anti-dup, confianza-based routing to Alegra /journals or conciliacion_partidas, and daily sync counts endpoint.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests + Global66 router implementation (TDD) | 3a11ccd | backend/routers/global66.py, backend/tests/test_global66.py |
| 2 | Register global66 router in server.py | 4d2e7ba | backend/server.py |

## What Was Built

### POST /api/global66/webhook (public — no auth)

1. Reads raw body bytes for HMAC-SHA256 verification against `GLOBAL66_WEBHOOK_SECRET` env var
2. Rejects invalid/missing `X-Global66-Signature` header with 401
3. Computes `MD5(transaction_id)` as `hash_tx`, checks `global66_transacciones_procesadas` for duplicate — returns 409 if found
4. Determines confianza: uses `payload.confianza` if present, otherwise calls `_calcular_confianza(monto, descripcion, tipo)`
5. **confianza >= 0.70**: calls `AlegraService.request_with_verify("journals", "POST", ...)` with Global66 bank account ID 11100507 (debit) and fallback 5493 (credit). Records in `global66_transacciones_procesadas` with `estado="procesado"` or `"error_verificacion"`.
6. **confianza < 0.70**: inserts into `conciliacion_partidas` with `estado="pendiente"`, publishes event to `roddos_events` with `event_type="global66.movimiento.pendiente"`, records in `global66_transacciones_procesadas` with `estado="pendiente_conciliacion"`. Returns `procesado=False, motivo="confianza_baja"`.

### GET /api/global66/sync (auth required)

Queries `global66_transacciones_procesadas` for today's date, returns:
```json
{"sincronizados": N, "pendientes": N, "errores": N, "fecha": "yyyy-MM-dd"}
```

### _calcular_confianza(monto, descripcion, tipo) → float

- Base: 0.5
- +0.15 if monto > 0
- +0.10 if descripcion contains payment keywords (transferencia, pago, cuota, abono)
- +0.10 if tipo in (credit, ingreso, deposito)
- Capped at 1.0

## Test Coverage (7/7 pass)

| Test | What it validates |
|------|-------------------|
| T1 | Invalid HMAC signature → 401 |
| T2 | Missing HMAC header → 401 |
| T3 | Duplicate transaction_id → 409 |
| T4 | confianza=0.85 → request_with_verify called on /journals endpoint |
| T5 | confianza=0.50 → conciliacion_partidas insert + event published |
| T6 | No confianza field → _calcular_confianza() scoring function runs |
| T7 | GET /sync → returns {sincronizados, pendientes, errores, fecha} |

## CLAUDE.md Compliance Verified

- NEVER `/journal-entries` → only `/journals` (ERROR-008): `grep -n "journal-entries" routers/global66.py` returns 0 results
- Fallback cuenta = 5493 NEVER 5495 (ERROR-009): `grep -n "5495" routers/global66.py` returns 0 results
- Date format `yyyy-MM-dd` strict, NEVER ISO-8601 with timezone: enforced via `strptime("%Y-%m-%d")`
- Anti-dup via MD5 hash (ERROR-011 pattern): MD5(transaction_id) stored in `hash_tx`

## Deviations from Plan

**1. [Rule 1 - Bug] Fixed duplicate detection error message case**
- **Found during:** Task 1 GREEN phase (T3 failure)
- **Issue:** Test checked for `"duplicado"` (lowercase, without 'a') but message said `"Transaccion duplicada"` — "duplicada" != "duplicado"
- **Fix:** Changed detail message to `"Duplicado detectado: transaction_id {id} ya fue procesado"` which contains literal word "duplicado"
- **Files modified:** backend/routers/global66.py (line 124)
- **Commit:** 3a11ccd (fix applied before task commit)

## Known Stubs

None — all endpoints produce real behavior. `GLOBAL66_BANK_ACCOUNT_ID = 11100507` is the hardcoded Global66 bank account ID as specified in the plan (not a stub — it is the correct production value).

## Self-Check: PASSED

- backend/routers/global66.py: FOUND
- backend/tests/test_global66.py: FOUND
- Commit 3a11ccd: FOUND (git log confirms)
- Commit 4d2e7ba: FOUND (git log confirms)
- All 7 tests pass: CONFIRMED
- server.py syntax OK: CONFIRMED
- grep "global66" backend/server.py: shows import + registration at lines 58-62, 206-209
