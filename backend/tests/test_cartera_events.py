"""Tests for new endpoints: /api/cartera/ruta-hoy, /api/events/recent, /api/events/stats"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Auth
def get_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    if res.status_code == 200:
        data = res.json()
        return data.get("token") or data.get("access_token")
    return None

@pytest.fixture(scope="module")
def auth_headers():
    token = get_token()
    if not token:
        pytest.skip("Auth failed")
    return {"Authorization": f"Bearer {token}"}


# ── Cartera ruta-hoy ──────────────────────────────────────────────────────────

class TestRutaHoy:
    """GET /api/cartera/ruta-hoy"""

    def test_status_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_response_has_ruta_array(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy", headers=auth_headers)
        data = res.json()
        assert "ruta" in data, "Missing 'ruta' key"
        assert isinstance(data["ruta"], list), "'ruta' should be a list"

    def test_response_has_resumen(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy", headers=auth_headers)
        data = res.json()
        assert "resumen" in data, "Missing 'resumen' key"
        resumen = data["resumen"]
        for field in ["total_por_cobrar", "total_esperado", "cobrado_hoy", "vencidas", "para_hoy"]:
            assert field in resumen, f"Missing resumen field: {field}"

    def test_response_has_fecha(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy", headers=auth_headers)
        data = res.json()
        assert "fecha" in data, "Missing 'fecha' key"

    def test_ruta_items_have_required_fields(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy", headers=auth_headers)
        data = res.json()
        ruta = data["ruta"]
        if len(ruta) > 0:
            item = ruta[0]
            for field in ["loanbook_id", "codigo", "cliente_nombre", "valor", "estado", "dias_vencida", "es_hoy"]:
                assert field in item, f"Missing field in ruta item: {field}"

    def test_requires_auth(self):
        res = requests.get(f"{BASE_URL}/api/cartera/ruta-hoy")
        assert res.status_code in [401, 403], f"Expected 401/403 without auth, got {res.status_code}"


# ── Events recent ─────────────────────────────────────────────────────────────

class TestEventsRecent:
    """GET /api/events/recent"""

    def test_status_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/recent", headers=auth_headers, params={"limit": 5})
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_returns_list(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/recent", headers=auth_headers, params={"limit": 5})
        data = res.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"

    def test_limit_param(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/recent", headers=auth_headers, params={"limit": 3})
        data = res.json()
        assert len(data) <= 3, f"Expected <=3 items, got {len(data)}"

    def test_requires_auth(self):
        res = requests.get(f"{BASE_URL}/api/events/recent")
        assert res.status_code in [401, 403]


# ── Events stats ──────────────────────────────────────────────────────────────

class TestEventsStats:
    """GET /api/events/stats"""

    def test_status_200(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/stats", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"

    def test_response_fields(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/stats", headers=auth_headers)
        data = res.json()
        for field in ["total_events", "total_today", "by_type", "fecha"]:
            assert field in data, f"Missing field: {field}"

    def test_by_type_is_dict(self, auth_headers):
        res = requests.get(f"{BASE_URL}/api/events/stats", headers=auth_headers)
        data = res.json()
        assert isinstance(data["by_type"], dict), "'by_type' should be a dict"

    def test_requires_auth(self):
        res = requests.get(f"{BASE_URL}/api/events/stats")
        assert res.status_code in [401, 403]
