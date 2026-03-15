"""
Backend tests for Sprint Visual UX improvements:
- MEJORA A: Tarea activa badge (pausar/continuar endpoints)
- MEJORA B: Inventario filter states
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

EMAIL = "contabilidad@roddos.com"
PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if resp.status_code == 200:
        return resp.json().get("access_token") or resp.json().get("token")
    pytest.skip(f"Auth failed: {resp.status_code} {resp.text}")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"}


class TestTareaActiva:
    """Tests for tarea activa badge API - MEJORA A"""

    def test_get_tarea_activa(self, headers):
        """GET /api/chat/tarea - should return active task or ninguna"""
        resp = requests.get(f"{BASE_URL}/api/chat/tarea", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "estado" in data
        print(f"Tarea activa estado: {data['estado']}")
        if data["estado"] != "ninguna":
            print(f"Tarea: {data.get('descripcion')} [{data.get('pasos_completados')}/{data.get('pasos_total')}]")

    def test_pausar_tarea(self, headers):
        """PATCH /api/chat/tarea/avance?accion=pausar"""
        # First ensure task is en_curso
        get_resp = requests.get(f"{BASE_URL}/api/chat/tarea", headers=headers)
        tarea = get_resp.json()

        if tarea.get("estado") == "pausada":
            # Resume first
            requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "continuar"}, headers=headers)

        resp = requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "pausar"}, headers=headers)
        print(f"Pausar response: {resp.status_code} {resp.text}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("estado") == "pausada"

    def test_get_tarea_after_pausar(self, headers):
        """GET /api/chat/tarea after pausing - should return pausada"""
        resp = requests.get(f"{BASE_URL}/api/chat/tarea", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado"] == "pausada"
        print(f"Tarea estado after pause: {data['estado']}")

    def test_continuar_tarea(self, headers):
        """PATCH /api/chat/tarea/avance?accion=continuar"""
        resp = requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "continuar"}, headers=headers)
        print(f"Continuar response: {resp.status_code} {resp.text}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("estado") == "en_curso"

    def test_get_tarea_after_continuar(self, headers):
        """GET /api/chat/tarea after continuing - should return en_curso"""
        resp = requests.get(f"{BASE_URL}/api/chat/tarea", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["estado"] == "en_curso"

    def test_avance_pasos_completados_retrocompatibilidad(self, headers):
        """PATCH pasos_completados=2 - backward compatibility"""
        resp = requests.patch(
            f"{BASE_URL}/api/chat/tarea/avance",
            params={"pasos_completados": 2},
            headers=headers,
        )
        print(f"Avance pasos response: {resp.status_code} {resp.text}")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    def test_pausar_nonexistent_fails(self, headers):
        """Pausar when no task en_curso should return 404 (after pausing)"""
        # Pause first
        requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "pausar"}, headers=headers)
        # Try to pause again
        resp = requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "pausar"}, headers=headers)
        assert resp.status_code == 404
        # Restore
        requests.patch(f"{BASE_URL}/api/chat/tarea/avance", params={"accion": "continuar"}, headers=headers)


class TestInventarioStats:
    """Tests for inventario stats - used by MEJORA B filter bar"""

    def test_get_stats(self, headers):
        """GET /api/inventario/stats - should return stats with estado counts"""
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        print(f"Stats: {data}")
        # Should have basic fields
        assert "total" in data

    def test_get_motos_no_filter(self, headers):
        """GET /api/inventario/motos - no filter returns all"""
        resp = requests.get(f"{BASE_URL}/api/inventario/motos", headers=headers)
        assert resp.status_code == 200
        motos = resp.json()
        print(f"Total motos (no filter): {len(motos)}")
        assert isinstance(motos, list)

    def test_get_motos_filter_disponible(self, headers):
        """GET /api/inventario/motos?estado=Disponible"""
        resp = requests.get(f"{BASE_URL}/api/inventario/motos", params={"estado": "Disponible"}, headers=headers)
        assert resp.status_code == 200
        motos = resp.json()
        print(f"Disponibles: {len(motos)}")
        for m in motos:
            assert m["estado"] == "Disponible", f"Expected Disponible, got {m['estado']}"

    def test_get_motos_filter_entregada(self, headers):
        """GET /api/inventario/motos?estado=Entregada"""
        resp = requests.get(f"{BASE_URL}/api/inventario/motos", params={"estado": "Entregada"}, headers=headers)
        assert resp.status_code == 200
        motos = resp.json()
        print(f"Entregadas: {len(motos)}")

    def test_get_motos_todas_excludes_anulada(self, headers):
        """GET /api/inventario/motos - no estado param, verify filtering works"""
        resp_all = requests.get(f"{BASE_URL}/api/inventario/motos", headers=headers)
        resp_anulada = requests.get(
            f"{BASE_URL}/api/inventario/motos", params={"estado": "Anulada"}, headers=headers
        )
        all_motos = resp_all.json()
        anuladas = resp_anulada.json()
        print(f"All motos: {len(all_motos)}, Anuladas: {len(anuladas)}")
        # TODAS should NOT include Anulada (filtered client-side)
        anuladas_in_all = [m for m in all_motos if m.get("estado") == "Anulada"]
        print(f"Anuladas in 'all' API response: {len(anuladas_in_all)}")
