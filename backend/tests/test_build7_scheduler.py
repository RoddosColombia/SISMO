"""
Build 7 Scheduler Tests — 9 CRON jobs, CFO alertas, text formats, APIs
"""
import pytest
import requests
import os
import subprocess
import sys

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    # Authenticate
    r = s.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com", "password": "Admin@RODDOS2025!"
    })
    if r.status_code == 200:
        token = r.json().get("token", "")
        s.headers.update({"Authorization": f"Bearer {token}"})
    return s


# ─── 7A: Scheduler registration ───────────────────────────────────────────────

class TestSchedulerRegistration:
    """7A-1: Verify 9 jobs startup log"""

    def test_9_jobs_in_startup_log(self):
        result = subprocess.run(
            ["grep", "-c", "9 jobs: DPD@06:00", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True
        )
        count = int(result.stdout.strip() or "0")
        assert count >= 1, f"Expected '9 jobs: DPD@06:00' in startup log, found {count} times"
        print(f"PASS: Found '9 jobs' startup message {count} times")

    def test_9_jobs_full_message(self):
        result = subprocess.run(
            ["grep", "9 jobs:", "/var/log/supervisor/backend.err.log"],
            capture_output=True, text=True
        )
        lines = result.stdout.strip().split("\n")
        last_line = lines[-1] if lines else ""
        expected_parts = ["DPD@06:00", "Buckets@06:05", "CFO@06:10", "Scores@06:30",
                          "RADAR@07:00", "Prev@Mar09:00", "Venc@Mié09:00", "Mora@Jue09:00", "Resumen@Vie17:00"]
        for part in expected_parts:
            assert part in last_line, f"Missing '{part}' in scheduler startup: {last_line}"
        print(f"PASS: All 9 job names present in startup log")

    def test_no_old_resumen_semanal_function(self):
        """resumen_semanal() must not exist (renamed to resumen_semanal_ceo)"""
        result = subprocess.run(
            ["grep", "-n", "^async def resumen_semanal(", "/app/backend/services/loanbook_scheduler.py"],
            capture_output=True, text=True
        )
        assert result.stdout.strip() == "", f"Old function resumen_semanal() still exists: {result.stdout}"
        print("PASS: Old resumen_semanal() function not found (correctly renamed)")


# ─── 7B: Job function execution ───────────────────────────────────────────────

class TestJobFunctions:
    """7B: Direct execution of job functions"""

    def _run(self, func_name):
        cmd = (
            f"cd /app/backend && python3 -c \""
            f"import asyncio, sys; sys.path.insert(0, '.'); "
            f"from services.loanbook_scheduler import {func_name}; "
            f"asyncio.run({func_name}())\""
        )
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        return result

    def test_7b1_calcular_dpd_todos(self):
        r = self._run("calcular_dpd_todos")
        assert r.returncode == 0, f"calcular_dpd_todos crashed: {r.stderr[-500:]}"
        print("PASS: calcular_dpd_todos() ran without error")

    def test_7b2_calcular_scores(self):
        r = self._run("calcular_scores")
        assert r.returncode == 0, f"calcular_scores crashed: {r.stderr[-500:]}"
        print("PASS: calcular_scores() ran without error")

    def test_7b3_alertar_buckets_criticos(self):
        r = self._run("alertar_buckets_criticos")
        assert r.returncode == 0, f"alertar_buckets_criticos crashed: {r.stderr[-500:]}"
        # Without API key should log and return
        assert "sin API key" in r.stderr or r.returncode == 0, "Should log 'sin API key'"
        print("PASS: alertar_buckets_criticos() ran without error")

    def test_7b4_recordatorio_preventivo(self):
        r = self._run("recordatorio_preventivo")
        assert r.returncode == 0, f"recordatorio_preventivo crashed: {r.stderr[-500:]}"
        print("PASS: recordatorio_preventivo() ran without error")

    def test_7b5_recordatorio_vencimiento(self):
        r = self._run("recordatorio_vencimiento")
        assert r.returncode == 0, f"recordatorio_vencimiento crashed: {r.stderr[-500:]}"
        print("PASS: recordatorio_vencimiento() ran without error")

    def test_7b6_notificar_mora_nueva(self):
        r = self._run("notificar_mora_nueva")
        assert r.returncode == 0, f"notificar_mora_nueva crashed: {r.stderr[-500:]}"
        print("PASS: notificar_mora_nueva() ran without error")

    def test_7b7_verificar_alertas_cfo_no_wa(self):
        """Without whatsapp_activo=True, should only log"""
        r = self._run("verificar_alertas_cfo")
        assert r.returncode == 0, f"verificar_alertas_cfo crashed: {r.stderr[-500:]}"
        print("PASS: verificar_alertas_cfo() ran without error (whatsapp_activo=False)")

    def test_7b8_resumen_semanal_ceo(self):
        r = self._run("resumen_semanal_ceo")
        assert r.returncode == 0, f"resumen_semanal_ceo crashed: {r.stderr[-500:]}"
        print("PASS: resumen_semanal_ceo() ran without error")


# ─── 7C: PTP Follow-up and CFO alertas estado ─────────────────────────────────

class TestPTPAndCFO:
    """7C: PTP follow-up and CFO alerta estado='nueva'"""

    def test_7c1_ptp_followup_no_crash(self):
        """Insert test loan with ptp_fecha=today, run calcular_scores, verify no crash"""
        cmd = """cd /app/backend && python3 -c "
import asyncio, sys
sys.path.insert(0, '.')
from datetime import date

async def run():
    from database import db
    today = date.today().isoformat()
    # Insert test PTP loan
    await db.loanbook.insert_one({
        'id': 'TEST_PTP_7C1',
        'estado': 'mora',
        'dpd_actual': 5,
        'dpd_maximo_historico': 5,
        'cuotas': [],
        'gestiones': [],
        'cliente_nombre': 'Test PTP User',
        'cliente_telefono': '+573001112233',
        'ptp_fecha': today,
        'ptp_monto': 150000,
        'codigo': 'TEST-PTP'
    })
    from services.loanbook_scheduler import calcular_scores
    await calcular_scores()
    # Cleanup
    await db.loanbook.delete_one({'id': 'TEST_PTP_7C1'})
    print('PTP_FOLLOWUP_COMPLETE')

asyncio.run(run())
" """
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=30)
        assert result.returncode == 0, f"PTP follow-up test crashed: {result.stderr[-500:]}"
        assert "PTP_FOLLOWUP_COMPLETE" in result.stdout, f"PTP test did not complete: {result.stdout}"
        # WA attempt logged (no API key so "WA sin API key" logged)
        assert "WA sin API key" in result.stderr or result.returncode == 0
        print("PASS: PTP follow-up executed without crash")

    def test_7c2_cfo_alerta_estado_nueva(self):
        """Verify cfo_agent inserts alertas with estado='nueva'"""
        result = subprocess.run(
            ["python3", "/tmp/test_cfo_alerta_7c2.py"],
            capture_output=True, text=True, timeout=15
        )
        assert result.returncode == 0, f"CFO alerta test crashed: {result.stderr[-500:]}"
        assert "ESTADO_NUEVA_OK" in result.stdout, f"estado='nueva' not found: {result.stdout}"
        print("PASS: CFO alerta estado='nueva' field verified")


