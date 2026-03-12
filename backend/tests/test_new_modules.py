"""Backend tests for new RODDOS modules: execute-action, inventario, presupuesto"""
import pytest
import requests
import os

def _get_base_url():
    url = os.environ.get("REACT_APP_BACKEND_URL", "")
    if not url:
        env_path = "/app/frontend/.env"
        with open(env_path) as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    url = line.split("=", 1)[1].strip()
    return url.rstrip("/")

BASE_URL = _get_base_url()

ADMIN_EMAIL = "admin@roddos.com"
ADMIN_PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def admin_headers():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200
    token = resp.json()["token"]
    return {"Authorization": f"Bearer {token}"}


# ─── PRIVACY ───────────────────────────────────────────────────────────────

class TestPrivacy:
    """Unauthenticated requests must return 401"""

    def test_inventario_stats_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/inventario/stats")
        assert resp.status_code == 401

    def test_inventario_motos_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/inventario/motos")
        assert resp.status_code == 401

    def test_presupuesto_requires_auth(self):
        resp = requests.get(f"{BASE_URL}/api/presupuesto")
        assert resp.status_code == 401

    def test_chat_execute_action_requires_auth(self):
        resp = requests.post(f"{BASE_URL}/api/chat/execute-action", json={"action": "test", "params": {}})
        assert resp.status_code == 401


# ─── CHAT EXECUTE ACTION ───────────────────────────────────────────────────

class TestChatExecuteAction:
    """Test AI chat execute-action endpoint"""

    def test_execute_action_returns_success(self, admin_headers):
        resp = requests.post(f"{BASE_URL}/api/chat/execute-action", headers=admin_headers,
                             json={"action": "crear_factura_venta", "payload": {"contact": {"id": 1}, "items": [{"id": 1, "quantity": 1, "price": 100000}]}})
        assert resp.status_code == 200
        data = resp.json()
        assert "success" in data
        assert data["success"] is True

    def test_execute_action_unknown_action(self, admin_headers):
        resp = requests.post(f"{BASE_URL}/api/chat/execute-action", headers=admin_headers,
                             json={"action": "unknown_action_xyz", "payload": {}})
        # Should return 200 with success or 400/422
        assert resp.status_code in [200, 400, 422]


# ─── INVENTARIO ───────────────────────────────────────────────────────────

class TestInventario:
    """Inventario Auteco endpoints"""

    def test_get_inventario_stats(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data
        assert "disponibles" in data

    def test_get_inventario_motos(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/inventario/motos", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ─── PRESUPUESTO ──────────────────────────────────────────────────────────

class TestPresupuesto:
    """Presupuesto (budget) endpoints"""
    created_id = None

    def test_get_presupuesto(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/presupuesto", headers=admin_headers, params={"ano": 2025})
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_save_presupuesto_item(self, admin_headers):
        resp = requests.post(f"{BASE_URL}/api/presupuesto", headers=admin_headers, json=[{
            "mes": "enero",
            "ano": 2025,
            "categoria": "Ingresos",
            "concepto": "TEST_Ventas motos",
            "valor_presupuestado": 10000000
        }])
        assert resp.status_code == 200
        data = resp.json()
        assert "guardados" in data.get("message", "")

    def test_presupuesto_persisted(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/presupuesto", headers=admin_headers, params={"ano": 2025})
        assert resp.status_code == 200
        items = resp.json()
        conceptos = [i.get("concepto") for i in items]
        assert "TEST_Ventas motos" in conceptos

    def test_delete_presupuesto_item(self, admin_headers):
        if not TestPresupuesto.created_id:
            pytest.skip("No item created")
        resp = requests.delete(f"{BASE_URL}/api/presupuesto/{TestPresupuesto.created_id}", headers=admin_headers)
        assert resp.status_code in [200, 204]
