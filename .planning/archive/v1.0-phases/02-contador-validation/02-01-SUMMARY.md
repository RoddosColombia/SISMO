---
phase: 02-contador-validation
plan: 01
status: complete
started: 2026-03-25T19:00:00Z
completed: 2026-03-25T19:30:00Z
---

## Summary

Rewired 4 broken action handlers in ai_chat.py from external HTTP calls (`service.request`) to direct Python imports of internal router functions. Added ROG-1 rule to AGENT_SYSTEM_PROMPT. Created 20-step smoke test covering the full accounting cycle.

## What Changed

### backend/ai_chat.py
- **ROG-1 rule** added as first line of AGENT_SYSTEM_PROMPT — agent must include real Alegra ID in every success response
- **crear_factura_venta** (line ~4003): `service.request("ventas/crear-factura")` → `from routers.ventas import crear_factura_venta`
- **registrar_pago_cartera** (line ~4067): `service.request("cartera/registrar-pago")` → `from routers.cartera import registrar_pago_cartera`
- **registrar_nomina** (line ~4144): `service.request("nomina/registrar")` → `from routers.nomina import registrar_nomina` (with Empleado model conversion)
- **registrar_ingreso_no_operacional** (line ~4326): `service.request("ingresos/no-operacional")` → `from routers.ingresos import registrar_ingreso_no_operacional`
- **crear_causacion** (line 3922): Verified still uses `request_with_verify("journals")` — no change needed

### backend/tests/test_smoke_20.py (NEW)
- 20 test methods covering full accounting cycle: auth, contact, factura venta, pago cartera, causacion, nomina, ingreso no-operacional, reconciliation
- Opt-in via SISMO_TEST_USER / SISMO_TEST_PASS env vars
- ROG-1 enforcement: every test asserts real numeric Alegra IDs

## Key Files

### Created
- `backend/tests/test_smoke_20.py` — 20-step smoke test (368 lines)

### Modified
- `backend/ai_chat.py` — 4 handlers rewired + ROG-1 rule (+40 lines, -14 lines)

## Deviations

None. All changes followed the plan exactly.

## Self-Check: PASSED

- [x] 4 handlers use import directo (verified via grep)
- [x] ROG-1 is first line of AGENT_SYSTEM_PROMPT
- [x] crear_causacion still uses request_with_verify
- [x] Smoke test has 20 test methods in 1 class
- [x] All imports present: ventas, cartera, nomina, ingresos
