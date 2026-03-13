"""test_build3_sprint1.py — BUILD 3: Scheduler DPD + Mora 15%EA + Scores.
Tests: radar endpoints, loanbook gestion/ptp/snapshot, migration_v24 idempotency.
"""
import pytest
import requests
import os
import asyncio

BASE_URL = "https://selector-cuentas.preview.emergentagent.com"
LOAN_ID = "c7bdd5ee-a19a-4a7e-9076-81aabaa61422"

# ── Auth fixture ─────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    data = resp.json()
    return data.get("access_token") or data.get("token")


@pytest.fixture(scope="module")
def auth(token):
    return {"Authorization": f"Bearer {token}"}


# ── Radar endpoints ───────────────────────────────────────────────────────────

class TestRadarEndpoints:
    """4 endpoints /api/radar/*"""

    def test_portfolio_health(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/portfolio-health", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        for key in ["total_loans", "activos", "en_mora", "tasa_mora", "saldo_cartera_total"]:
            assert key in data, f"Missing key: {key}"
        print(f"PASS portfolio-health: {data}")

    def test_collection_queue(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/queue", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        if data:
            item = data[0]
            for key in ["bucket", "dpd_actual", "total_a_pagar", "dias_para_protocolo", "whatsapp_link"]:
                assert key in item, f"Queue item missing key: {key}"
        print(f"PASS queue: {len(data)} items")

    def test_semana_stats(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/semana", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        totales = data.get("totales", {})
        for key in ["cuotas_esperadas", "cuotas_pagadas", "porcentaje_cobrado"]:
            assert key in totales, f"semana.totales missing key: {key}"
        print(f"PASS semana: {totales}")

    def test_roll_rate(self, auth):
        resp = requests.get(f"{BASE_URL}/api/radar/roll-rate", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "roll_rate_pct" in data
        assert "data_disponible" in data
        # Correct behavior: data_disponible=False if no 7d events
        print(f"PASS roll-rate: roll_rate_pct={data['roll_rate_pct']}, data_disponible={data['data_disponible']}")


# ── Loanbook BUILD 3 endpoints ────────────────────────────────────────────────

class TestLoanbookBuild3:
    """gestion, ptp, snapshot for LB-TEST001"""

    def test_register_gestion(self, auth):
        body = {
            "tipo": "llamada",
            "canal": "whatsapp",
            "resultado": "no_contestó",
            "notas": "Test gestión BUILD3"
        }
        resp = requests.post(f"{BASE_URL}/api/loanbook/{LOAN_ID}/gestion", json=body, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert "gestion" in data
        assert "id" in data["gestion"]
        print(f"PASS gestion: {data['gestion']['id']}")

    def test_register_ptp(self, auth):
        body = {"ptp_fecha": "2026-03-20", "ptp_monto": 350000}
        resp = requests.post(f"{BASE_URL}/api/loanbook/{LOAN_ID}/ptp", json=body, headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ptp_fecha") == "2026-03-20"
        assert data.get("ptp_monto") == 350000
        print(f"PASS ptp: {data}")

    def test_snapshot_build3_fields(self, auth):
        resp = requests.get(f"{BASE_URL}/api/loanbook/{LOAN_ID}/snapshot", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        for key in ["dpd_actual", "dpd_bucket", "score_pago", "estrella_nivel"]:
            assert key in data, f"snapshot missing key: {key}"
        assert data["dpd_actual"] > 0, "LB-TEST001 should have dpd_actual > 0"
        assert data["dpd_bucket"] == "15-21", f"Expected 15-21 got {data['dpd_bucket']}"
        print(f"PASS snapshot: dpd={data['dpd_actual']} bucket={data['dpd_bucket']} score={data['score_pago']} stars={data['estrella_nivel']}")


# ── Migration v24 idempotency ─────────────────────────────────────────────────

class TestMigrationV24:
    """Verify migration_v24 idempotency directly in Python"""

    def test_migration_idempotent(self):
        """Run run_migration_v24 twice — second call should log 'Ya aplicada'"""
        import sys, io, logging
        sys.path.insert(0, "/app/backend")

        # Capture logs
        log_output = []

        class ListHandler(logging.Handler):
            def emit(self, record):
                log_output.append(record.getMessage())

        from migration_v24 import run_migration_v24
        from database import db

        handler = ListHandler()
        logging.getLogger().setLevel(logging.DEBUG)
        logging.getLogger().addHandler(handler)

        async def run_twice():
            await run_migration_v24(db)
            await run_migration_v24(db)

        asyncio.run(run_twice())
        logging.getLogger().removeHandler(handler)

        skip_msgs = [m for m in log_output if "Ya aplicada" in m]
        assert len(skip_msgs) >= 1, f"Expected 'Ya aplicada' log. Got: {log_output}"
        print(f"PASS migration idempotent: {skip_msgs}")


# ── DPD & Score calculation verification ─────────────────────────────────────

class TestSchedulerCalculations:
    """Verify LB-TEST001 has correct DPD and score via snapshot"""

    def test_lb_test001_dpd_bucket(self, auth):
        resp = requests.get(f"{BASE_URL}/api/loanbook/{LOAN_ID}/snapshot", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["dpd_actual"] >= 15, f"Expected dpd>=15 for LB-TEST001, got {data['dpd_actual']}"
        assert data["dpd_bucket"] == "15-21", f"Expected bucket 15-21, got {data['dpd_bucket']}"
        print(f"PASS DPD check: dpd={data['dpd_actual']} bucket={data['dpd_bucket']}")

    def test_lb_test001_score(self, auth):
        resp = requests.get(f"{BASE_URL}/api/loanbook/{LOAN_ID}/snapshot", headers=auth)
        assert resp.status_code == 200
        data = resp.json()
        assert data["score_pago"] in ["D", "E"], f"Expected score D/E for LB-TEST001, got {data['score_pago']}"
        assert data["estrella_nivel"] <= 1, f"Expected estrella<=1, got {data['estrella_nivel']}"
        print(f"PASS Score check: score={data['score_pago']} estrella={data['estrella_nivel']}")
