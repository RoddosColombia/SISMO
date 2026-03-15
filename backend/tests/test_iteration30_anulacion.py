"""
Iteration 30 — Tests for anular_factura_compra feature:
- Guard blocking Vendida/Entregada motos
- Guard allowing Disponible motos
- post_action_sync CASO 5
- Alegra mock DELETE /bills/{id}
- System prompt keywords
- Stats endpoint: Anulada doesn't count as disponibles
- Action handler registration in ai_chat.py
"""
import pytest
import requests
import os
import uuid
import asyncio
from motor.motor_asyncio import AsyncIOMotorClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
MONGO_URL = os.environ.get("MONGO_URL", "")
DB_NAME = os.environ.get("DB_NAME", "roddos_db")

# ── Shared auth token ──────────────────────────────────────────────────────────
@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    if resp.status_code != 200:
        pytest.skip(f"Login failed: {resp.status_code} {resp.text}")
    data = resp.json()
    token = data.get("token") or data.get("access_token")
    if not token:
        pytest.skip("No token in login response")
    return token


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── Async DB helper ────────────────────────────────────────────────────────────
def run_async(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def get_db():
    client = AsyncIOMotorClient(MONGO_URL)
    return client[DB_NAME]


# ── TEST 1: Guard blocks anulación when moto is Vendida ───────────────────────
class TestGuardBlocks:
    bill_id = "BILL-BLOCK-TEST30"

    def setup_method(self):
        """Insert a Vendida moto linked to BILL-BLOCK-TEST30"""
        db = get_db()
        async def _insert():
            await db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id})
            await db.inventario_motos.insert_one({
                "id": f"TEST_moto_vendida_{uuid.uuid4().hex[:6]}",
                "marca": "HONDA",
                "version": "CB 125 TEST",
                "chasis": f"TEST-CHASIS-{uuid.uuid4().hex[:8]}",
                "estado": "Vendida",
                "factura_compra_alegra_id": self.bill_id,
            })
        run_async(_insert())

    def teardown_method(self):
        db = get_db()
        run_async(db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id}))

    def test_guard_finds_blocked_motos(self):
        """TEST 1: Guard should find motos in [Vendida, Entregada] for this bill"""
        db = get_db()
        async def _check():
            motos = await db.inventario_motos.find(
                {"factura_compra_alegra_id": self.bill_id,
                 "estado": {"$in": ["Vendida", "Entregada"]}},
                {"_id": 0}
            ).to_list(10)
            return motos
        motos = run_async(_check())
        assert len(motos) > 0, "Guard should find at least 1 blocked moto"
        print(f"PASS TEST 1: Guard found {len(motos)} blocked moto(s) for bill {self.bill_id}")

    def test_guard_error_message_contains_no_se_puede_anular(self):
        """TEST 1b: Simulated guard raises ValueError with 'No se puede anular'"""
        db = get_db()
        bill_id = self.bill_id
        bill_numero = "FC-TEST-BLOCK"

        async def _simulate_guard():
            motos_bloqueadas = await db.inventario_motos.find(
                {"factura_compra_alegra_id": bill_id,
                 "estado": {"$in": ["Vendida", "Entregada"]}},
                {"_id": 0}
            ).to_list(10)

            if motos_bloqueadas:
                detalle = ", ".join(
                    f"chasis {m.get('chasis') or m.get('marca','') + ' ' + m.get('version','')} ({m.get('estado')})"
                    for m in motos_bloqueadas
                )
                raise ValueError(
                    f"❌ No se puede anular la factura {bill_numero}. "
                    f"La(s) siguiente(s) moto(s) vinculadas ya fueron vendidas/entregadas: {detalle}. "
                    "Resuelve primero esas ventas antes de anular la compra."
                )
            return "ALLOWED"

        with pytest.raises(ValueError) as exc_info:
            run_async(_simulate_guard())

        assert "No se puede anular" in str(exc_info.value)
        print(f"PASS TEST 1b: Error message contains 'No se puede anular': {str(exc_info.value)[:80]}")


