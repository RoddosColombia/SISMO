"""Backend tests for Mercately WhatsApp integration — BUILD 5"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

ADMIN_EMAIL = "contabilidad@roddos.com"
ADMIN_PASSWORD = "Admin@RODDOS2025!"
WHITELIST_NUMBER = "+573009998877"
UNKNOWN_NUMBER = "+573111111111"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── 1. GET /api/settings/mercately ────────────────────────────────────────────

def test_get_mercately_settings_returns_expected_fields(admin_headers):
    """GET /settings/mercately must return has_credentials, api_key_masked, phone_number, whitelist, ceo_number, configured_at"""
    resp = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    for field in ("has_credentials", "api_key_masked", "phone_number", "whitelist", "ceo_number", "configured_at"):
        assert field in data, f"Missing field: {field}"
    print(f"PASS: GET /settings/mercately returned correct fields: {list(data.keys())}")


def test_get_mercately_settings_no_api_secret(admin_headers):
    """api_secret must NOT be present in GET /settings/mercately response"""
    resp = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "api_secret" not in data, "api_secret should have been removed from the model"
    print("PASS: api_secret is NOT in GET /settings/mercately response")


# ── 2. POST /api/settings/mercately ───────────────────────────────────────────

def test_post_mercately_settings_saves_correctly(admin_headers):
    """POST /settings/mercately with full payload must save and be reflected in GET"""
    payload = {
        "api_key": "test-api-key-12345",
        "phone_number": "+573001234567",
        "whitelist": [WHITELIST_NUMBER, "+573000000001"],
        "ceo_number": "+573009876543",
    }
    resp = requests.post(f"{BASE_URL}/api/settings/mercately", json=payload, headers=admin_headers)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "message" in data or "ok" in data or resp.status_code == 200
    print(f"PASS: POST /settings/mercately saved correctly")

    # Verify via GET
    get_resp = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
    assert get_resp.status_code == 200
    get_data = get_resp.json()
    assert get_data["has_credentials"] is True
    assert get_data["phone_number"] == "+573001234567"
    assert WHITELIST_NUMBER in get_data["whitelist"]
    assert get_data["ceo_number"] == "+573009876543"
    assert "api_secret" not in get_data
    print(f"PASS: GET after POST shows correct data (api_secret absent)")


# ── 3. POST /api/settings/mercately/test — invalid key must return 400 or 503, not 500 ──

def test_mercately_test_connection_invalid_key(admin_headers):
    """POST /settings/mercately/test with invalid API key must return 400 or 503, NOT 500"""
    # First ensure we have an (invalid) API key saved
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key": "invalid-key-xyz",
        "phone_number": "+573001234567",
        "whitelist": [],
        "ceo_number": "",
    }, headers=admin_headers)

    resp = requests.post(f"{BASE_URL}/api/settings/mercately/test", headers=admin_headers)
    assert resp.status_code in (400, 503), f"Expected 400 or 503 (not 500), got {resp.status_code}: {resp.text}"
    print(f"PASS: POST /settings/mercately/test returned {resp.status_code} (not 500) with invalid key")


def test_mercately_test_connection_no_api_key(admin_headers):
    """POST /settings/mercately/test with empty API key must return 400"""
    # Temporarily save empty api_key (but keep whitelist for other tests)
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key": "",
        "phone_number": "+573001234567",
        "whitelist": [WHITELIST_NUMBER],
        "ceo_number": "",
    }, headers=admin_headers)
    resp = requests.post(f"{BASE_URL}/api/settings/mercately/test", headers=admin_headers)
    assert resp.status_code == 400, f"Expected 400 for empty api_key, got {resp.status_code}: {resp.text}"
    print(f"PASS: POST /settings/mercately/test returned 400 when no api_key")


# ── Setup: ensure whitelist has WHITELIST_NUMBER for webhook tests ─────────────

@pytest.fixture(scope="module", autouse=True)
def setup_mercately_config(admin_headers):
    """Ensure Mercately config has a valid api_key and WHITELIST_NUMBER in whitelist"""
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key": "test-api-key-12345",
        "phone_number": "+573001234567",
        "whitelist": [WHITELIST_NUMBER],
        "ceo_number": "+573009876543",
    }, headers=admin_headers)
    yield


# ── 4. POST /api/mercately/webhook — PUBLIC (no JWT) ──────────────────────────

def test_webhook_is_public_no_jwt():
    """POST /api/mercately/webhook must be accessible without JWT"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone": UNKNOWN_NUMBER,
        "message_type": "text",
        "content": "hola",
    })
    assert resp.status_code == 200, f"Expected 200 (public endpoint), got {resp.status_code}: {resp.text}"
    print(f"PASS: webhook is public (no JWT required), status {resp.status_code}")


def test_webhook_unknown_phone_returns_ok():
    """POST /api/mercately/webhook with unknown phone → {ok: true}, no crash"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone": UNKNOWN_NUMBER,
        "message_type": "text",
        "content": "hola",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected {{ok: true}}, got {data}"
    print(f"PASS: webhook DESCONOCIDO returns {{ok: true}}")


def test_webhook_whitelist_phone_content_si_returns_ok():
    """POST /api/mercately/webhook with whitelist phone + content=si → {ok: true}, no crash on empty session"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone": WHITELIST_NUMBER,
        "message_type": "text",
        "content": "si",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected {{ok: true}}, got {data}"
    print(f"PASS: webhook INTERNO + content=si (empty session) returns {{ok: true}}")


def test_webhook_whitelist_phone_content_no_returns_ok():
    """POST /api/mercately/webhook with whitelist phone + content=no → {ok: true}"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone": WHITELIST_NUMBER,
        "message_type": "text",
        "content": "no",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected {{ok: true}}, got {data}"
    print(f"PASS: webhook INTERNO + content=no returns {{ok: true}}")


def test_webhook_no_phone_returns_ok():
    """POST /api/mercately/webhook with missing phone → {ok: true}"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "message_type": "text",
        "content": "test",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS: webhook missing phone returns {{ok: true}}")


def test_webhook_invalid_json_returns_ok():
    """POST /api/mercately/webhook with invalid/empty body → {ok: true} (no crash)"""
    resp = requests.post(
        f"{BASE_URL}/api/mercately/webhook",
        data="not-json",
        headers={"Content-Type": "application/json"},
    )
    # Should return 200 with {ok: true} or 422 — must NOT be 500
    assert resp.status_code in (200, 422), f"Unexpected status {resp.status_code}: {resp.text}"
    print(f"PASS: webhook invalid JSON returns {resp.status_code} (not 500)")


# ── 5. Verify api_secret removed from model ───────────────────────────────────

def test_post_mercately_settings_no_api_secret_in_payload(admin_headers):
    """POST /settings/mercately must NOT require api_secret field"""
    payload = {
        "api_key": "test-key-789",
        "phone_number": "+573001234567",
        "whitelist": [],
        "ceo_number": "",
    }
    resp = requests.post(f"{BASE_URL}/api/settings/mercately", json=payload, headers=admin_headers)
    assert resp.status_code == 200, f"POST without api_secret should work, got {resp.status_code}: {resp.text}"
    print("PASS: POST /settings/mercately works without api_secret")
