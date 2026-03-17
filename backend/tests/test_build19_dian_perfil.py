"""
BUILD 19 Backend Tests: DIAN Integration + User Profile Module
Tests: DIAN status/sync/historial/probar-conexion, auth perfil/cambiar-password/sesiones/preferencias
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

EMAIL = "contabilidad@roddos.com"
PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ─────────────── SMOKE ───────────────

def test_smoke():
    resp = requests.get(f"{BASE_URL}/api/health/smoke")
    assert resp.status_code == 200
    assert resp.json().get("status") == "ok"
    print("SMOKE: OK")


# ─────────────── DIAN ───────────────

def test_dian_status(auth):
    resp = requests.get(f"{BASE_URL}/api/dian/status", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("modo") == "simulacion"
    assert data.get("total_causadas", -1) >= 0
    print(f"DIAN status: modo={data['modo']}, total_causadas={data['total_causadas']}")


def test_dian_historial(auth):
    resp = requests.get(f"{BASE_URL}/api/dian/historial", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    print(f"DIAN historial: {len(data)} registros")


def test_dian_probar_conexion(auth):
    resp = requests.post(f"{BASE_URL}/api/dian/probar-conexion", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("ok") is True
    print(f"DIAN probar-conexion: {data.get('mensaje')}")


def test_dian_sync(auth):
    resp = requests.post(f"{BASE_URL}/api/dian/sync", headers=auth, json={})
    assert resp.status_code == 200
    data = resp.json()
    assert "consultadas" in data
    assert "procesadas" in data or "causadas" in data
    assert "omitidas" in data
    causadas = data.get("causadas", data.get("procesadas", 0))
    print(f"DIAN sync: consultadas={data['consultadas']}, causadas/procesadas={causadas}, omitidas={data['omitidas']}")


# ─────────────── AUTH PERFIL ───────────────

def test_get_sesiones(auth):
    resp = requests.get(f"{BASE_URL}/api/auth/sesiones", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    print(f"Sesiones: {len(data)} sesiones")


def test_get_preferencias(auth):
    resp = requests.get(f"{BASE_URL}/api/auth/preferencias", headers=auth)
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
    print(f"Preferencias: {data}")


def test_put_preferencias(auth):
    payload = {"notificaciones_email": True, "notificaciones_push": False, "resumen_semanal": True}
    resp = requests.put(f"{BASE_URL}/api/auth/preferencias", headers=auth, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("message") == "Preferencias guardadas" or "preferencias" in data
    print(f"PUT preferencias: {data}")


def test_put_perfil(auth):
    payload = {"nombre": "Contabilidad Test", "cargo": "Contador"}
    resp = requests.put(f"{BASE_URL}/api/auth/perfil", headers=auth, json=payload)
    assert resp.status_code == 200
    data = resp.json()
    print(f"PUT perfil: {data}")


def test_cambiar_password_wrong_current(auth):
    """Contraseña actual incorrecta debe retornar 400"""
    payload = {
        "password_actual": "WrongPassword123!",
        "password_nueva": "NuevoPass123!",
        "password_confirmar": "NuevoPass123!"
    }
    resp = requests.put(f"{BASE_URL}/api/auth/cambiar-password", headers=auth, json=payload)
    assert resp.status_code == 400, f"Expected 400, got {resp.status_code}: {resp.text}"
    print(f"cambiar-password wrong: {resp.status_code} - OK")


def test_cambiar_password_success_and_restore(auth):
    """Change password then restore to original"""
    new_pass = "NuevoPass123!"
    
    # Change to new password
    payload = {
        "password_actual": PASSWORD,
        "password_nueva": new_pass,
        "password_confirmar": new_pass
    }
    resp = requests.put(f"{BASE_URL}/api/auth/cambiar-password", headers=auth, json=payload)
    assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
    data = resp.json()
    assert "message" in data
    assert data.get("logout_required") is True
    print(f"cambiar-password success: {data['message']}")
    
    # Login with new password to get new token
    login_resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": new_pass})
    assert login_resp.status_code == 200, "Login with new password failed"
    new_token = login_resp.json()["token"]
    new_auth = {"Authorization": f"Bearer {new_token}"}
    
    # Restore original password
    restore_payload = {
        "password_actual": new_pass,
        "password_nueva": PASSWORD,
        "password_confirmar": PASSWORD
    }
    restore_resp = requests.put(f"{BASE_URL}/api/auth/cambiar-password", headers=new_auth, json=restore_payload)
    assert restore_resp.status_code == 200, f"Restore failed: {restore_resp.text}"
    print(f"Password restored to original: OK")