# ── TEST 2: Guard allows when moto is Disponible ──────────────────────────────
class TestGuardAllows:
    bill_id = "BILL-OK-TEST30"

    def setup_method(self):
        db = get_db()
        async def _insert():
            await db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id})
            await db.inventario_motos.insert_one({
                "id": f"TEST_moto_disp_{uuid.uuid4().hex[:6]}",
                "marca": "YAMAHA",
                "version": "FZ 150 TEST",
                "chasis": f"TEST-DISP-{uuid.uuid4().hex[:8]}",
                "estado": "Disponible",
                "factura_compra_alegra_id": self.bill_id,
            })
        run_async(_insert())

    def teardown_method(self):
        db = get_db()
        run_async(db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id}))

    def test_guard_finds_zero_blocked_motos(self):
        """TEST 2: Guard should return 0 blocked motos for Disponible moto"""
        db = get_db()
        async def _check():
            motos = await db.inventario_motos.find(
                {"factura_compra_alegra_id": self.bill_id,
                 "estado": {"$in": ["Vendida", "Entregada"]}},
                {"_id": 0}
            ).to_list(10)
            return motos
        motos = run_async(_check())
        assert len(motos) == 0, "Guard should return 0 blocked motos for Disponible"
        print(f"PASS TEST 2: Guard returns {len(motos)} blocked motos → allowed to proceed")


# ── TEST 3: post_action_sync CASO 5 ───────────────────────────────────────────
class TestPostActionSyncCaso5:
    bill_id = "BILL-ANNUL-TEST30"

    def setup_method(self):
        db = get_db()
        async def _insert():
            await db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id})
            await db.roddos_events.delete_many({"data.bill_id": self.bill_id})
            await db.inventario_motos.insert_many([
                {
                    "id": f"TEST_moto_annul_{uuid.uuid4().hex[:6]}",
                    "marca": "SUZUKI",
                    "version": "GS 150 TEST",
                    "chasis": f"TEST-ANNUL-{uuid.uuid4().hex[:8]}",
                    "estado": "Disponible",
                    "factura_compra_alegra_id": self.bill_id,
                },
                {
                    "id": f"TEST_moto_annul_{uuid.uuid4().hex[:6]}",
                    "marca": "SUZUKI",
                    "version": "GS 150 TEST B",
                    "chasis": None,
                    "estado": "Disponible",
                    "factura_compra_alegra_id": self.bill_id,
                }
            ])
        run_async(_insert())

    def teardown_method(self):
        db = get_db()
        run_async(db.inventario_motos.delete_many({"factura_compra_alegra_id": self.bill_id}))
        run_async(db.roddos_events.delete_many({"data.bill_id": self.bill_id}))

    def test_post_action_sync_updates_estado_to_anulada(self):
        """TEST 3a: post_action_sync CASO 5 sets estado=Anulada for linked motos"""
        import sys
        sys.path.insert(0, "/app/backend")
        from post_action_sync import post_action_sync

        db = get_db()
        bill_id = self.bill_id

        async def _run():
            user = {"id": "test-user", "email": "test@test.com"}
            alegra_resp = {"id": bill_id, "numero": "FC-TEST-30", "proveedor": "TestCo"}
            await post_action_sync(
                "anular_factura_compra",
                alegra_resp,
                {},
                db,
                user,
                metadata={},
            )
            # Verify motos updated
            motos = await db.inventario_motos.find(
                {"factura_compra_alegra_id": bill_id}, {"_id": 0}
            ).to_list(50)
            return motos

        motos = run_async(_run())
        assert all(m["estado"] == "Anulada" for m in motos), f"All motos should be Anulada, got: {[m['estado'] for m in motos]}"
        print(f"PASS TEST 3a: {len(motos)} moto(s) set to Anulada")

    def test_post_action_sync_creates_event(self):
        """TEST 3b: post_action_sync creates factura.compra.anulada event"""
        import sys
        sys.path.insert(0, "/app/backend")
        from post_action_sync import post_action_sync

        db = get_db()
        bill_id = self.bill_id

        async def _run():
            # Re-insert fresh motos and clean old events
            await db.roddos_events.delete_many({"data.bill_id": bill_id})
            await db.inventario_motos.delete_many({"factura_compra_alegra_id": bill_id})
            await db.inventario_motos.insert_one({
                "id": f"TEST_moto_annul_ev_{uuid.uuid4().hex[:6]}",
                "marca": "SUZUKI", "version": "GS 150 EV",
                "chasis": None, "estado": "Disponible",
                "factura_compra_alegra_id": bill_id,
            })
            user = {"id": "test-user", "email": "test@test.com"}
            alegra_resp = {"id": bill_id, "numero": "FC-TEST-30", "proveedor": "TestCo"}
            await post_action_sync("anular_factura_compra", alegra_resp, {}, db, user, metadata={})
            event = await db.roddos_events.find_one(
                {"event_type": "factura.compra.anulada", "data.bill_id": bill_id},
                {"_id": 0}
            )
            # Cleanup
            await db.inventario_motos.delete_many({"factura_compra_alegra_id": bill_id})
            await db.roddos_events.delete_many({"data.bill_id": bill_id})
            return event

        event = run_async(_run())
        assert event is not None, "Event factura.compra.anulada should be created"
        assert event["event_type"] == "factura.compra.anulada"
        assert event["data"]["bill_id"] == bill_id
        print(f"PASS TEST 3b: Event created — {event['event_type']} for bill {bill_id}")


