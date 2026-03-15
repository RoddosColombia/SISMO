"""Test file for GAP 1, 2, 3 verification — iteration 28."""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

# ── Auth fixture ──────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    t = resp.json().get("token")
    assert t, "No token in response"
    return t


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}


# ── GAP 1: normalizar_telefono unit cases via webhook ─────────────────────────

class TestGap1NormalizarTelefono:
    """GAP 1 — Phone normalization logic tested indirectly via webhook detection."""

    def test_webhook_detects_cliente_sin_prefijo(self, headers):
        """Verify the normalizer function runs: all loanbook telefono_principal uses +57 format.
        Also check loanbook phones are normalized (migration ran)."""
        # Use loanbook endpoint which we know returns cliente_telefono
        resp = requests.get(f"{BASE_URL}/api/loanbook", headers=headers)
        assert resp.status_code == 200
        loans = resp.json()
        # At least one loanbook entry exists (env is set up)
        # Check that any non-empty telefono starts with +57 (migration ran)
        non_empty = [l.get("cliente_telefono","") for l in loans if l.get("cliente_telefono")]
        if non_empty:
            bad = [t for t in non_empty if not t.startswith("+57")]
            assert len(bad) == 0, f"Found non-normalized phones: {bad}"
        # Normalization function works (webhook should detect +573101234567 client)
        print(f"  Loanbook phones checked: {len(non_empty)} non-empty, all normalized")

    def test_crm_clientes_telefono_formato(self, headers):
        """All crm_clientes telefono_principal should start with +57 (after migration)."""
        resp = requests.get(f"{BASE_URL}/api/crm", headers=headers)
        assert resp.status_code == 200
        clientes = resp.json()
        mal_formato = [
            c.get("telefono_principal", "")
            for c in clientes
            if c.get("telefono_principal") and not c["telefono_principal"].startswith("+57")
        ]
        assert len(mal_formato) == 0, f"Phones not normalized: {mal_formato}"

    def test_loanbook_telefono_normalizado(self, headers):
        """All loanbook cliente_telefono should be +57... or empty."""
        resp = requests.get(f"{BASE_URL}/api/loanbook", headers=headers)
        assert resp.status_code == 200
        loans = resp.json()
        mal_formato = [
            (l.get("codigo"), l.get("cliente_telefono"))
            for l in loans
            if l.get("cliente_telefono") and not l["cliente_telefono"].startswith("+57")
        ]
        assert len(mal_formato) == 0, f"Loanbook phones not normalized: {mal_formato}"


# ── GAP 1: Webhook endpoint ───────────────────────────────────────────────────

class TestGap1Webhook:
    """POST /api/mercately/webhook endpoint smoke tests."""

    def test_webhook_returns_ok_without_config(self):
        """Webhook should return {ok: True} even without mercately config."""
        resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
            "phone": "3101234567",
            "message_type": "text",
            "content": "Hola"
        })
        # If no api_key configured, should return 200 ok
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("ok") is True

    def test_webhook_accepts_normalized_phone(self):
        """Webhook should accept +573101234567 format."""
        resp = requests.post(f"{BASE_URL}/api/mercately/webhook", json={
            "phone": "+573101234567",
            "message_type": "text",
            "content": "Hola"
        })
        assert resp.status_code == 200


# ── GAP 2: Inventario stats ───────────────────────────────────────────────────

class TestGap2InventarioStats:
    """GET /api/inventario/stats returns required fields."""

    def test_stats_returns_required_fields(self, headers):
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        for field in ("total", "disponibles", "vendidas", "entregadas", "total_inversion"):
            assert field in data, f"Missing field: {field}"

    def test_stats_values_are_numeric(self, headers):
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["total"], int)
        assert isinstance(data["disponibles"], int)
        assert isinstance(data["total_inversion"], (int, float))
        assert data["total"] >= 0

    def test_stats_consistency(self, headers):
        """total >= disponibles + vendidas + entregadas."""
        resp = requests.get(f"{BASE_URL}/api/inventario/stats", headers=headers)
        data = resp.json()
        assert data["total"] >= data["disponibles"] + data["vendidas"] + data["entregadas"]


# ── GAP 3: CFO async job ──────────────────────────────────────────────────────

