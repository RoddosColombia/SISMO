"""Backend tests for RODDOS Contable IA"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "admin@roddos.com"
ADMIN_PASSWORD = "Admin@RODDOS2025!"
CONTADOR_EMAIL = "contador@roddos.com"
CONTADOR_PASSWORD = "Contador@2025!"


@pytest.fixture(scope="module")
def admin_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Admin login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def contador_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": CONTADOR_EMAIL, "password": CONTADOR_PASSWORD})
    assert resp.status_code == 200, f"Contador login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def contador_headers(contador_token):
    return {"Authorization": f"Bearer {contador_token}"}


# ─── AUTH ───────────────────────────────────────────────────────────────────

class TestAuth:
    """Authentication tests"""

    def test_admin_login(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["email"] == ADMIN_EMAIL
        assert data["user"]["role"] == "admin"

    def test_contador_login(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": CONTADOR_EMAIL, "password": CONTADOR_PASSWORD})
        assert resp.status_code == 200
        data = resp.json()
        assert "token" in data
        assert data["user"]["role"] == "user"

    def test_invalid_login(self):
        resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "bad@email.com", "password": "wrongpass"})
        assert resp.status_code == 401

    def test_me_endpoint(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == ADMIN_EMAIL

    def test_unauthenticated_request(self):
        resp = requests.get(f"{BASE_URL}/api/auth/me")
        assert resp.status_code == 401


# ─── ALEGRA MOCK DATA ────────────────────────────────────────────────────────

class TestAlegraEndpoints:
    """Alegra endpoints - all mocked in demo mode"""

    def test_get_accounts(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/accounts", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0

    def test_get_invoices(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/invoices", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_bills(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/bills", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_get_contacts(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/contacts", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_bank_accounts(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/bank-accounts", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_get_journal_entries(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/alegra/journal-entries", headers=admin_headers)
        assert resp.status_code == 200

    def test_accounts_require_auth(self):
        resp = requests.get(f"{BASE_URL}/api/alegra/accounts")
        assert resp.status_code == 401


# ─── SETTINGS ────────────────────────────────────────────────────────────────

class TestSettings:
    """Settings endpoints"""

    def test_get_demo_mode(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/settings/demo-mode", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "is_demo_mode" in data

    def test_get_credentials_admin(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/settings/credentials", headers=admin_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "is_demo_mode" in data

    def test_get_credentials_non_admin_forbidden(self, contador_headers):
        resp = requests.get(f"{BASE_URL}/api/settings/credentials", headers=contador_headers)
        assert resp.status_code == 403

    def test_get_default_accounts(self, admin_headers):
        resp = requests.get(f"{BASE_URL}/api/settings/default-accounts", headers=admin_headers)
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)


# ─── CHAT ────────────────────────────────────────────────────────────────────

class TestChat:
    """Chat endpoint"""

    def test_chat_message(self, admin_headers):
        resp = requests.post(f"{BASE_URL}/api/chat/message", headers=admin_headers,
                             json={"session_id": "test-session-001", "message": "Hola, ¿cómo estás?"})
        assert resp.status_code == 200
        data = resp.json()
        assert "response" in data or "message" in data or "content" in data
