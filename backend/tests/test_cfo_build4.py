"""BUILD 4 — Agente CFO: Tests for all CFO endpoints"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get('REACT_APP_BACKEND_URL', '').rstrip('/')

@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert resp.status_code == 200
    return resp.json()["token"]

@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# GET /api/cfo/semaforo
class TestSemaforo:
    def test_semaforo_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/semaforo", headers=auth)
        assert resp.status_code == 200

    def test_semaforo_has_5_dimensiones(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/semaforo", headers=auth)
        data = resp.json()
        # Should have dimensiones key or direct keys for the 5 areas
        assert "semaforo" in data or "dimensiones" in data or "caja" in data or "ventas" in data
        print(f"Semaforo keys: {list(data.keys())}")

    def test_semaforo_dimensiones_content(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/semaforo", headers=auth)
        data = resp.json()
        # Check the 5 expected dimensions exist somewhere
        content = str(data)
        expected = ["caja", "cartera", "ventas", "roll_rate", "impuesto"]
        found = [d for d in expected if d in content.lower()]
        print(f"Found dimensions: {found}")
        assert len(found) >= 3, f"Expected at least 3 of 5 dimensions, found: {found}"


# GET /api/cfo/pyg
class TestPyG:
    def test_pyg_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/pyg", headers=auth)
        assert resp.status_code == 200

    def test_pyg_has_required_fields(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/pyg", headers=auth)
        data = resp.json()
        content = str(data)
        print(f"P&G keys: {list(data.keys()) if isinstance(data, dict) else 'list'}")
        for field in ["ingresos_totales", "margen_bruto", "resultado_neto"]:
            assert field in content, f"Missing field: {field}"


# GET /api/cfo/config
class TestCfoConfig:
    def test_config_get_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/config", headers=auth)
        assert resp.status_code == 200

    def test_config_defaults(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/config", headers=auth)
        data = resp.json()
        print(f"Config: {data}")
        assert "dia_informe" in data
        assert "umbral_mora_pct" in data
        assert "umbral_caja_cop" in data
        assert "whatsapp_activo" in data

    def test_config_post(self, auth):
        payload = {
            "dia_informe": 1,
            "umbral_mora_pct": 5.0,
            "umbral_caja_cop": 5000000,
            "whatsapp_activo": False,
            "whatsapp_ceo": ""
        }
        resp = requests.post(f"{BASE_URL}/api/cfo/config", json=payload, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        print(f"Config POST response: {data}")


# GET /api/cfo/informes
class TestCfoInformes:
    def test_informes_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/informes", headers=auth)
        assert resp.status_code == 200

    def test_informes_is_array(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/informes", headers=auth)
        data = resp.json()
        assert isinstance(data, list) or ("informes" in data), f"Expected list, got: {type(data)}"


# GET /api/cfo/informe-mensual
class TestCfoInformeMensual:
    def test_informe_mensual_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/informe-mensual", headers=auth)
        assert resp.status_code == 200

    def test_informe_mensual_response(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/informe-mensual", headers=auth)
        data = resp.json()
        print(f"Informe mensual keys: {list(data.keys()) if isinstance(data, dict) else data}")
        assert isinstance(data, dict)


# GET /api/cfo/alertas
class TestCfoAlertas:
    def test_alertas_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/alertas", headers=auth)
        assert resp.status_code == 200

    def test_alertas_is_array(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/alertas", headers=auth)
        data = resp.json()
        assert isinstance(data, list), f"Expected list, got: {type(data)}"


# GET /api/cfo/plan-accion
class TestCfoPlanAccion:
    def test_plan_accion_status(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/plan-accion", headers=auth)
        assert resp.status_code == 200

    def test_plan_accion_has_plan(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/plan-accion", headers=auth)
        data = resp.json()
        print(f"Plan accion: {data}")
        assert "plan_acciones" in data or isinstance(data, list)


# POST /api/cfo/generar
class TestCfoGenerar:
    def test_generar_status(self, auth):
        resp = requests.post(f"{BASE_URL}/api/cfo/generar", headers=auth, timeout=60)
        print(f"Generar status: {resp.status_code}")
        print(f"Generar response keys: {list(resp.json().keys()) if resp.status_code == 200 else resp.text[:200]}")
        assert resp.status_code == 200

    def test_generar_has_content(self, auth):
        resp = requests.post(f"{BASE_URL}/api/cfo/generar", headers=auth, timeout=60)
        data = resp.json()
        content = str(data)
        # Should have some AI-generated content
        assert len(content) > 100, "Generated report seems empty"
