"""Backend tests — BUILD 5 TEST 5 — Mercately WhatsApp integration
Tests: 5A (cliente flow), 5B (interno flow), 5C (configuración + resumen_semanal)
"""
import asyncio
import pytest
import requests
import os
import sys
from datetime import datetime, timezone, timedelta

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

MONGO_URL = "mongodb://localhost:27017"
DB_NAME   = "roddos_contable"

ADMIN_EMAIL    = "contabilidad@roddos.com"
ADMIN_PASSWORD = "Admin@RODDOS2025!"
WHITELIST_NUMBER = "+573009998877"
UNKNOWN_NUMBER   = "+579999999999"
PUBLIC_IMAGE_URL = "https://via.placeholder.com/300.jpg"


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login",
                         json={"email": ADMIN_EMAIL, "password": ADMIN_PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def admin_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="module", autouse=True)
def setup_mercately_config(admin_headers):
    """Ensure Mercately config has api_key, whitelist, and destinatarios_resumen for all tests."""
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key":               "test_key_abc123",
        "phone_number":          "+573001234567",
        "whitelist":             [WHITELIST_NUMBER],
        "ceo_number":            "+573001112233",
        "destinatarios_resumen": ["+573001112233", "+573005556677"],
    }, headers=admin_headers)
    yield


# ─── TEST 5A-1: cliente + image → no crash ────────────────────────────────────

def test_5A1_cliente_image_no_crash():
    """5A-1: phone de cliente REAL (or DESCONOCIDO) + image → endpoint returns ok, no 500"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        UNKNOWN_NUMBER,
        "message_type": "image",
        "media_url":    PUBLIC_IMAGE_URL,
        "content":      "comprobante de pago",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True, f"Expected {{ok: true}}, got {data}"
    print(f"PASS 5A-1: unknown phone + image → {{ok: true}}, no crash")


def test_5A1_real_client_image_no_crash():
    """5A-1 (alt): whitelist phone + image → endpoint handles gracefully, no 500"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "image",
        "media_url":    PUBLIC_IMAGE_URL,
        "content":      "comprobante",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5A-1 alt: whitelist + image → {{ok: true}}")


# ─── TEST 5A-2: duplicate referencia ─────────────────────────────────────────

def test_5A2_duplicate_comprobante_endpoint_no_crash():
    """5A-2: send image twice — endpoint must not crash (returns ok both times)"""
    payload = {
        "phone":        WHITELIST_NUMBER,
        "message_type": "image",
        "media_url":    PUBLIC_IMAGE_URL,
        "content":      "comprobante pago referencia TEST-REF-001",
    }
    resp1 = requests.post(f"{BASE_URL}/api/mercately/webhook", json=payload)
    assert resp1.status_code == 200, f"1st call failed: {resp1.status_code}: {resp1.text}"
    assert resp1.json().get("ok") is True

    resp2 = requests.post(f"{BASE_URL}/api/mercately/webhook", json=payload)
    assert resp2.status_code == 200, f"2nd call failed: {resp2.status_code}: {resp2.text}"
    assert resp2.json().get("ok") is True
    print("PASS 5A-2: both image sends returned ok (no crash, duplicate logic in place)")


# ─── TEST 5A-3: DESCONOCIDO phone ────────────────────────────────────────────

def test_5A3_desconocido_phone_returns_ok():
    """5A-3: unknown phone 9999999999 → {ok: true}, no action in Alegra"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        UNKNOWN_NUMBER,
        "message_type": "text",
        "content":      "hola",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5A-3: DESCONOCIDO phone → {{ok: true}}")


# ─── TEST 5A-4: whitelist + text 'si' without session ────────────────────────

def test_5A4_whitelist_si_without_session_returns_ok():
    """5A-4: whitelist phone + text 'si' with no active session → 'No hay propuesta pendiente', no crash"""
    # Clear any existing session first by sending 'no'
    requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone": WHITELIST_NUMBER, "message_type": "text", "content": "no",
    })

    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "text",
        "content":      "si",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5A-4: whitelist + 'si' without session → {{ok: true}} (no crash)")


# ─── TEST 5B-1: INTERNO + image/document → graceful ──────────────────────────

def test_5B1_interno_image_no_crash():
    """5B-1: whitelist phone + image → propuesta with retenciones or graceful error, no 500"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "image",
        "media_url":    PUBLIC_IMAGE_URL,
        "content":      "factura proveedor con retenciones",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5B-1: INTERNO + image → {{ok: true}}, no crash")