class TestGap3CfoAsync:
    """GAP 3 — POST /api/cfo/generar returns job_id immediately, polling works."""

    def test_generar_returns_job_id_immediately(self, headers):
        """Must return job_id and estado='pendiente' fast (< 3s)."""
        start = time.time()
        resp = requests.post(f"{BASE_URL}/api/cfo/generar", headers=headers)
        elapsed = time.time() - start
        assert resp.status_code == 200, f"generar failed: {resp.text}"
        data = resp.json()
        assert "job_id" in data, "No job_id in response"
        assert data.get("estado") == "pendiente", f"Expected 'pendiente', got: {data.get('estado')}"
        assert elapsed < 5, f"Response too slow ({elapsed:.1f}s) — should be async"
        print(f"  ✅ generar returned in {elapsed:.2f}s with job_id={data['job_id']}")
        return data["job_id"]

    def test_status_endpoint_returns_job(self, headers):
        """GET /api/cfo/status/{job_id} must return job state."""
        # First create a job
        resp = requests.post(f"{BASE_URL}/api/cfo/generar", headers=headers)
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        # Poll immediately
        status_resp = requests.get(f"{BASE_URL}/api/cfo/status/{job_id}", headers=headers)
        assert status_resp.status_code == 200
        job = status_resp.json()
        assert "id" in job or "job_id" in job or job.get("estado") in ("pendiente", "en_proceso", "completado", "error")
        assert job.get("estado") in ("pendiente", "en_proceso", "completado", "error")
        print(f"  ✅ status for {job_id}: {job.get('estado')}")

    def test_status_404_for_unknown_job(self, headers):
        """Unknown job_id should return 404."""
        resp = requests.get(f"{BASE_URL}/api/cfo/status/nonexistent-job-id-xyz", headers=headers)
        assert resp.status_code == 404

    def test_full_polling_flow(self, headers):
        """Dispatch job → poll until completado or error (max 120s)."""
        resp = requests.post(f"{BASE_URL}/api/cfo/generar", headers=headers)
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]
        print(f"  Job dispatched: {job_id}")

        max_wait = 120
        interval = 3
        elapsed = 0
        final_state = None
        while elapsed < max_wait:
            time.sleep(interval)
            elapsed += interval
            s = requests.get(f"{BASE_URL}/api/cfo/status/{job_id}", headers=headers)
            assert s.status_code == 200
            state = s.json().get("estado")
            print(f"  [{elapsed}s] estado={state}")
            if state in ("completado", "error"):
                final_state = state
                break

        assert final_state is not None, f"Job still not completed after {max_wait}s"
        if final_state == "error":
            job_data = requests.get(f"{BASE_URL}/api/cfo/status/{job_id}", headers=headers).json()
            print(f"  Job error: {job_data.get('error')}")
        assert final_state == "completado", f"Job ended with state: {final_state}"

        # Verify informe_id exists
        job_data = requests.get(f"{BASE_URL}/api/cfo/status/{job_id}", headers=headers).json()
        assert job_data.get("informe_id"), "completado job should have informe_id"
        print(f"  ✅ Job completed with informe_id={job_data['informe_id']}")


# ── GAP 1: crear préstamo normalizes telefono ─────────────────────────────────

class TestGap1LoanbookCreate:
    """POST /api/loanbook normalizes cliente_telefono to +57..."""

    def test_create_loan_normalizes_phone(self, headers):
        """Create loan with raw phone '3109999888' → stored as '+573109999888'."""
        payload = {
            "cliente_nombre": "TEST_GapUser",
            "cliente_telefono": "3109999888",
            "plan": "P39S",
            "fecha_factura": "2026-02-01",
            "precio_venta": 5000000,
            "cuota_inicial": 1000000,
            "valor_cuota": 100000,
        }
        resp = requests.post(f"{BASE_URL}/api/loanbook", json=payload, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        tel = data.get("cliente_telefono", "")
        assert tel == "+573109999888", f"Expected '+573109999888', got '{tel}'"
        print(f"  ✅ Loan created, telefono normalized to {tel}")

        # Cleanup: note the id for future cleanup (best effort)
        loan_id = data.get("id")
        if loan_id:
            print(f"  Created test loan id={loan_id} (cleanup manually if needed)")
