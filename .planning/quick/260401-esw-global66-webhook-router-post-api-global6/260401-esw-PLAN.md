---
phase: quick
plan: 260401-esw
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/routers/global66.py
  - backend/tests/test_global66.py
  - backend/server.py
autonomous: true
requirements: [GLOBAL66-WEBHOOK, GLOBAL66-SYNC]

must_haves:
  truths:
    - "POST /api/global66/webhook validates HMAC-SHA256 and rejects invalid signatures with 401"
    - "Duplicate transaction_id is rejected with 409"
    - "High-confidence movements (>=0.70) create verified journal in Alegra via request_with_verify"
    - "Low-confidence movements (<0.70) go to conciliacion_partidas as pendiente with event published"
    - "GET /api/global66/sync returns sincronizados/pendientes/errores counts for the day"
    - "Router registered in server.py with conditional import pattern"
  artifacts:
    - path: "backend/routers/global66.py"
      provides: "POST /api/global66/webhook + GET /api/global66/sync endpoints"
      exports: ["router"]
    - path: "backend/tests/test_global66.py"
      provides: "Unit tests for webhook signature, anti-dup, confianza routing, sync"
  key_links:
    - from: "backend/routers/global66.py"
      to: "alegra_service.request_with_verify"
      via: "AlegraService(db)"
      pattern: "service\\.request_with_verify.*journals.*POST"
    - from: "backend/routers/global66.py"
      to: "global66_transacciones_procesadas"
      via: "db.global66_transacciones_procesadas"
      pattern: "db\\.global66_transacciones_procesadas"
    - from: "backend/server.py"
      to: "backend/routers/global66.py"
      via: "conditional try/except import"
      pattern: "from routers import global66"
---

<objective>
Create Global66 webhook receiver and daily sync endpoint for SISMO.

Purpose: Enable automated processing of Global66 payment platform movements into Alegra accounting — high-confidence movements auto-journaled, low-confidence routed to manual conciliation with WhatsApp alert.
Output: Working POST /api/global66/webhook + GET /api/global66/sync endpoints with TDD coverage.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@backend/routers/cartera.py (anti-dup pattern + AlegraService + request_with_verify usage)
@backend/routers/nomina.py (hashlib + anti-dup + request_with_verify pattern)
@backend/server.py (conditional router registration pattern)
@backend/database.py (db object)
@backend/alegra_service.py (request_with_verify implementation)

<interfaces>
<!-- Patterns executor MUST follow — extracted from codebase -->

From backend/alegra_service.py:
```python
class AlegraService:
    def __init__(self, db): ...
    async def request_with_verify(self, endpoint: str, method: str, body: dict = None) -> dict:
        """Returns dict with _verificado=True/False flag"""
```

From backend/database.py:
```python
from motor.motor_asyncio import AsyncIOMotorClient
db = client[db_name]  # use db.collection_name directly
```

From backend/server.py conditional import pattern:
```python
try:
    from routers import global66 as global66_router
    print("[OK] global66 router loaded successfully")
except Exception as e:
    print(f"[ERROR] Failed to load global66 router: {e}")
    global66_router = None
```

Anti-dup pattern (from cartera.py):
```python
existing = await db.collection.find_one({"hash_field": hash_value})
if existing:
    raise HTTPException(status_code=409, detail="Duplicado detectado...")
```

Journal payload structure (from cartera.py):
```python
journal_payload = {
    "date": "2026-04-01",  # yyyy-MM-dd STRICT
    "observations": "...",
    "entries": [
        {"id": bank_account_id, "debit": monto, "credit": 0},
        {"id": contra_account_id, "debit": 0, "credit": monto},
    ]
}
```
</interfaces>
</context>

<tasks>