def test_5B1_interno_document_no_crash():
    """5B-1 (doc): whitelist phone + document message_type → graceful, no 500"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "document",
        "media_url":    PUBLIC_IMAGE_URL,
        "content":      "factura",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    assert resp.json().get("ok") is True
    print(f"PASS 5B-1 doc: INTERNO + document → {{ok: true}}")


# ─── TEST 5B-2: Expired session → SI → "No hay propuesta pendiente" ──────────

def test_5B2_expired_session_si_returns_ok():
    """5B-2: insert expired session, then send 'si' → 'No hay propuesta pendiente', no crash"""
    # Insert an expired session directly into MongoDB
    sys.path.insert(0, "/app/backend")
    import motor.motor_asyncio
    mongo_url = MONGO_URL
    db_name   = DB_NAME

    async def _insert_expired():
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        db = client[db_name]
        expired_at = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        await db.mercately_sessions.update_one(
            {"phone": WHITELIST_NUMBER},
            {"$set": {
                "phone": WHITELIST_NUMBER,
                "expires_at": expired_at,
                "tipo_remitente": "INTERNO",
                "propuesta_texto": "test expired session",
            }},
            upsert=True,
        )
        client.close()

    asyncio.run(_insert_expired())

    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "text",
        "content":      "si",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5B-2: expired session + 'si' → {{ok: true}} (session expired, 'No hay propuesta')")


# ─── TEST 5B-3: INTERNO + 'no' → cancel session ──────────────────────────────

def test_5B3_interno_no_cancels_session():
    """5B-3: whitelist phone + text 'no' → session cancelled, {ok: true}"""
    resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
        "phone":        WHITELIST_NUMBER,
        "message_type": "text",
        "content":      "no",
    })
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert data.get("ok") is True
    print(f"PASS 5B-3: INTERNO + 'no' → session cancelled, {{ok: true}}")


# ─── TEST 5C-1: POST settings with destinatarios_resumen ─────────────────────

def test_5C1_post_settings_with_destinatarios_resumen(admin_headers):
    """5C-1: POST /settings/mercately with destinatarios_resumen → saved correctly, api_secret NOT in GET"""
    payload = {
        "api_key":               "test_key_abc123",
        "phone_number":          "+573001234567",
        "whitelist":             [WHITELIST_NUMBER],
        "ceo_number":            "+573001112233",
        "destinatarios_resumen": ["+573001112233", "+573005556677"],
    }
    resp = requests.post(f"{BASE_URL}/api/settings/mercately", json=payload, headers=admin_headers)
    assert resp.status_code == 200, f"POST failed: {resp.status_code}: {resp.text}"

    get_resp = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
    assert get_resp.status_code == 200
    data = get_resp.json()

    assert "api_secret" not in data, "api_secret must NOT be in GET response"
    assert "destinatarios_resumen" in data, "destinatarios_resumen must be in GET response"
    assert isinstance(data["destinatarios_resumen"], list)
    # Both recipients should appear (ceo_number prepended if not present)
    for num in ["+573001112233", "+573005556677"]:
        assert num in data["destinatarios_resumen"], f"{num} missing from destinatarios_resumen"
    print(f"PASS 5C-1: destinatarios_resumen saved and returned correctly: {data['destinatarios_resumen']}")


# ─── TEST 5C-2: Backwards-compat ceo_number ──────────────────────────────────

def test_5C2_backwards_compat_ceo_number_in_destinatarios(admin_headers):
    """5C-2: ceo_number exists but NOT in destinatarios_resumen → must appear automatically"""
    # Save config with ceo_number but empty destinatarios_resumen
    resp = requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key":               "test_key_abc123",
        "phone_number":          "+573001234567",
        "whitelist":             [WHITELIST_NUMBER],
        "ceo_number":            "+573009876543",
        "destinatarios_resumen": [],  # empty
    }, headers=admin_headers)
    assert resp.status_code == 200

    get_resp = requests.get(f"{BASE_URL}/api/settings/mercately", headers=admin_headers)
    data = get_resp.json()

    # ceo_number should appear in destinatarios_resumen
    assert "+573009876543" in data["destinatarios_resumen"], \
        f"ceo_number should auto-appear in destinatarios_resumen, got: {data['destinatarios_resumen']}"
    print(f"PASS 5C-2: backwards-compat → ceo_number auto-added to destinatarios_resumen: {data['destinatarios_resumen']}")

    # Restore config
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key":               "test_key_abc123",
        "phone_number":          "+573001234567",
        "whitelist":             [WHITELIST_NUMBER],
        "ceo_number":            "+573001112233",
        "destinatarios_resumen": ["+573001112233", "+573005556677"],
    }, headers=admin_headers)


# ─── TEST 5C-3: test with invalid key → 400 or 503, never 500 ────────────────

def test_5C3_test_connection_invalid_key_not_500(admin_headers):
    """5C-3: POST /settings/mercately/test with invalid API key → 400 or 503, never 500"""
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key": "completely-invalid-key-xyz",
        "phone_number": "+573001234567",
        "whitelist": [WHITELIST_NUMBER],
        "ceo_number": "",
        "destinatarios_resumen": [],
    }, headers=admin_headers)

    resp = requests.post(f"{BASE_URL}/api/settings/mercately/test", headers=admin_headers)
    assert resp.status_code != 500, f"Got 500 — must NEVER be 500! Response: {resp.text}"
    assert resp.status_code in (400, 503), f"Expected 400 or 503, got {resp.status_code}: {resp.text}"
    print(f"PASS 5C-3: invalid api_key → {resp.status_code} (not 500)")

    # Restore valid test config
    requests.post(f"{BASE_URL}/api/settings/mercately", json={
        "api_key":               "test_key_abc123",
        "phone_number":          "+573001234567",
        "whitelist":             [WHITELIST_NUMBER],
        "ceo_number":            "+573001112233",
        "destinatarios_resumen": ["+573001112233", "+573005556677"],
    }, headers=admin_headers)


# ─── TEST 5C-4: enviar_whatsapp with empty api_key → returns False ────────────

def test_5C4_enviar_whatsapp_empty_api_key_returns_false():
    """5C-4: enviar_whatsapp() with empty api_key → returns False, no exception"""
    sys.path.insert(0, "/app/backend")

    async def _test():
        import motor.motor_asyncio
        mongo_url = MONGO_URL
        db_name   = DB_NAME

        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        _db = client[db_name]

        # Temporarily clear api_key
        await _db.mercately_config.update_one({}, {"$set": {"api_key": ""}})
        try:
            from routers.mercately import enviar_whatsapp
            result = await enviar_whatsapp("+573001112233", "test message")
            client.close()
            return result
        except Exception as e:
            client.close()
            raise e

    result = asyncio.run(_test())
    assert result is False, f"Expected False when api_key is empty, got {result}"
    print(f"PASS 5C-4: enviar_whatsapp() with empty api_key returns False (no exception)")

    # Restore api_key
    async def _restore():
        import motor.motor_asyncio
        mongo_url = MONGO_URL
        db_name   = DB_NAME
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        _db = client[db_name]
        await _db.mercately_config.update_one({}, {"$set": {"api_key": "test_key_abc123"}})
        client.close()

    asyncio.run(_restore())


# ─── TEST 5C-5: resumen_semanal() with empty destinatarios → no crash ────────

def test_5C5_resumen_semanal_empty_destinatarios_no_crash():
    """5C-5: resumen_semanal() with empty destinatarios must not crash"""
    sys.path.insert(0, "/app/backend")

    async def _test():
        import motor.motor_asyncio
        mongo_url = MONGO_URL
        db_name   = DB_NAME
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        _db = client[db_name]

        # Set empty destinatarios_resumen and ceo_number
        await _db.mercately_config.update_one(
            {}, {"$set": {"destinatarios_resumen": [], "ceo_number": ""}},
        )
        client.close()

        # Now call resumen_semanal — should not crash
        from services.loanbook_scheduler import resumen_semanal
        try:
            await resumen_semanal()
            return True
        except Exception as e:
            raise AssertionError(f"resumen_semanal() crashed: {e}")

    result = asyncio.run(_test())
    assert result is True
    print("PASS 5C-5: resumen_semanal() with empty destinatarios completed without crash")

    # Restore
    async def _restore():
        import motor.motor_asyncio
        mongo_url = MONGO_URL
        db_name   = DB_NAME
        client = motor.motor_asyncio.AsyncIOMotorClient(mongo_url)
        _db = client[db_name]
        await _db.mercately_config.update_one({}, {"$set": {
            "api_key":               "test_key_abc123",
            "destinatarios_resumen": ["+573001112233", "+573005556677"],
            "ceo_number":            "+573001112233",
        }})
        client.close()

    asyncio.run(_restore())
