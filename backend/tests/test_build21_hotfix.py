"""
BUILD 21 HOTFIX Tests:
- BUG 1: LoanBook pago registration (KeyError fix + descriptive errors)
- BUG 2: Excel/PDF download with auth
- MEJORA: Chat pendientes endpoints
"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
LOAN_ID = "60623115-35f0-4407-9565-24ecd599ba48"


@pytest.fixture(scope="module")
def auth_token():
    res = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "test1234"
    })
    if res.status_code != 200:
        pytest.skip(f"Auth failed: {res.status_code} {res.text}")
    token = res.json().get("access_token") or res.json().get("token")
    if not token:
        pytest.skip("No token in response")
    return token


@pytest.fixture(scope="module")
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ── BUG 1: Loanbook pago ─────────────────────────────────────────────────────

class TestLoanbookPago:
    """BUG 1: Payment registration with descriptive errors"""

    def test_pago_cuota_ya_pagada_descriptive_error(self, auth_headers):
        """Cuota 2 of LB-2026-0016 is already paid — expect 400 with 'ya fue registrada'"""
        res = requests.post(
            f"{BASE_URL}/api/loanbook/{LOAN_ID}/pago",
            json={"cuota_numero": 2, "valor_pagado": 130000, "metodo_pago": "efectivo", "notas": "test"},
            headers=auth_headers
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}: {res.text}"
        detail = res.json().get("detail", "")
        assert "ya fue registrada" in detail.lower() or "pagada" in detail.lower(), \
            f"Expected descriptive error, got: {detail}"
        print(f"PASS: cuota ya pagada → {res.status_code}: {detail}")

    def test_pago_estado_incorrecto_descriptive_error(self, auth_headers):
        """LB in pendiente_entrega should return 400 with descriptive Spanish message"""
        # Find a loan in pendiente_entrega state to test
        loans_res = requests.get(f"{BASE_URL}/api/loanbook?limit=50", headers=auth_headers)
        if loans_res.status_code != 200:
            pytest.skip("Can't list loanbooks")
        
        loans = loans_res.json()
        if isinstance(loans, dict):
            loans = loans.get("items", loans.get("data", []))
        
        pending_loan = next((l for l in loans if l.get("estado") == "pendiente_entrega"), None)
        if not pending_loan:
            pytest.skip("No loan in pendiente_entrega state found")
        
        res = requests.post(
            f"{BASE_URL}/api/loanbook/{pending_loan['id']}/pago",
            json={"cuota_numero": 1, "valor_pagado": 100000, "metodo_pago": "efectivo"},
            headers=auth_headers
        )
        assert res.status_code == 400, f"Expected 400, got {res.status_code}"
        detail = res.json().get("detail", "")
        assert "pendiente_entrega" in detail or "entrega" in detail.lower() or "estado" in detail.lower(), \
            f"Expected descriptive state error, got: {detail}"
        print(f"PASS: pendiente_entrega → {res.status_code}: {detail}")

    def test_pago_otro_loanbook_activo_no_500(self, auth_headers):
        """Find another active loanbook and attempt payment — must not return 500"""
        loans_res = requests.get(f"{BASE_URL}/api/loanbook?limit=50", headers=auth_headers)
        if loans_res.status_code != 200:
            pytest.skip(f"Can't list loanbooks: {loans_res.status_code}")
        
        loans = loans_res.json()
        if isinstance(loans, dict):
            loans = loans.get("items", loans.get("data", []))
        
        active_loans = [l for l in loans if l.get("estado") in ("activo", "mora") and l.get("id") != LOAN_ID]
        if not active_loans:
            pytest.skip("No other active loanbook found")
        
        loan = active_loans[0]
        cuotas = loan.get("cuotas", [])
        unpaid = next((c for c in cuotas if c.get("estado") != "pagada"), None)
        if not unpaid:
            pytest.skip("No unpaid cuota found in active loan")
        
        res = requests.post(
            f"{BASE_URL}/api/loanbook/{loan['id']}/pago",
            json={"cuota_numero": unpaid["numero"], "valor_pagado": unpaid.get("valor_cuota", 100000), "metodo_pago": "efectivo", "notas": "TEST_pago"},
            headers=auth_headers
        )
        assert res.status_code != 500, f"Got unexpected 500: {res.text}"
        assert res.status_code in (200, 201, 400), f"Unexpected status: {res.status_code}: {res.text}"
        print(f"PASS: otro loanbook pago → {res.status_code}")


# ── BUG 2: Excel/PDF Downloads ───────────────────────────────────────────────

class TestExcelPdfDownload:
    """BUG 2: Authenticated file downloads"""

    def test_excel_con_auth_retorna_200(self, auth_headers):
        """Excel download with auth must return 200 with excel content-type"""
        res = requests.get(
            f"{BASE_URL}/api/cfo/estado-resultados/excel?periodo=2026-01",
            headers=auth_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        ct = res.headers.get("content-type", "")
        assert "spreadsheet" in ct or "excel" in ct or "octet" in ct, \
            f"Expected excel content-type, got: {ct}"
        print(f"PASS: Excel download → {res.status_code}, content-type: {ct}")

    def test_pdf_con_auth_retorna_200(self, auth_headers):
        """PDF download with auth must return 200 with pdf content-type"""
        res = requests.get(
            f"{BASE_URL}/api/cfo/estado-resultados/pdf?periodo=2026-01",
            headers=auth_headers
        )
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text[:200]}"
        ct = res.headers.get("content-type", "")
        assert "pdf" in ct or "octet" in ct, f"Expected pdf content-type, got: {ct}"
        print(f"PASS: PDF download → {res.status_code}, content-type: {ct}")

    def test_pdf_sin_auth_retorna_401(self):
        """PDF without auth must return 401"""
        res = requests.get(f"{BASE_URL}/api/cfo/estado-resultados/pdf?periodo=2026-01")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print(f"PASS: PDF sin auth → {res.status_code}")

    def test_excel_sin_auth_retorna_401(self):
        """Excel without auth must return 401"""
        res = requests.get(f"{BASE_URL}/api/cfo/estado-resultados/excel?periodo=2026-01")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print(f"PASS: Excel sin auth → {res.status_code}")


# ── MEJORA: Chat Pendientes ──────────────────────────────────────────────────

class TestChatPendientes:
    """MEJORA: Chat pending topics endpoints"""

    def test_get_pendientes_retorna_estructura(self, auth_headers):
        """GET /api/chat/pendientes returns {pendientes:[], total:N}"""
        res = requests.get(f"{BASE_URL}/api/chat/pendientes", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert "pendientes" in data, f"Missing 'pendientes' key: {data}"
        assert "total" in data, f"Missing 'total' key: {data}"
        assert isinstance(data["pendientes"], list), "pendientes must be a list"
        print(f"PASS: GET pendientes → {res.status_code}: total={data['total']}")

    def test_delete_pendiente_individual(self, auth_headers):
        """DELETE /api/chat/pendientes/{key} must return ok"""
        res = requests.delete(
            f"{BASE_URL}/api/chat/pendientes/test_key_nonexistent",
            headers=auth_headers
        )
        # Even if not found, should return ok (upsert-style)
        assert res.status_code in (200, 404), f"Unexpected: {res.status_code}: {res.text}"
        print(f"PASS: DELETE pendiente → {res.status_code}")

    def test_delete_todos_pendientes(self, auth_headers):
        """DELETE /api/chat/pendientes must return ok with descartados count"""
        res = requests.delete(f"{BASE_URL}/api/chat/pendientes", headers=auth_headers)
        assert res.status_code == 200, f"Expected 200, got {res.status_code}: {res.text}"
        data = res.json()
        assert data.get("ok") is True, f"Expected ok=True: {data}"
        assert "descartados" in data, f"Missing 'descartados' key: {data}"
        print(f"PASS: DELETE todos pendientes → {res.status_code}: {data}")

    def test_get_pendientes_sin_auth_retorna_401(self):
        """GET pendientes without auth must return 401"""
        res = requests.get(f"{BASE_URL}/api/chat/pendientes")
        assert res.status_code == 401, f"Expected 401, got {res.status_code}"
        print(f"PASS: GET pendientes sin auth → {res.status_code}")
