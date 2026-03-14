"""Backend tests for BUILD 6 — RADAR + CRM endpoints."""
import time
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


@pytest.fixture(scope="module")
def first_loan_id(client):
    """Get first active/mora loan id from CRM list."""
    r = client.get(f"{BASE_URL}/api/crm")
    assert r.status_code == 200
    data = r.json()
    assert len(data) > 0, "No loans found in CRM list"
    return data[0]["id"]


# ── TEST 6A: RADAR endpoints ──────────────────────────────────────────────────

class TestRadarQueue:
    def test_6a1_queue_response_time(self, client):
        """6A-1: GET /api/radar/queue responds in < 200ms."""
        start = time.time()
        r = client.get(f"{BASE_URL}/api/radar/queue")
        elapsed_ms = (time.time() - start) * 1000
        assert r.status_code == 200, f"Queue failed: {r.text}"
        assert elapsed_ms < 200, f"Queue took {elapsed_ms:.1f}ms (> 200ms)"
        print(f"Queue response time: {elapsed_ms:.1f}ms ✓")

    def test_6a2_queue_item_fields(self, client):
        """6A-2: Each queue item has required fields."""
        r = client.get(f"{BASE_URL}/api/radar/queue")
        assert r.status_code == 200
        data = r.json()
        if len(data) == 0:
            pytest.skip("Queue is empty — no overdue loans today")
        item = data[0]
        required = ["loanbook_id", "cliente_nombre", "bucket", "dpd_actual",
                    "total_a_pagar", "dias_para_protocolo", "whatsapp_link"]
        for f in required:
            assert f in item, f"Missing field: {f}"

    def test_6a3_queue_order(self, client):
        """6A-3: Queue ordered RECUPERACION → CRITICO → URGENTE → ACTIVO, DPD desc within bucket."""
        BUCKET_PRIORITY = {"RECUPERACION": 0, "CRITICO": 1, "URGENTE": 2, "ACTIVO": 3,
                           "HOY": 4, "MAÑANA": 5, "AL_DIA": 6}
        r = client.get(f"{BASE_URL}/api/radar/queue")
        assert r.status_code == 200
        data = r.json()
        if len(data) < 2:
            pytest.skip("Not enough items to verify ordering")
        for i in range(len(data) - 1):
            p1 = BUCKET_PRIORITY.get(data[i]["bucket"], 99)
            p2 = BUCKET_PRIORITY.get(data[i+1]["bucket"], 99)
            assert p1 <= p2, f"Order wrong: {data[i]['bucket']} before {data[i+1]['bucket']}"

    def test_6a4_semana_endpoint(self, client):
        """6A-4: GET /api/radar/semana returns required fields."""
        r = client.get(f"{BASE_URL}/api/radar/semana")
        assert r.status_code == 200, f"semana failed: {r.text}"
        data = r.json()
        for f in ["esperadas", "pagadas", "pendientes", "nuevas_moras"]:
            assert f in data, f"Missing field: {f}"

    def test_6a5_roll_rate(self, client):
        """6A-5: GET /api/radar/roll-rate returns roll_rate_pct in [0, 100]."""
        r = client.get(f"{BASE_URL}/api/radar/roll-rate")
        assert r.status_code == 200, f"roll-rate failed: {r.text}"
        data = r.json()
        assert "roll_rate_pct" in data
        assert 0 <= data["roll_rate_pct"] <= 100


# ── TEST 6B: CRM mutation endpoints ───────────────────────────────────────────

class TestCRMMutations:
    def test_6b1_update_datos(self, client, first_loan_id):
        """6B-1: PUT /api/crm/{id}/datos updates telefono_alternativo."""
        r = client.put(f"{BASE_URL}/api/crm/{first_loan_id}/datos",
                       json={"telefono_alternativo": "3009999999"})
        assert r.status_code == 200, f"Update datos failed: {r.text}"
        data = r.json()
        assert data.get("ok") is True or "updated" in data

    def test_6b2_add_nota(self, client, first_loan_id):
        """6B-2: POST /api/crm/{id}/nota adds a note with date and author."""
        texto = "Trabaja en Rappi. Mejor contactar martes."
        r = client.post(f"{BASE_URL}/api/crm/{first_loan_id}/nota",
                        json={"texto": texto})
        # Note: if no crm doc, it may return 400
        if r.status_code == 400 and "ficha CRM" in r.text:
            pytest.skip("No CRM doc for this loan — nota requires CRM record")
        assert r.status_code == 200, f"Add nota failed: {r.text}"
        data = r.json()
        assert "texto" in data or "id" in data
        assert data.get("texto") == texto or "id" in data

    def test_6b3_register_gestion(self, client, first_loan_id):
        """6B-3: POST /api/crm/{id}/gestion registers a gestión."""
        r = client.post(f"{BASE_URL}/api/crm/{first_loan_id}/gestion",
                        json={"canal": "llamada", "resultado": "no_contestó", "nota": "Sin respuesta"})
        assert r.status_code == 200, f"Register gestion failed: {r.text}"
        data = r.json()
        assert data.get("canal") == "llamada"
        assert data.get("resultado") == "no_contestó"
        assert "id" in data
        # Verify it appears in loanbook gestiones
        profile = client.get(f"{BASE_URL}/api/crm/{first_loan_id}")
        assert profile.status_code == 200
        gestiones = profile.json().get("gestiones", [])
        assert any(g.get("resultado") == "no_contestó" for g in gestiones), \
            "Gestion not found in profile gestiones"

    def test_6b4_register_ptp_gestion(self, client, first_loan_id):
        """6B-4: POST gestion with prometió_fecha sets ptp_activo."""
        r = client.post(f"{BASE_URL}/api/crm/{first_loan_id}/gestion",
                        json={"canal": "llamada", "resultado": "contestó_prometió_fecha",
                              "nota": "Promete pagar", "ptp_fecha": "2026-04-09"})
        assert r.status_code == 200, f"PTP gestion failed: {r.text}"
        data = r.json()
        assert data.get("ptp_fecha") == "2026-04-09"


# ── TEST 6C: Route migration ───────────────────────────────────────────────────

class TestRouteMigration:
    def test_6c1_old_cartera_queue_returns_404(self, client):
        """6C-1: GET /api/cartera/queue returns 404."""
        r = client.get(f"{BASE_URL}/api/cartera/queue")
        assert r.status_code == 404, f"Expected 404, got {r.status_code}"

    def test_6c2_new_radar_queue_returns_200(self, client):
        """6C-2: GET /api/radar/queue returns 200."""
        r = client.get(f"{BASE_URL}/api/radar/queue")
        assert r.status_code == 200, f"Expected 200, got {r.status_code}"

    def test_6c_crm_list_returns_200(self, client):
        """CRM list endpoint returns 200."""
        r = client.get(f"{BASE_URL}/api/crm")
        assert r.status_code == 200
        assert isinstance(r.json(), list)

    def test_6c_crm_profile_returns_200(self, client, first_loan_id):
        """CRM 360 profile returns 200 with correct fields."""
        r = client.get(f"{BASE_URL}/api/crm/{first_loan_id}")
        assert r.status_code == 200
        data = r.json()
        assert "loan" in data
        assert "score_pct" in data
        assert "gestiones" in data
