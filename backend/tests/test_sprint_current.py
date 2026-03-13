"""
Sprint tests: Login, Dashboard, AI Chat, Loanbook, Cartera, Settings, execute-action
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "contabilidad@roddos.com"
ADMIN_PASS = "Admin@RODDOS2025!"
USER_EMAIL = "compras@roddos.com"
USER_PASS = "Contador@2025!"


@pytest.fixture(scope="module")
def admin_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert r.status_code == 200, f"Admin login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def user_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS})
    assert r.status_code == 200, f"User login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# --- AUTH ---
class TestAuth:
    def test_admin_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data
        assert data["user"]["role"] == "admin"

    def test_user_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS})
        assert r.status_code == 200
        data = r.json()
        assert "token" in data

    def test_invalid_login(self):
        r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "wrong@test.com", "password": "wrong"})
        assert r.status_code in [400, 401, 422]


# --- DASHBOARD ---
class TestDashboard:
    def test_dashboard_alegra_invoices(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/alegra/invoices", headers=admin_headers,
                         params={"date_start": "2025-10-01", "date_end": "2025-10-31"})
        assert r.status_code == 200

    def test_dashboard_alegra_bills(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/alegra/bills", headers=admin_headers,
                         params={"date_start": "2025-10-01", "date_end": "2025-10-31"})
        assert r.status_code == 200


# --- AI CHAT ---
class TestAIChat:
    def test_chat_general_question(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={"message": "¿Qué puedes hacer?", "session_id": "test-session-1", "conversation_history": []},
            headers=admin_headers,
            timeout=30
        )
        assert r.status_code == 200

    def test_chat_causar_egreso(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={"message": "Causar arrendamiento por $3.000.000 para octubre 2025", "session_id": "test-session-2", "conversation_history": []},
            headers=admin_headers,
            timeout=45
        )
        assert r.status_code == 200

    def test_chat_retencion(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/chat/message",
            json={"message": "¿Cuánto es la retención en la fuente de $5.000.000 en servicios?", "session_id": "test-session-3", "conversation_history": []},
            headers=admin_headers,
            timeout=30
        )
        assert r.status_code == 200


# --- EXECUTE ACTION ---
class TestExecuteAction:
    def test_registrar_entrega_not_found_returns_400(self, admin_headers):
        """Bug fix: registrar_entrega should return 400 not 422"""
        r = requests.post(
            f"{BASE_URL}/api/chat/execute-action",
            json={
                "action": "registrar_entrega",
                "payload": {"loanbook_id": "test-id-inexistente", "fecha_entrega": "2026-03-13"}
            },
            headers=admin_headers,
            timeout=15
        )
        assert r.status_code == 400, f"Expected 400, got {r.status_code}: {r.text}"
        data = r.json()
        assert "no encontrado" in data.get("detail", "").lower() or "not found" in data.get("detail", "").lower()


# --- LOANBOOK ---
class TestLoanbook:
    def test_loanbook_list(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/loanbook", headers=admin_headers)
        assert r.status_code == 200

    def test_loanbook_accessible_by_user(self, user_headers):
        r = requests.get(f"{BASE_URL}/api/loanbook", headers=user_headers)
        assert r.status_code in [200, 403]


# --- CARTERA ---
class TestCartera:
    def test_cartera_semanal(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/cartera/semanal", headers=admin_headers)
        assert r.status_code == 200

    def test_cartera_clients_no_500(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/cartera/clientes", headers=admin_headers)
        assert r.status_code != 500

    def test_cartera_cola_remota(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/cartera/cola-remota", headers=admin_headers)
        assert r.status_code == 200


# --- SETTINGS ---
class TestSettings:
    def test_get_mercately_settings(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
        assert r.status_code == 200

    def test_save_mercately_settings(self, admin_headers):
        r = requests.post(
            f"{BASE_URL}/api/settings/mercately",
            json={"api_key": "test_key_123", "api_secret": "test_secret_456"},
            headers=admin_headers
        )
        assert r.status_code in [200, 201]

    def test_alegra_credentials(self, admin_headers):
        r = requests.get(f"{BASE_URL}/api/settings/credentials", headers=admin_headers)
        assert r.status_code == 200
