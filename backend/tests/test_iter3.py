"""
Iteration 3 backend tests: Login, Dashboard alerts, Agent suggestions, 
2FA status, Audit log, Webhooks, Module pages
"""
import pytest
import requests
import os

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

ADMIN_EMAIL = "contabilidad@roddos.com"
ADMIN_PASS = "Admin@RODDOS2025!"
USER_EMAIL = "compras@roddos.com"
USER_PASS = "Contador@2025!"


@pytest.fixture(scope="module")
def admin_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
    assert res.status_code == 200
    data = res.json()
    if data.get("requires_2fa"):
        pytest.skip("2FA enabled - skip admin auth tests")
    return data["token"]


@pytest.fixture(scope="module")
def user_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS})
    assert res.status_code == 200
    data = res.json()
    if data.get("requires_2fa"):
        pytest.skip("2FA enabled - skip user auth tests")
    return data["token"]


@pytest.fixture(scope="module")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="module")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}


# ── LOGIN ──────────────────────────────────────────────────────────────────
class TestLogin:
    def test_admin_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASS})
        assert res.status_code == 200
        data = res.json()
        assert "token" in data or data.get("requires_2fa")
        print(f"Admin login OK: {data.get('user', {}).get('role', 'N/A')}")

    def test_user_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": USER_EMAIL, "password": USER_PASS})
        assert res.status_code == 200
        data = res.json()
        assert "token" in data or data.get("requires_2fa")
        print(f"User login OK: {data.get('user', {}).get('role', 'N/A')}")

    def test_invalid_login(self):
        res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "bad@test.com", "password": "wrong"})
        assert res.status_code == 401


# ── DASHBOARD ALERTS ───────────────────────────────────────────────────────
class TestDashboard:
    def test_alerts(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/dashboard/alerts", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Dashboard alerts count: {len(data)}")
        if data:
            assert "title" in data[0] or "message" in data[0] or "tipo" in data[0]

    def test_kpis_via_alegra(self, admin_headers):
        # KPIs come from alegra invoices
        res = requests.get(f"{BASE_URL}/api/alegra/invoices", headers=admin_headers)
        assert res.status_code == 200
        print(f"KPI source (invoices) status: OK")


# ── AGENT SUGGESTIONS ─────────────────────────────────────────────────────
class TestAgent:
    def test_suggestions(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/agent/memory/suggestions", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Agent suggestions count: {len(data)}")


# ── 2FA STATUS ────────────────────────────────────────────────────────────
class TestTwoFA:
    def test_2fa_status_admin(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/auth/2fa/status", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert "totp_enabled" in data
        print(f"2FA status for admin: {data}")


# ── AUDIT LOG ─────────────────────────────────────────────────────────────
class TestAuditLog:
    def test_audit_log(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/audit-logs", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Audit log entries: {len(data)}")


# ── WEBHOOKS ──────────────────────────────────────────────────────────────
class TestWebhooks:
    def test_webhook_register(self, admin_headers):
        payload = {"url": "https://test.example.com/webhook", "events": ["invoice.created"]}
        res = requests.post(f"{BASE_URL}/api/settings/webhooks/register", json=payload, headers=admin_headers)
        assert res.status_code in [200, 201, 202, 400]
        print(f"Webhook register response: {res.status_code}")

    def test_webhook_status(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/settings/webhooks/status", headers=admin_headers)
        assert res.status_code == 200
        print(f"Webhook status: {res.json()}")


# ── MODULES ───────────────────────────────────────────────────────────────
class TestModules:
    def test_inventario_auteco(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/inventario/motos", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        assert isinstance(data, list)
        print(f"Inventario Auteco motos: {len(data)}")

    def test_inventario_stats(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/inventario/stats", headers=admin_headers)
        assert res.status_code == 200
        data = res.json()
        print(f"Inventario stats: {data}")

    def test_facturas_venta(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/alegra/invoices", headers=admin_headers)
        assert res.status_code == 200
        print(f"Facturas venta status: OK")

    def test_facturas_compra(self, admin_headers):
        res = requests.get(f"{BASE_URL}/api/alegra/bills", headers=admin_headers)
        assert res.status_code == 200

    def test_nomina_via_alegra(self, admin_headers):
        # Nomina is frontend-only UI, check that impuestos config (backend) works
        res = requests.get(f"{BASE_URL}/api/impuestos/config", headers=admin_headers)
        assert res.status_code == 200
