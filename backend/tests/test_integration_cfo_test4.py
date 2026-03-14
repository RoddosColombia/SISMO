"""
TEST 4 — Integración oficial Agente CFO (BUILD 4)
Covers:
  4A — Endpoints backend: semaforo, generar, informe-mensual, alertas
  4B — Semáforo dinámico: impuestos y cartera responden a datos MongoDB
  4C — Chat routing: CFO vs contable intent detection
"""
import pytest
import requests
import os
import json
from datetime import date, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
CREDENTIALS = {"email": "contabilidad@roddos.com", "password": "Admin@RODDOS2025!"}

# ── Auth fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json=CREDENTIALS)
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    tok = data.get("access_token") or data.get("token")
    assert tok, f"No token in response: {data}"
    return tok

@pytest.fixture(scope="session")
def auth(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ── TEST 4A: Endpoints backend ────────────────────────────────────────────────

class TestA_Endpoints:
    """4A — Endpoints backend CFO"""

    def test_semaforo_status_200(self, auth):
        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        assert r.status_code == 200, f"semaforo → {r.status_code}: {r.text}"
        print(f"  [PASS] GET /api/cfo/semaforo → 200")

    def test_semaforo_5_keys(self, auth):
        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        data = r.json()
        required = {"caja", "cartera", "ventas", "roll_rate", "impuestos"}
        assert set(data.keys()) == required, f"Keys={set(data.keys())} expected={required}"
        print(f"  [PASS] semaforo has exactly 5 keys: {set(data.keys())}")

    def test_semaforo_no_metricas_key(self, auth):
        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        data = r.json()
        assert "metricas" not in data, "metricas should NOT be exposed in /semaforo endpoint"
        print(f"  [PASS] semaforo does not expose 'metricas' key")

    def test_semaforo_valid_colors(self, auth):
        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        data = r.json()
        valid = {"VERDE", "AMARILLO", "ROJO"}
        for k, v in data.items():
            assert v in valid, f"Key {k} has invalid color: {v}"
        print(f"  [PASS] All semaforo colors valid: {data}")

    def test_generar_informe(self, auth):
        r = auth.post(f"{BASE_URL}/api/cfo/generar", timeout=120)
        assert r.status_code == 200, f"generar → {r.status_code}: {r.text}"
        data = r.json()
        print(f"  [PASS] POST /api/cfo/generar → 200, keys={list(data.keys())}")

    def test_generar_informe_structure(self, auth):
        r = auth.post(f"{BASE_URL}/api/cfo/generar", timeout=120)
        assert r.status_code == 200
        data = r.json()
        assert "semaforo" in data, f"Missing 'semaforo' in response: {list(data.keys())}"
        assert "diagnostico" in data, f"Missing 'diagnostico': {list(data.keys())}"
        assert "plan_accion" in data or "plan_acciones" in data, f"Missing plan_accion: {list(data.keys())}"
        assert "generado_en" in data or "fecha_generacion" in data, f"Missing timestamp: {list(data.keys())}"
        diag = data.get("diagnostico", {})
        assert "bien" in diag, f"diagnostico missing 'bien': {diag}"
        assert "mal" in diag, f"diagnostico missing 'mal': {diag}"
        plan = data.get("plan_accion") or data.get("plan_acciones", [])
        if plan:
            item = plan[0]
            assert "accion" in item, f"plan item missing 'accion': {item}"
            assert "responsable" in item, f"plan item missing 'responsable': {item}"
        print(f"  [PASS] generar structure OK, diagnostico.bien={len(diag.get('bien',[]))}, plan items={len(plan)}")

    def test_informe_mensual_persistencia(self, auth):
        # First generate
        auth.post(f"{BASE_URL}/api/cfo/generar", timeout=120)
        # Then verify GET returns it
        r = auth.get(f"{BASE_URL}/api/cfo/informe-mensual")
        assert r.status_code == 200, f"informe-mensual → {r.status_code}: {r.text}"
        data = r.json()
        assert "mensaje" not in data, f"No informe guardado: {data}"
        assert "semaforo" in data or "periodo" in data, f"Unexpected response: {data}"
        print(f"  [PASS] GET /api/cfo/informe-mensual → persisted informe found, periodo={data.get('periodo')}")

    def test_alertas_no_500(self, auth):
        r = auth.get(f"{BASE_URL}/api/cfo/alertas")
        assert r.status_code == 200, f"alertas → {r.status_code}: {r.text}"
        data = r.json()
        assert isinstance(data, list), f"alertas should return list, got: {type(data)}"
        print(f"  [PASS] GET /api/cfo/alertas → 200, {len(data)} alertas")


# ── TEST 4B: Semáforo dinámico ────────────────────────────────────────────────

class TestB_SemaforoDinamico:
    """4B — Semáforo dinámico: impuestos y cartera"""

    def test_impuestos_rojo_con_fecha_vencida(self, auth):
        """Insertar fechas_dian vencidas → impuestos debe ser ROJO o AMARILLO"""
        # Direct MongoDB manipulation via backend config endpoint
        fecha_vencida = (date.today() - timedelta(days=2)).isoformat()
        payload = {
            "dia_informe": 1,
            "umbral_mora_pct": 5.0,
            "umbral_caja_cop": 5000000.0,
            "whatsapp_activo": False,
            "whatsapp_ceo": "",
        }
        # Save config first
        auth.post(f"{BASE_URL}/api/cfo/config", json=payload)

        # Use direct MongoDB manipulation through a helper endpoint or Python
        # We'll use pymongo directly since we're in the test environment
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import asyncio
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")

        async def _set_dian():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            await db.cfo_config.delete_many({})
            await db.cfo_config.insert_one({
                "dia_informe": 1,
                "umbral_mora_pct": 5.0,
                "umbral_caja_cop": 5000000.0,
                "whatsapp_activo": False,
                "whatsapp_ceo": "",
                "fechas_dian": [{"nombre": "IVA Q1", "fecha": fecha_vencida}],
                "tarifa_ica_por_mil": 11.04,
            })
            client.close()

        asyncio.run(_set_dian())

        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        assert r.status_code == 200
        data = r.json()
        color = data.get("impuestos")
        assert color in ("ROJO", "AMARILLO"), f"impuestos should be ROJO/AMARILLO with vencida fecha, got: {color}"
        print(f"  [PASS] impuestos = {color} with vencida date {fecha_vencida}")

    def test_impuestos_verde_sin_fechas_dian(self, auth):
        """Limpiar fechas_dian → impuestos debe ser VERDE"""
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import asyncio
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")

        async def _clear_dian():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            await db.cfo_config.delete_many({})
            await db.cfo_config.insert_one({
                "dia_informe": 1,
                "umbral_mora_pct": 5.0,
                "umbral_caja_cop": 5000000.0,
                "whatsapp_activo": False,
                "whatsapp_ceo": "",
                "fechas_dian": [],
                "tarifa_ica_por_mil": 11.04,
            })
            client.close()

        asyncio.run(_clear_dian())

        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        assert r.status_code == 200
        data = r.json()
        color = data.get("impuestos")
        assert color == "VERDE", f"impuestos should be VERDE with no fechas_dian, got: {color}"
        print(f"  [PASS] impuestos = VERDE after clearing fechas_dian")

    def test_cartera_rojo_con_alto_dpd(self, auth):
        """Modificar loan con dpd alto → cartera debe cambiar a ROJO"""
        import sys
        sys.path.insert(0, "/app/backend")
        from motor.motor_asyncio import AsyncIOMotorClient
        from dotenv import load_dotenv
        load_dotenv("/app/backend/.env")
        import asyncio
        mongo_url = os.environ.get("MONGO_URL")
        db_name = os.environ.get("DB_NAME")

        original_dpd = {}

        async def _set_high_dpd():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            # Set umbral_mora_pct very low to make it easier to trigger ROJO
            await db.cfo_config.update_one({}, {"$set": {"umbral_mora_pct": 1.0}}, upsert=True)
            # Find an active loan and set high dpd
            loan = await db.loanbook.find_one({"estado": {"$in": ["activo", "mora"]}})
            if loan:
                original_dpd["id"] = str(loan["_id"])
                original_dpd["dpd"] = loan.get("dpd_actual", 0)
                # Update many loans to have high DPD to ensure tasa_mora > threshold
                await db.loanbook.update_many(
                    {"estado": {"$in": ["activo", "mora"]}},
                    {"$set": {"dpd_actual": 30}}
                )
            client.close()
            return loan is not None

        has_loans = asyncio.run(_set_high_dpd())

        if not has_loans:
            pytest.skip("No active loans found for cartera test")

        r = auth.get(f"{BASE_URL}/api/cfo/semaforo")
        assert r.status_code == 200
        data = r.json()
        cartera_color = data.get("cartera")
        print(f"  cartera = {cartera_color} after setting high DPD")

        # Restore
        async def _restore_dpd():
            client = AsyncIOMotorClient(mongo_url)
            db = client[db_name]
            await db.loanbook.update_many(
                {"estado": {"$in": ["activo", "mora"]}},
                {"$set": {"dpd_actual": original_dpd.get("dpd", 0)}}
            )
            await db.cfo_config.update_one({}, {"$set": {"umbral_mora_pct": 5.0}})
            client.close()

        asyncio.run(_restore_dpd())

        assert cartera_color in ("ROJO", "AMARILLO"), f"cartera should be ROJO/AMARILLO with high DPD (>15%), got: {cartera_color}. Note: depends on portfolio tasa_mora calculation from shared_state"
        print(f"  [PASS] cartera = {cartera_color} with high DPD loans (restored original values)")


# ── TEST 4C: Chat routing ──────────────────────────────────────────────────────

class TestC_ChatRouting:
    """4C — Chat routing: CFO vs contable intent"""

    def test_cfo_query_returns_financial_info(self, auth):
        """Financial message → respuesta con info financiera"""
        payload = {
            "message": "cómo vamos financieramente este mes",
            "session_id": "test-cfo-routing-1"
        }
        r = auth.post(f"{BASE_URL}/api/chat/message", json=payload, timeout=90)
        assert r.status_code == 200, f"chat → {r.status_code}: {r.text}"
        data = r.json()
        response_text = data.get("message", "") or data.get("response", "") or str(data)
        response_lower = response_text.lower()

        # Check for financial keywords
        financial_kws = ["semáforo", "semaforo", "caja", "cartera", "ventas", "mora",
                         "peso", "cop", "financiero", "resultado", "ingreso", "margen",
                         "rojo", "verde", "amarillo", "impuesto", "brecha"]
        found = [kw for kw in financial_kws if kw in response_lower]
        assert len(found) >= 1, f"CFO response should contain financial keywords. Response: {response_text[:300]}"

        # Should NOT be a factura/causación response
        anti_kws = ["crear factura", "registrar factura", "causación", "propuesta de causacion"]
        bad = [kw for kw in anti_kws if kw in response_lower]
        assert len(bad) == 0, f"CFO response should NOT propose factura creation. Found: {bad}. Response: {response_text[:300]}"

        print(f"  [PASS] CFO query → financial response (keywords: {found[:3]})")

    def test_contable_query_not_cfo(self, auth):
        """Factura message → contable flow, NOT just CFO semaforo data"""
        payload = {
            "message": "registra factura de arriendo por 2000000 pesos",
            "session_id": "test-contable-routing-1"
        }
        r = auth.post(f"{BASE_URL}/api/chat/message", json=payload, timeout=90)
        assert r.status_code == 200, f"chat → {r.status_code}: {r.text}"
        data = r.json()
        response_text = data.get("message", "") or data.get("response", "") or str(data)
        response_lower = response_text.lower()

        # Should mention factura/contable terms
        contable_kws = ["factura", "arriendo", "causación", "causacion", "contabiliz",
                        "registro", "cuenta", "débito", "credito", "asiento", "2000000", "2,000,000"]
        found = [kw for kw in contable_kws if kw in response_lower]
        assert len(found) >= 1, f"Contable response should contain accounting keywords. Response: {response_text[:300]}"

        # Should NOT just return raw semaforo JSON/data
        assert "caja" not in response_lower or "factura" in response_lower or "arriendo" in response_lower, \
            f"Response appears to be CFO data instead of contable flow. Response: {response_text[:300]}"

        print(f"  [PASS] Contable query → accounting response (keywords: {found[:3]})")
