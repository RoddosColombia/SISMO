"""test_cfo_estrategico.py — BUILD 11: Agente CFO Estratégico RODDOS tests"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# Auth credentials
EMAIL = "contabilidad@roddos.com"
PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def auth_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    if res.status_code == 200:
        return res.json().get("access_token") or res.json().get("token")
    pytest.skip(f"Auth failed: {res.status_code} {res.text}")


@pytest.fixture(scope="module")
def client(auth_token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {auth_token}", "Content-Type": "application/json"})
    return s


# ── PASO 0: Verify clean DB ───────────────────────────────────────────────────
class TestCleanDB:
    """Verify no test loanbooks exist"""

    def test_no_lb_test_codes(self, client):
        res = client.get(f"{BASE_URL}/api/loanbook")
        assert res.status_code == 200
        data = res.json()
        lbs = data if isinstance(data, list) else data.get("loanbooks", data.get("items", []))
        test_codes = [lb.get("codigo", "") for lb in lbs if str(lb.get("codigo", "")).startswith("LB-TEST")]
        assert len(test_codes) == 0, f"Found test loanbooks: {test_codes}"
        print(f"PASS: No LB-TEST* loanbooks found ({len(lbs)} total)")

    def test_real_loanbooks_exist(self, client):
        res = client.get(f"{BASE_URL}/api/loanbook")
        assert res.status_code == 200
        data = res.json()
        lbs = data if isinstance(data, list) else data.get("loanbooks", data.get("items", []))
        real = [lb for lb in lbs if "LB-2026" in str(lb.get("codigo", ""))]
        assert len(real) >= 9, f"Expected >= 9 real loanbooks, found {len(real)}"
        print(f"PASS: Found {len(real)} real LB-2026-* loanbooks")


# ── GET /api/cfo/indicadores ──────────────────────────────────────────────────
class TestIndicadores:
    def test_indicadores_status(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/indicadores")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        print("PASS: GET /cfo/indicadores => 200")

    def test_indicadores_recaudo_base(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/indicadores")
        data = res.json()
        assert data.get("recaudo_semanal_base") == 1509500, \
            f"Expected recaudo_semanal_base=1509500, got {data.get('recaudo_semanal_base')}"
        print(f"PASS: recaudo_semanal_base={data['recaudo_semanal_base']}")

    def test_indicadores_creditos_activos(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/indicadores")
        data = res.json()
        activos = data.get("creditos_activos")
        assert activos == 9, f"Expected creditos_activos=9, got {activos}"
        print(f"PASS: creditos_activos={activos}")

    def test_indicadores_has_required_fields(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/indicadores")
        data = res.json()
        for field in ["recaudo_semanal_base", "creditos_activos", "creditos_minimos", "autosostenible", "saldo_cartera"]:
            assert field in data, f"Missing field: {field}"
        print("PASS: All required indicadores fields present")


# ── GET /api/cfo/plan-ingresos ────────────────────────────────────────────────
class TestPlanIngresos:
    def test_plan_ingresos_status(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-ingresos?semanas=4")
        assert res.status_code == 200
        print("PASS: GET /cfo/plan-ingresos?semanas=4 => 200")

    def test_plan_ingresos_semana1_miercoles(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-ingresos?semanas=4")
        data = res.json()
        semanas = data.get("semanas", [])
        assert len(semanas) >= 1, "No semanas returned"
        s1 = semanas[0]
        # Miércoles = day of week 2
        from datetime import date
        wed = date.fromisoformat(s1["miercoles"])
        assert wed.weekday() == 2, f"semana 1 miércoles={s1['miercoles']} is weekday {wed.weekday()}, expected 2"
        print(f"PASS: Semana 1 miércoles={s1['miercoles']} (weekday={wed.weekday()})")

    def test_plan_ingresos_recaudo_cartera(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-ingresos?semanas=4")
        data = res.json()
        assert data.get("recaudo_semanal_base") == 1509500
        print(f"PASS: recaudo_semanal_base={data['recaudo_semanal_base']}")

    def test_plan_ingresos_creditos_activos(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-ingresos?semanas=4")
        data = res.json()
        assert data.get("creditos_activos") == 9
        print(f"PASS: creditos_activos={data['creditos_activos']}")


# ── GET /api/cfo/cuotas-iniciales ─────────────────────────────────────────────
class TestCuotasIniciales:
    def test_cuotas_iniciales_status(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/cuotas-iniciales")
        assert res.status_code == 200
        print("PASS: GET /cfo/cuotas-iniciales => 200")

    def test_cuotas_iniciales_total(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/cuotas-iniciales")
        data = res.json()
        total = data.get("total_pendiente")
        assert total == 5300000, f"Expected total_pendiente=5300000, got {total}"
        print(f"PASS: total_pendiente={total}")

    def test_cuotas_iniciales_5_clientes(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/cuotas-iniciales")
        data = res.json()
        detalle = data.get("detalle", [])
        assert len(detalle) == 5, f"Expected 5 clients, got {len(detalle)}"
        print(f"PASS: {len(detalle)} clients with pending cuotas iniciales")


# ── POST /api/cfo/financiero/config ───────────────────────────────────────────
class TestFinancieroConfig:
    def test_save_config_status(self, client):
        res = client.post(f"{BASE_URL}/api/cfo/financiero/config", json={
            "gastos_fijos_semanales": 800000,
            "reserva_minima_semanas": 2,
            "limite_compromisos_pct": 0.6,
            "objetivo_deuda_np_meses": 3,
        })
        assert res.status_code == 200
        print("PASS: POST /cfo/financiero/config => 200")

    def test_save_config_ok_true(self, client):
        res = client.post(f"{BASE_URL}/api/cfo/financiero/config", json={"gastos_fijos_semanales": 800000})
        data = res.json()
        assert data.get("ok") == True
        print(f"PASS: ok={data['ok']}")

    def test_save_config_creditos_minimos(self, client):
        res = client.post(f"{BASE_URL}/api/cfo/financiero/config", json={"gastos_fijos_semanales": 800000})
        data = res.json()
        indicadores = data.get("indicadores", {})
        assert "creditos_minimos" in indicadores
        assert indicadores["creditos_minimos"] >= 1
        print(f"PASS: creditos_minimos={indicadores['creditos_minimos']}")


# ── GET /api/cfo/plan-deudas (sin deudas) ─────────────────────────────────────
class TestPlanDeudas:
    def test_plan_deudas_no_error_500(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-deudas")
        assert res.status_code != 500, f"Got 500: {res.text[:200]}"
        assert res.status_code == 200
        print(f"PASS: GET /cfo/plan-deudas => {res.status_code}")

    def test_plan_deudas_responde_correctamente(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/plan-deudas")
        data = res.json()
        # Should have either semanas list or error/mensaje field
        assert "semanas" in data or "error" in data or "mensaje" in data
        print(f"PASS: plan-deudas response keys: {list(data.keys())}")


# ── GET /api/cfo/reporte-lunes ────────────────────────────────────────────────
class TestReporteLunes:
    def test_reporte_lunes_status(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/reporte-lunes")
        assert res.status_code == 200
        print("PASS: GET /cfo/reporte-lunes => 200")

    def test_reporte_lunes_semana_label(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/reporte-lunes")
        data = res.json()
        assert "semana_label" in data, f"Missing semana_label in {list(data.keys())}"
        print(f"PASS: semana_label={data['semana_label']}")

    def test_reporte_lunes_ingresos_recaudo(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/reporte-lunes")
        data = res.json()
        ingresos = data.get("ingresos", {})
        assert "recaudo_cartera" in ingresos
        print(f"PASS: recaudo_cartera={ingresos.get('recaudo_cartera')}")

    def test_reporte_lunes_caja_estado(self, client):
        res = client.get(f"{BASE_URL}/api/cfo/reporte-lunes")
        data = res.json()
        caja = data.get("caja", {})
        estado = caja.get("estado")
        # With gastos_fijos=0, caja = recaudo_sem - 0 - 0, should be >= 0 => verde
        assert estado in ["verde", "rojo", "amarillo"], f"Unexpected caja estado: {estado}"
        print(f"PASS: caja.estado={estado}")