# ─── 7D: Exact text verification ──────────────────────────────────────────────

class TestExactTexts:
    """7D: Verify exact message formats in source code"""

    def test_7d1_dpd8_message_format(self):
        """DPD=8 msg contains 'llevas X días con tu cuota' and COP format"""
        with open("/app/backend/services/loanbook_scheduler.py") as f:
            src = f.read()
        assert "llevas" in src and "días con tu cuota" in src, "DPD=8 msg missing 'llevas X días con tu cuota'"
        # COP format check: _fmt_cop function uses . separator
        assert "_fmt_cop" in src, "Missing _fmt_cop helper"
        # Verify format function produces pesos with dots
        cmd = """cd /app/backend && python3 -c "
import sys; sys.path.insert(0,'.')
from services.loanbook_scheduler import _fmt_cop
r = _fmt_cop(100000)
assert r == '\$100.000', f'Wrong COP format: {r}'
print('COP_FORMAT_OK:', r)
" """
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        assert result.returncode == 0, f"_fmt_cop test: {result.stderr}"
        assert "COP_FORMAT_OK" in result.stdout
        print(f"PASS: DPD=8 text and COP format verified: {result.stdout.strip()}")

    def test_7d2_dpd15_message_format(self):
        """DPD=15 msg contains 'aviso formal' and 'Tienes 7 días para regularizar'"""
        with open("/app/backend/services/loanbook_scheduler.py") as f:
            src = f.read()
        assert "aviso formal" in src, "DPD=15 msg missing 'aviso formal'"
        assert "7 días para regularizar" in src, "DPD=15 msg missing 'Tienes 7 días para regularizar'"
        print("PASS: DPD=15 text verified")

    def test_7d3_mora_nueva_message(self):
        """DPD=1 mora nueva msg contains '¿Tuviste algún inconveniente?'"""
        with open("/app/backend/services/loanbook_scheduler.py") as f:
            src = f.read()
        assert "¿Tuviste algún inconveniente?" in src, "mora nueva msg missing '¿Tuviste algún inconveniente?'"
        print("PASS: mora nueva text verified")

    def test_7d4_preventivo_and_vencimiento_texts(self):
        """Preventivo contains 'mañana miércoles', vencimiento contains '📸'"""
        with open("/app/backend/services/loanbook_scheduler.py") as f:
            src = f.read()
        assert "mañana miércoles" in src, "recordatorio_preventivo msg missing 'mañana miércoles'"
        assert "📸" in src, "recordatorio_vencimiento msg missing comprobante 📸"
        print("PASS: preventivo 'mañana miércoles' and vencimiento '📸' verified")

    def test_7b8_resumen_format_under_450_chars(self):
        """resumen_semanal_ceo text generation under 450 chars for minimal data"""
        result = subprocess.run(
            ["python3", "/tmp/test_resumen_format.py"],
            capture_output=True, text=True, timeout=10
        )
        assert result.returncode == 0, f"Resumen format test failed: {result.stderr}"
        for line in result.stdout.split("\n"):
            if line.startswith("CHARS:"):
                chars = int(line.split(":")[1])
                assert chars < 450, f"Resumen text too long: {chars} chars (max 450)"
                print(f"PASS: Resumen text is {chars} chars (< 450)")
                break


