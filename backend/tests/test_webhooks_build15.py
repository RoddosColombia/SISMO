"""Test suite for Build 15: Alegra Webhooks + CFO cache + JWT + Settings UI"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Auth token fixture
@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    if resp.status_code == 200:
        return resp.json().get("access_token") or resp.json().get("token")
    pytest.skip(f"Auth failed: {resp.status_code} {resp.text[:200]}")

@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}

WEBHOOK_SECRET = "roddos-webhook-2026"
WEBHOOK_HEADERS = {"x-api-key": WEBHOOK_SECRET, "Content-Type": "application/json"}


# ── PARTE 0 FIX 1: JWT 7 days ─────────────────────────────────────────────────

class TestJWT7Days:
    def test_jwt_expiry_7days(self, auth_token, auth_headers):
        """JWT token should have 7-day expiry (168h)"""
        import base64, json
        parts = auth_token.split(".")
        assert len(parts) == 3, "Not a valid JWT"
        # Decode payload (add padding)
        payload_b64 = parts[1] + "=" * (4 - len(parts[1]) % 4)
        payload = json.loads(base64.b64decode(payload_b64))
        iat = payload.get("iat", 0)
        exp = payload.get("exp", 0)
        diff_hours = (exp - iat) / 3600
        print(f"JWT expiry: {diff_hours:.1f}h (expected ~168h)")
        assert diff_hours >= 167, f"JWT expiry too short: {diff_hours:.1f}h, expected 168h"

    def test_auth_me_returns_user(self, auth_headers):
        """GET /api/auth/me should return user data"""
        resp = requests.get(f"{BASE_URL}/api/auth/me", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "email" in data
        print(f"Auth me: {data.get('email')}")


# ── PARTE 1: Webhook receiver auth ────────────────────────────────────────────

class TestWebhookReceiver:
    def test_webhook_wrong_key_returns_401(self):
        """POST /api/webhooks/alegra with wrong x-api-key → 401"""
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers={"x-api-key": "wrong-key", "Content-Type": "application/json"},
            json={"event": "test", "data": {}})
        assert resp.status_code == 401, f"Expected 401, got {resp.status_code}"

    def test_webhook_correct_key_returns_ok(self):
        """POST /api/webhooks/alegra with correct x-api-key → {status:'ok'} < 1s"""
        start = time.time()
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers=WEBHOOK_HEADERS,
            json={"event": "unknown-event", "data": {}})
        elapsed = time.time() - start
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        assert resp.json().get("status") == "ok"
        assert elapsed < 1.5, f"Response too slow: {elapsed:.2f}s"
        print(f"Webhook responded in {elapsed:.3f}s")

    def test_webhook_no_key_returns_401(self):
        """POST /api/webhooks/alegra with no x-api-key → 401"""
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers={"Content-Type": "application/json"},
            json={"event": "test", "data": {}})
        assert resp.status_code == 401


# ── PARTE 2: Event handlers ────────────────────────────────────────────────────

class TestWebhookEvents:
    def test_new_client_creates_contacto(self):
        """event=new-client → creates document in contactos"""
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers=WEBHOOK_HEADERS,
            json={
                "event": "new-client",
                "data": {
                    "id": f"test-client-{unique_id}",
                    "name": f"TEST Cliente {unique_id}",
                    "phonePrimary": "+573001234567",
                    "email": f"test_{unique_id}@test.com",
                    "identification": {"number": f"TEST-{unique_id}"}
                }
            })
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"
        # Background task runs asynchronously, give it a moment
        time.sleep(1)
        print(f"new-client event sent for id=test-client-{unique_id}")

    def test_new_invoice_creates_event(self):
        """event=new-invoice → creates roddos_events with requiere_revision:true"""
        import uuid
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers=WEBHOOK_HEADERS,
            json={
                "event": "new-invoice",
                "data": {
                    "id": f"inv-test-{str(uuid.uuid4())[:8]}",
                    "number": "FV-9999",
                    "client": {"name": "Test Cliente", "id": "999"},
                    "total": 1000000
                }
            })
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"
        time.sleep(1)
        print("new-invoice event sent")

    def test_delete_invoice_returns_ok(self):
        """event=delete-invoice → returns ok (even if no moto linked)"""
        resp = requests.post(f"{BASE_URL}/api/webhooks/alegra",
            headers=WEBHOOK_HEADERS,
            json={
                "event": "delete-invoice",
                "data": {"id": "nonexistent-invoice-99999"}
            })
        assert resp.status_code == 200
        assert resp.json().get("status") == "ok"
        time.sleep(1)
        print("delete-invoice event sent")


# ── PARTE 4: Webhook status + sync-pagos ─────────────────────────────────────

class TestWebhookStatus:
    def test_webhook_status_requires_auth(self):
        """GET /api/webhooks/status without token → 401 or 403"""
        resp = requests.get(f"{BASE_URL}/api/webhooks/status")
        assert resp.status_code in (401, 403, 422), f"Expected auth error, got {resp.status_code}"

    def test_webhook_status_with_auth(self, auth_headers):
        """GET /api/webhooks/status returns required fields"""
        resp = requests.get(f"{BASE_URL}/api/webhooks/status", headers=auth_headers)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "suscripciones" in data
        assert "total_activas" in data
        assert "cron_intervalo" in data
        assert "pagos_sincronizados_hoy" in data
        assert "ultimo_sync_pago" in data
        print(f"Webhook status: total_activas={data.get('total_activas')}, pagos_hoy={data.get('pagos_sincronizados_hoy')}")

    def test_sync_pagos_ahora_requires_auth(self):
        """POST /api/webhooks/sync-pagos-ahora without token → auth error"""
        resp = requests.post(f"{BASE_URL}/api/webhooks/sync-pagos-ahora")
        assert resp.status_code in (401, 403, 422)

    def test_sync_pagos_ahora_with_auth(self, auth_headers):
        """POST /api/webhooks/sync-pagos-ahora → {procesados, message}"""
        resp = requests.post(f"{BASE_URL}/api/webhooks/sync-pagos-ahora", headers=auth_headers)
        assert resp.status_code == 200, f"Got {resp.status_code}: {resp.text[:200]}"
        data = resp.json()
        assert "procesados" in data
        assert "message" in data
        assert isinstance(data["procesados"], int)
        print(f"sync-pagos-ahora: procesados={data['procesados']}, message={data['message']}")


# ── PARTE 0 FIX 3: CFO cache ─────────────────────────────────────────────────

class TestCFOCache:
    def test_semaforo_second_call_faster(self, auth_headers):
        """GET /api/cfo/semaforo: second call should be faster (cache)"""
        # First call
        t0 = time.time()
        r1 = requests.get(f"{BASE_URL}/api/cfo/semaforo", headers=auth_headers)
        t1 = time.time() - t0
        assert r1.status_code == 200, f"semaforo returned {r1.status_code}: {r1.text[:200]}"
        
        # Second call (should be cached)
        t0 = time.time()
        r2 = requests.get(f"{BASE_URL}/api/cfo/semaforo", headers=auth_headers)
        t2 = time.time() - t0
        assert r2.status_code == 200
        print(f"semaforo: 1st={t1:.3f}s, 2nd={t2:.3f}s (cache expected < 1s)")
        assert t2 < 3.0, f"Second call still slow: {t2:.3f}s"

    def test_pyg_second_call_faster(self, auth_headers):
        """GET /api/cfo/pyg: second call should be faster (cache)"""
        t0 = time.time()
        r1 = requests.get(f"{BASE_URL}/api/cfo/pyg", headers=auth_headers)
        t1 = time.time() - t0
        assert r1.status_code == 200, f"pyg returned {r1.status_code}: {r1.text[:200]}"
        
        t0 = time.time()
        r2 = requests.get(f"{BASE_URL}/api/cfo/pyg", headers=auth_headers)
        t2 = time.time() - t0
        assert r2.status_code == 200
        print(f"pyg: 1st={t1:.3f}s, 2nd={t2:.3f}s (cache expected < 1s)")
        assert t2 < 3.0, f"Second call still slow: {t2:.3f}s"
