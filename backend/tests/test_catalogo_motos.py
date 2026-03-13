"""Tests for /api/settings/catalogo endpoints - Catálogo de Motos (BUILD 1 RODDOS)"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def auth_token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert r.status_code == 200, f"Login failed: {r.text}"
    return r.json()["token"]


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


# ── GET /settings/catalogo ──────────────────────────────────────────────────

class TestGetCatalogo:
    def test_get_catalogo_returns_200(self, headers):
        r = requests.get(f"{BASE_URL}/api/settings/catalogo", headers=headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"

    def test_get_catalogo_has_sport100(self, headers):
        r = requests.get(f"{BASE_URL}/api/settings/catalogo", headers=headers)
        data = r.json()
        modelos = [m["modelo"] for m in data]
        assert "Sport 100" in modelos, f"Sport 100 not found in {modelos}"

    def test_get_catalogo_has_raider125(self, headers):
        r = requests.get(f"{BASE_URL}/api/settings/catalogo", headers=headers)
        data = r.json()
        modelos = [m["modelo"] for m in data]
        assert "Raider 125" in modelos, f"Raider 125 not found in {modelos}"

    def test_get_catalogo_fields(self, headers):
        r = requests.get(f"{BASE_URL}/api/settings/catalogo", headers=headers)
        data = r.json()
        assert len(data) >= 2
        for item in data:
            for field in ["id", "modelo", "marca", "costo", "pvp", "cuota_inicial", "matricula", "planes", "activo"]:
                assert field in item, f"Missing field '{field}' in {item}"
            assert "P39S" in item["planes"]
            assert "P52S" in item["planes"]
            assert "P78S" in item["planes"]


# ── POST /settings/catalogo ─────────────────────────────────────────────────

class TestCreateCatalogo:
    created_id = None

    def test_post_catalogo_creates_model(self, headers):
        payload = {
            "modelo": "TEST_Moto Prueba",
            "marca": "TestMarca",
            "costo": 5000000,
            "pvp": 6000000,
            "cuota_inicial": 500000,
            "matricula": 660000,
            "planes": {
                "P39S": {"semanas": 39, "cuota": 150000},
                "P52S": {"semanas": 52, "cuota": 120000},
                "P78S": {"semanas": 78, "cuota": 80000}
            },
            "activo": True
        }
        r = requests.post(f"{BASE_URL}/api/settings/catalogo", json=payload, headers=headers)
        assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
        data = r.json()
        assert data["modelo"] == "TEST_Moto Prueba"
        assert "id" in data
        TestCreateCatalogo.created_id = data["id"]
        print(f"Created model id: {TestCreateCatalogo.created_id}")

    def test_created_model_persists(self, headers):
        if not TestCreateCatalogo.created_id:
            pytest.skip("No created_id from previous test")
        r = requests.get(f"{BASE_URL}/api/settings/catalogo/{TestCreateCatalogo.created_id}", headers=headers)
        assert r.status_code == 200
        assert r.json()["modelo"] == "TEST_Moto Prueba"


# ── PUT /settings/catalogo/{id} ─────────────────────────────────────────────

class TestUpdateCatalogo:
    def test_put_updates_pvp(self, headers):
        # Get Sport 100
        r = requests.get(f"{BASE_URL}/api/settings/catalogo", headers=headers)
        sport = next((m for m in r.json() if m["modelo"] == "Sport 100"), None)
        assert sport is not None
        original_pvp = sport["pvp"]
        new_pvp = original_pvp + 100000

        r2 = requests.put(f"{BASE_URL}/api/settings/catalogo/{sport['id']}", json={"pvp": new_pvp}, headers=headers)
        assert r2.status_code == 200
        assert r2.json()["pvp"] == new_pvp

        # Restore
        requests.put(f"{BASE_URL}/api/settings/catalogo/{sport['id']}", json={"pvp": original_pvp}, headers=headers)

    def test_put_deactivates_model(self, headers):
        if not TestCreateCatalogo.created_id:
            pytest.skip("No test model to deactivate")
        item_id = TestCreateCatalogo.created_id
        r = requests.put(f"{BASE_URL}/api/settings/catalogo/{item_id}", json={"activo": False}, headers=headers)
        assert r.status_code == 200
        assert r.json()["activo"] == False

        # Verify persistence
        r2 = requests.get(f"{BASE_URL}/api/settings/catalogo/{item_id}", headers=headers)
        assert r2.json()["activo"] == False

    def test_put_nonexistent_returns_404(self, headers):
        r = requests.put(f"{BASE_URL}/api/settings/catalogo/nonexistent-id-xyz", json={"pvp": 100}, headers=headers)
        assert r.status_code == 404