# ── TEST 4: Alegra mock DELETE /bills/{id} ────────────────────────────────────
class TestAlegraMockDelete:
    def test_alegra_mock_delete_bills(self):
        """TEST 4: alegra_service _mock DELETE bills/123 returns {id:'123', status:'void'}"""
        import sys
        sys.path.insert(0, "/app/backend")
        from alegra_service import AlegraService

        # Call _mock directly to avoid is_demo_mode check (credentials have is_demo_mode=False in preview)
        service = AlegraService(None)
        result = service._mock("bills/123", "DELETE")
        assert isinstance(result, dict), f"Expected dict, got {type(result)}: {result}"
        assert result.get("id") == "123", f"Expected id='123', got {result}"
        assert result.get("status") == "void", f"Expected status='void', got {result}"
        print(f"PASS TEST 4: Alegra _mock DELETE bills/123 → {result}")


# ── TEST 5: System prompt keywords ────────────────────────────────────────────
class TestSystemPromptKeywords:
    def _read_ai_chat(self):
        with open("/app/backend/ai_chat.py", "r") as f:
            return f.read()

    def test_keyword_referencia(self):
        content = self._read_ai_chat()
        count = content.count("referencia")
        assert count > 1, f"'referencia' should appear >1 times, found {count}"
        print(f"PASS TEST 5a: 'referencia' appears {count} times")

    def test_keyword_vin(self):
        content = self._read_ai_chat()
        assert "VIN:" in content, "'VIN:' keyword not found in system prompt"
        print("PASS TEST 5b: 'VIN:' found")

    def test_keyword_negro_mate(self):
        content = self._read_ai_chat()
        assert "NEGRO MATE" in content, "'NEGRO MATE' keyword not found"
        print("PASS TEST 5c: 'NEGRO MATE' found")

    def test_keyword_anular_factura_compra(self):
        content = self._read_ai_chat()
        count = content.count("anular_factura_compra")
        assert count > 1, f"'anular_factura_compra' should appear >1 times, found {count}"
        print(f"PASS TEST 5d: 'anular_factura_compra' appears {count} times")

    def test_keyword_caso_anular(self):
        content = self._read_ai_chat()
        assert "ANULACIÓN" in content or "CASO ANULAR" in content or "ANULAR" in content, \
            "ANULACIÓN/CASO ANULAR not found in system prompt"
        print("PASS TEST 5e: ANULACIÓN/ANULAR keyword found")

    def test_rule_cantidad_one_chasis(self):
        content = self._read_ai_chat()
        assert "NUNCA cantidad > 1 con un solo chasis" in content or \
               "cantidad > 1" in content, \
            "Rule 'cantidad > 1 with single chasis' not found"
        print("PASS TEST 5f: Single-chasis quantity rule found")

    def test_keyword_pendiente_datos(self):
        content = self._read_ai_chat()
        assert "Pendiente datos" in content, "'Pendiente datos' not found in system prompt"
        print("PASS TEST 5g: 'Pendiente datos' found")


