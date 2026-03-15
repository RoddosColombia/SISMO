"""Build 8 backend tests: scheduler trigger, wa-logs endpoints"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json()["token"]

@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# TEST 8E — Scheduler trigger
class TestScheduler:
    def test_trigger_known_job(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/calcular_dpd_todos", headers=auth)
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        data = resp.json()
        assert data.get("ok") is True
        assert data.get("job") == "calcular_dpd_todos"
        assert "triggered_at" in data

    def test_trigger_unknown_job_returns_4xx(self, auth):
        resp = requests.post(f"{BASE_URL}/api/scheduler/trigger/job_inexistente", headers=auth)
        assert resp.status_code in [400, 404], f"Expected 400/404: {resp.status_code}"

    def test_list_jobs(self, auth):
        resp = requests.get(f"{BASE_URL}/api/scheduler/jobs", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) > 0


# TEST 8E — WA Logs
class TestWaLogs:
    def test_wa_logs_returns_array(self, auth):
        resp = requests.get(f"{BASE_URL}/api/settings/wa-logs", headers=auth)
        assert resp.status_code == 200, f"Expected 200: {resp.text}"
        data = resp.json()
        assert isinstance(data, list)


# TEST 8B — Dashboard API endpoints
class TestDashboardAPIs:
    def test_radar_semana(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/semana", headers=auth)
        assert resp.status_code == 200

    def test_radar_queue(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/queue", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    def test_inventario_stats(self, auth):
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=auth)
        assert resp.status_code == 200

    def test_cfo_alertas(self, auth):
        resp = requests.get(f"{BASE_URL}/api/cfo/alertas", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