<task type="auto" tdd="true">
  <name>Task 1: Tests + Global66 router implementation</name>
  <files>backend/tests/test_global66.py, backend/routers/global66.py</files>
  <behavior>
    - Test HMAC: valid signature returns 200, invalid/missing returns 401
    - Test anti-dup: same transaction_id twice returns 409 on second call
    - Test high confianza (>=0.70): calls request_with_verify, returns _verificado=True in response
    - Test low confianza (<0.70): inserts into conciliacion_partidas with estado="pendiente", publishes event
    - Test confianza from payload: if webhook body has `confianza` float field, use it instead of scoring function
    - Test sync endpoint: returns {sincronizados, pendientes, errores} structure
  </behavior>
  <action>
    **RED phase — write tests first in backend/tests/test_global66.py:**

    Use pytest + pytest-asyncio. Mock AlegraService.request_with_verify and db collections using unittest.mock.AsyncMock.
    Follow the project pattern: `sys.path.insert(0, ...)` for imports (see existing test files).

    Tests to write:
    1. `test_webhook_rejects_invalid_signature` — POST with wrong X-Global66-Signature header returns 401
    2. `test_webhook_rejects_missing_signature` — POST without signature header returns 401
    3. `test_webhook_duplicate_transaction` — POST same transaction_id twice, second returns 409
    4. `test_webhook_high_confianza_creates_journal` — payload with confianza=0.85, mock request_with_verify returns {"id": 123, "_verificado": True}, verify journal created
    5. `test_webhook_low_confianza_routes_to_conciliacion` — payload with confianza=0.50, verify insert into conciliacion_partidas and event published
    6. `test_webhook_confianza_from_scoring` — payload WITHOUT confianza field, monto=500000 + descripcion with keyword "transferencia", verify scoring function runs
    7. `test_sync_returns_counts` — GET /api/global66/sync returns correct structure

    **GREEN phase — implement backend/routers/global66.py:**

    ```
    router = APIRouter(prefix="/global66", tags=["global66"])
    ```

    **POST /webhook (NO auth — public webhook endpoint):**
    1. Read raw body bytes for HMAC verification
    2. Compute HMAC-SHA256(raw_body, GLOBAL66_WEBHOOK_SECRET) and compare with X-Global66-Signature header (use hmac.compare_digest)
    3. Parse JSON: extract transaction_id, tipo, monto, descripcion, fecha
    4. Anti-dup: compute MD5(transaction_id), check db.global66_transacciones_procesadas for existing hash_tx
    5. Determine confianza: use payload.get("confianza") if present (float 0-1), otherwise call _calcular_confianza(monto, descripcion)
    6. _calcular_confianza logic: start at 0.5, +0.15 if monto > 0, +0.10 if descripcion contains payment keywords (transferencia, pago, cuota, abono), +0.10 if tipo in (credit, ingreso, deposito). Cap at 1.0.
    7. If confianza >= 0.70:
       - Build journal_payload with Global66 bank account ID 11100507 (debit) and fallback cuenta 5493 (credit — Gastos Generales per CLAUDE.md). Date = fecha from webhook in yyyy-MM-dd format.
       - Call service.request_with_verify("journals", "POST", journal_payload)
       - If _verificado: insert into global66_transacciones_procesadas with hash_tx, transaction_id, alegra_journal_id, confianza, estado="procesado"
       - If NOT _verificado: insert with estado="error_verificacion"
       - Return 200 with _verificado flag
    8. If confianza < 0.70:
       - Insert into conciliacion_partidas: {origen: "global66", transaction_id, monto, descripcion, fecha, confianza, estado: "pendiente", fecha_registro: utcnow}
       - Insert event into roddos_events: {event_type: "global66.movimiento.pendiente", transaction_id, monto, confianza, alerta_whatsapp: True}
       - Insert into global66_transacciones_procesadas with estado="pendiente_conciliacion"
       - Return 200 with procesado=False, motivo="confianza_baja"
    9. Always return HTTP 200 (webhook best practice — never 4xx/5xx except auth failures and dups)

    **GET /sync (requires auth — Depends(get_current_user)):**
    1. Query global66_transacciones_procesadas for today's date (fecha_registro starts with today yyyy-MM-dd)
    2. Count by estado: procesado=sincronizados, pendiente_conciliacion=pendientes, error_verificacion=errores
    3. Return {sincronizados: N, pendientes: N, errores: N, fecha: today}

    CRITICAL reminders:
    - NEVER use /journal-entries — always /journals (ERROR-008)
    - Fallback account ALWAYS 5493, NEVER 5495 (ERROR-009)
    - Date format yyyy-MM-dd STRICT, NEVER ISO-8601 with timezone
    - Anti-dup via MD5(transaction_id) in hash_tx field (ERROR-011 pattern)
  </action>
  <verify>
    <automated>cd backend && python -m pytest tests/test_global66.py -v -x 2>&1 | tail -30</automated>
  </verify>
  <done>All 7 tests pass. Router handles HMAC validation, anti-dup, confianza routing (high->Alegra, low->conciliacion), and sync endpoint returns correct counts.</done>
</task>

<task type="auto">
  <name>Task 2: Register global66 router in server.py</name>
  <files>backend/server.py</files>
  <action>
    Add conditional import block for global66 router in server.py, following the exact pattern used for cartera_router, nomina_router, admin_kb_router:

    After the `admin_kb_router` try/except block (around line 58), add:
    ```python
    try:
        from routers import global66 as global66_router
        print("[OK] global66 router loaded successfully")
    except Exception as e:
        print(f"[ERROR] Failed to load global66 router: {e}")
        global66_router = None
    ```

    Then after the admin_kb_router registration block (around line 208), add:
    ```python
    if global66_router:
        app.include_router(global66_router.router, prefix=PREFIX)
    else:
        print("[WARN] global66_router not loaded, skipping registration")
    ```

    Verify server.py still loads correctly by running a quick syntax check.
  </action>
  <verify>
    <automated>cd backend && python -c "import ast; ast.parse(open('server.py').read()); print('server.py syntax OK')"</automated>
  </verify>
  <done>global66 router conditionally imported and registered in server.py. Server syntax validates. Route available at /api/global66/webhook (POST) and /api/global66/sync (GET).</done>
</task>

</tasks>

<verification>
1. `cd backend && python -m pytest tests/test_global66.py -v` — all tests pass
2. `cd backend && python -c "import ast; ast.parse(open('server.py').read())"` — no syntax errors
3. `grep -n "global66" backend/server.py` — shows import + registration
4. `grep -n "request_with_verify" backend/routers/global66.py` — confirms Alegra integration pattern
5. `grep -n "5495" backend/routers/global66.py` — must return 0 results (NEVER use 5495)
6. `grep -n "journal-entries" backend/routers/global66.py` — must return 0 results (NEVER use /journal-entries)
</verification>

<success_criteria>
- POST /api/global66/webhook validates HMAC, deduplicates by MD5(transaction_id), routes high-confianza to Alegra journals and low-confianza to conciliacion_partidas
- GET /api/global66/sync returns daily reconciliation counts
- All tests pass with mocked AlegraService and db
- Router registered in server.py with conditional import pattern
- No forbidden patterns: no /journal-entries, no ID 5495, no ISO dates with timezone
</success_criteria>

<output>
After completion, create `.planning/quick/260401-esw-global66-webhook-router-post-api-global6/260401-esw-SUMMARY.md`
</output>