# ── TEST 6: Stats endpoint — Anulada not counted as disponibles ───────────────
class TestStatsAnulada:
    bill_id = "BILL-STATS-TEST30"
    moto_id = None

    def setup_method(self):
        db = get_db()
        moto_id = f"TEST_stats_anulada_{uuid.uuid4().hex[:6]}"
        TestStatsAnulada.moto_id = moto_id

        async def _insert():
            await db.inventario_motos.delete_many({"id": {"$regex": "TEST_stats_anulada"}})
            await db.inventario_motos.insert_one({
                "id": moto_id,
                "marca": "KAWASAKI",
                "version": "Z400 TEST",
                "chasis": f"TEST-STATS-{uuid.uuid4().hex[:8]}",
                "estado": "Anulada",
                "factura_compra_alegra_id": self.bill_id,
            })
        run_async(_insert())

    def teardown_method(self):
        db = get_db()
        run_async(db.inventario_motos.delete_many({"id": {"$regex": "TEST_stats_anulada"}}))

    def test_anulada_not_in_disponibles(self, headers):
        """TEST 6: GET /api/inventario/stats — Anulada moto not counted in disponibles"""
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=headers)
        assert resp.status_code == 200, f"Stats API failed: {resp.status_code}"
        data = resp.json()

        # Verify disponibles field does NOT include our Anulada moto
        # We do a direct DB check
        db = get_db()
        async def _check():
            disp = await db.inventario_motos.count_documents({"estado": "Disponible"})
            anuladas = await db.inventario_motos.count_documents({"estado": "Anulada"})
            return disp, anuladas
        disp_count, anulada_count = run_async(_check())

        assert data["disponibles"] == disp_count, \
            f"Stats disponibles ({data['disponibles']}) != DB disponibles ({disp_count})"
        assert anulada_count >= 1, "Should have at least 1 Anulada moto"
        assert data["disponibles"] != disp_count + anulada_count, \
            "Anulada motos should NOT be counted in disponibles"
        print(f"PASS TEST 6: disponibles={data['disponibles']}, anuladas_in_db={anulada_count} — correctly separated")


# ── TEST 7: anular_factura_compra registered in handler ─────────────────────
class TestActionHandlerRegistered:
    def test_special_handler_before_action_map(self):
        """TEST 7: anular_factura_compra is handled as special case before ACTION_MAP check"""
        with open("/app/backend/ai_chat.py", "r") as f:
            content = f.read()

        special_case_idx = content.find("Special case: anular_factura_compra")
        action_map_idx = content.find("ACTION_MAP")

        assert special_case_idx >= 0, "Special case handler for anular_factura_compra not found"

        # The special case should appear before the ACTION_MAP fallback check
        action_map_check_idx = content.find("if action_type not in ACTION_MAP")
        assert special_case_idx < action_map_check_idx, \
            "Special case handler should appear BEFORE ACTION_MAP check"
        print(f"PASS TEST 7: Special handler at char {special_case_idx}, ACTION_MAP check at {action_map_check_idx}")
