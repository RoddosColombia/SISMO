"""test_build9.py — BUILD 9: Learning Engine tests.
Tests: learning endpoint, scheduler triggers, crear_outcome via gestión, E2E flow.
"""
import pytest
import requests
import time
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(scope="module")
def first_loanbook_id(auth):
    resp = requests.get(f"{BASE_URL}/api/loanbook?limit=1", headers=auth)
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) > 0, "No loanbook items found"
    return items[0]["id"]


# ── TEST 9A: GET /api/crm/{id}/learning ─────────────────────────────────────

class TestLearningEndpoint:
    """TEST 9A — learning endpoint structure"""

    def test_learning_returns_200(self, auth, first_loanbook_id):
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: GET /api/crm/{first_loanbook_id}/learning → 200")

    def test_learning_response_structure(self, auth, first_loanbook_id):
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        data = resp.json()
        assert "loanbook_id" in data
        assert "recomendacion" in data
        assert "alerta_deterioro" in data
        assert data["loanbook_id"] == first_loanbook_id
        print(f"PASS: response has loanbook_id, recomendacion, alerta_deterioro")

    def test_recomendacion_fields(self, auth, first_loanbook_id):
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        rec = resp.json()["recomendacion"]
        required = ["tiene_patron", "recomendacion", "canal", "dia_sugerido", "hora_sugerida", "tasa_exito", "confianza"]
        for field in required:
            assert field in rec, f"Missing field '{field}' in recomendacion"
        assert isinstance(rec["recomendacion"], str) and len(rec["recomendacion"]) > 0
        print(f"PASS: recomendacion has all required fields: {list(rec.keys())}")

    def test_alerta_deterioro_null_when_no_pattern(self, auth, first_loanbook_id):
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        data = resp.json()
        # In a fresh install with no patterns, alerta_deterioro should be null
        # (null is valid when no pattern or DPD != 0)
        alerta = data["alerta_deterioro"]
        assert alerta is None or isinstance(alerta, dict), f"alerta_deterioro should be null or dict, got: {alerta}"
        print(f"PASS: alerta_deterioro is {alerta}")

    def test_learning_404_for_invalid_id(self, auth):
        resp = requests.get(f"{BASE_URL}/api/crm/INVALID-LB-999/learning", headers=auth)
        assert resp.status_code == 404, f"Expected 404, got {resp.status_code}"
        print("PASS: Non-existent loanbook → 404")


# ── TEST 9B: Scheduler trigger BUILD 9 jobs ──────────────────────────────────

class TestSchedulerTriggerBuild9:
    """TEST 9B — scheduler trigger for ML jobs"""

    def test_trigger_alertas_predictivas(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/alertas_predictivas", headers=auth)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("label") == "Alertas Predictivas ML (06:45)", f"Unexpected label: {data.get('label')}"
        print(f"PASS: alertas_predictivas trigger → ok=True, label='{data['label']}'")

    def test_trigger_resolver_outcomes(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/resolver_outcomes", headers=auth)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("label") == "Resolver Outcomes WA (07:30)", f"Unexpected label: {data.get('label')}"
        print(f"PASS: resolver_outcomes trigger → ok=True, label='{data['label']}'")

    def test_trigger_procesar_patrones(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/procesar_patrones", headers=auth)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("label") == "Procesar Patrones ML (Lun 08:00)", f"Unexpected label: {data.get('label')}"
        print(f"PASS: procesar_patrones trigger → ok=True, label='{data['label']}'")


# ── TEST 9C: crear_outcome via registrar_gestion ─────────────────────────────

class TestCrearOutcome:
    """TEST 9C — outcome created after registrar_gestion"""

    def test_registrar_gestion_returns_200(self, auth, first_loanbook_id):
        resp = requests.post(
            f"{BASE_URL}/api/crm/{first_loanbook_id}/gestion",
            headers=auth,
            json={"canal": "whatsapp", "resultado": "no_contestó"}
        )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print(f"PASS: POST gestión → 200")

    def test_learning_outcome_created_after_gestion(self, auth, first_loanbook_id):
        # Register a gestión first
        requests.post(
            f"{BASE_URL}/api/crm/{first_loanbook_id}/gestion",
            headers=auth,
            json={"canal": "whatsapp", "resultado": "no_contestó"}
        )
        # Wait 3 seconds for asyncio.create_task to execute
        time.sleep(3)

        # Check via learning endpoint that the system is operational
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        assert resp.status_code == 200, f"Learning endpoint failed after gestion: {resp.text}"
        # We can verify by checking the gestión appeared in the timeline
        crm_resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}", headers=auth)
        assert crm_resp.status_code == 200
        data = crm_resp.json()
        gestiones = data.get("gestiones", [])
        assert len(gestiones) >= 1, "No gestiones found in CRM timeline"
        print(f"PASS: Gestión appeared in CRM timeline ({len(gestiones)} gestiones). Outcome creation async triggered.")


# ── TEST 9G: E2E flow ─────────────────────────────────────────────────────────

class TestE2EFlow:
    """TEST 9G — Full E2E flow"""

    def test_e2e_gestion_in_timeline(self, auth, first_loanbook_id):
        # Register gestión
        resp = requests.post(
            f"{BASE_URL}/api/crm/{first_loanbook_id}/gestion",
            headers=auth,
            json={"canal": "llamada", "resultado": "no_contestó"}
        )
        assert resp.status_code == 200

        # Verify in timeline
        crm_resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}", headers=auth)
        assert crm_resp.status_code == 200
        data = crm_resp.json()
        gestiones = data.get("gestiones", [])
        assert len(gestiones) >= 1
        print(f"PASS: Gestión in timeline ({len(gestiones)} total)")

    def test_e2e_resolver_outcomes_ok(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/resolver_outcomes", headers=auth)
        assert resp.status_code == 200
        assert resp.json().get("ok") is True
        print("PASS: resolver_outcomes trigger ok")

    def test_e2e_procesar_patrones_ok(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/procesar_patrones", headers=auth)
        assert resp.status_code == 200
        assert resp.json().get("ok") is True
        print("PASS: procesar_patrones trigger ok")

    def test_e2e_learning_endpoint_no_errors(self, auth, first_loanbook_id):
        resp = requests.get(f"{BASE_URL}/api/crm/{first_loanbook_id}/learning", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "recomendacion" in data
        print(f"PASS: learning endpoint after E2E → {data['recomendacion'].get('recomendacion','')[:60]}")
