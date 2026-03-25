# Phase 2: Contador Validation — CONTEXT

## Phase Goal
El Agente Contador alcanza 8.5/10 con smoke test 20/20 pasando contra IDs reales de Alegra, clasificación >=85% de confianza, y reconciliación bancaria a 90%+ de match.

## Pre-existing Work (already done in quick tasks)
- FIX 6: tipo_identificacion obligatorio (commit 8821ad3) — CC, PPT, CE, PAS, NIT, TI
- FIX 7: servicios adicionales en factura (commit 2f42115) — incluir_soat, incluir_matricula, incluir_gps
- FIX 9: inventario post-factura already exists in ventas.py lines 434-439
- Session cleanup: AgentChatPage session_id now unique per conversation (commit 2f42115)
- Cuota fija por plan desde catálogo (commit b1eeb95) — no calcular desde precio

## Decisions

### D1: Internal Call Mechanism → Import directo
**Decision:** All action handlers in ai_chat.py call internal router functions via Python import, NOT via HTTP or service.request().
**Pattern:**
```python
from routers.ventas import crear_factura_venta, CrearFacturaVentaRequest
req = CrearFacturaVentaRequest(**payload)
result = await crear_factura_venta(req, current_user=user)
```
**Why:** Same process, no overhead, clear tracebacks, no JWT handling needed.
**Applies to:** crear_factura_venta, registrar_pago_cartera, registrar_nomina, registrar_ingreso_no_operacional.

### D2: Connect All 4 Actions → Yes
**Decision:** All 4 action types with dedicated internal endpoints get connected via import directo:
1. `crear_factura_venta` → `routers.ventas.crear_factura_venta`
2. `registrar_pago_cartera` → `routers.cartera.registrar_pago_cartera`
3. `registrar_nomina` → `routers.nomina.registrar_nomina`
4. `registrar_ingreso_no_operacional` → `routers.ingresos.registrar_ingreso_no_operacional`

**Exception:** `crear_causacion` stays as direct Alegra call via `request_with_verify()` (no internal endpoint needed — it's a simple journal POST).

### D3: Smoke Test → Hybrid
**Decision:** Automated script for mechanical steps + manual test via Agente chat for conversational flow.
- `tests/test_smoke_20.py` — pytest script with 20 steps against production Alegra (create contact, invoice, payment, receipt, reconciliation)
- Manual chat test — verify the agent parses natural language correctly and returns real IDs

### D4: ROG-1 Rule → Add to System Prompt
**Decision:** Add as rule #0 at the top of AGENT_SYSTEM_PROMPT:
"REGLA INVIOLABLE ROG-1: NUNCA reportar éxito sin incluir el ID real de Alegra (journal_id, factura_numero, o loanbook_id) en tu respuesta. Si el resultado no tiene un ID real, reporta el error exacto."

### D5: crear_causacion → request_with_verify
**Decision:** Keep direct Alegra call but ensure it uses `request_with_verify()` not `service.request()`. Verify it returns the real Alegra journal ID.

## Core Problem Statement
`ai_chat.py` line 4002: `service.request("ventas/crear-factura", "POST", payload)` sends the request to `api.alegra.com/api/v1/ventas/crear-factura` which doesn't exist. Same pattern at line 4063 for cartera. Both need to call internal Python functions directly.

## Files to Modify
- `backend/ai_chat.py` — Main file: rewire 4 action handlers, add ROG-1 rule, verify crear_causacion uses request_with_verify
- `backend/tests/test_smoke_20.py` — New: automated smoke test script

## Files NOT to Modify (already correct)
- `backend/routers/ventas.py` — Already has complete flow (contact lookup/create, services, inventory update, loanbook creation)
- `backend/routers/cartera.py` — Already has registrar_pago_cartera with journal creation
- `backend/routers/nomina.py` — Already has registrar_nomina
- `backend/routers/ingresos.py` — Already has registrar_ingreso_no_operacional

## Verification Plan
### Automated (test_smoke_20.py):
1. Login → get token
2. Create contact in Alegra → verify contact_id
3. Create invoice (moto + SOAT + matrícula + GPS) → verify factura_numero
4. Verify loanbook created → verify loanbook_id
5. Verify moto estado → "Vendida"
6. Register payment → verify journal_id
7. Verify cuota marked as pagada
8. Create causación (gasto) → verify journal_id
9. Register nómina → verify journal_id
10. Register ingreso no-operacional → verify journal_id

### Manual (via Agente chat):
- "Facturar moto Raider a Ronald Galviz, PPT 4650762, con SOAT, matrícula y GPS"
- Verify agent returns real factura FE### and loanbook LB-2026-####
- "Registrar pago de $149,900 de LB-2026-0001 por transferencia Bancolombia"
- Verify agent returns real journal_id

## Deferred Ideas
- System prompts per agent (CONT-06 scope — part of Phase 2 but separate from this sprint)
- Confidence router (CONT-07 — evaluate after action rewiring is stable)
- Reconciliation batch optimization (CONT-08 — separate task)