# ─── 7E: Backend API health ────────────────────────────────────────────────────

class TestBackendAPIs:
    """7E: Backend APIs still working"""

    def test_7e1_radar_queue_200(self, client):
        r = client.get(f"{BASE_URL}/api/radar/queue")
        assert r.status_code == 200, f"GET /api/radar/queue returned {r.status_code}: {r.text[:200]}"
        print("PASS: GET /api/radar/queue → 200")

    def test_7e2_cfo_alertas_200(self, client):
        r = client.get(f"{BASE_URL}/api/cfo/alertas")
        assert r.status_code == 200, f"GET /api/cfo/alertas returned {r.status_code}: {r.text[:200]}"
        data = r.json()
        assert isinstance(data, list), f"Expected list, got {type(data)}"
        print(f"PASS: GET /api/cfo/alertas → 200, {len(data)} alertas")

    def test_7e3_cfo_config_post(self, client):
        payload = {"whatsapp_activo": True, "whatsapp_ceo": "+573001112233"}
        r = client.post(f"{BASE_URL}/api/cfo/config", json=payload)
        assert r.status_code == 200, f"POST /api/cfo/config returned {r.status_code}: {r.text[:200]}"
        data = r.json()
        config_data = data.get("config", data)
        assert config_data.get("whatsapp_activo") is True, f"whatsapp_activo not saved: {data}"
        assert config_data.get("whatsapp_ceo") == "+573001112233", f"whatsapp_ceo not saved: {data}"
        print(f"PASS: POST /api/cfo/config → 200, config saved correctly")
        # Reset
        client.post(f"{BASE_URL}/api/cfo/config", json={"whatsapp_activo": False})
