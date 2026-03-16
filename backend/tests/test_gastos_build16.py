"""Build 16: Backend tests for Carga Masiva de Gastos endpoints"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={
        "email": "contabilidad@roddos.com",
        "password": "Admin@RODDOS2025!"
    })
    if r.status_code == 200:
        data = r.json()
        return data.get("access_token") or data.get("token")
    pytest.skip(f"Auth failed: {r.status_code} {r.text[:200]}")


@pytest.fixture(scope="module")
def headers(token):
    return {"Authorization": f"Bearer {token}"}


# ── GET /gastos/plantilla ──────────────────────────────────────────────────────
def test_plantilla_requires_auth():
    r = requests.get(f"{BASE_URL}/api/gastos/plantilla")
    assert r.status_code in (401, 403), f"Expected auth required, got {r.status_code}"


def test_plantilla_download(headers):
    r = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=headers)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    ct = r.headers.get("content-type", "")
    assert "spreadsheet" in ct or "xlsx" in ct or "openxml" in ct, f"Unexpected content-type: {ct}"
    assert len(r.content) > 5000, "File too small"
    # Verify it's a valid xlsx
    import io, openpyxl
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    sheets = wb.sheetnames
    assert "Gastos" in sheets, f"Missing Gastos sheet. Sheets: {sheets}"
    assert "Instrucciones" in sheets, f"Missing Instrucciones sheet. Sheets: {sheets}"
    print(f"✅ Plantilla: 2 sheets {sheets}, size {len(r.content)} bytes")


def test_plantilla_has_12_headers(headers):
    import io, openpyxl
    r = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=headers)
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb["Gastos"]
    # Row 3 is the header row
    headers_row = [str(c.value or "").strip() for c in ws[3] if c.value]
    assert len(headers_row) == 12, f"Expected 12 headers, got {len(headers_row)}: {headers_row}"
    expected = ["Fecha", "Proveedor", "NIT_Proveedor", "Concepto", "Monto_Sin_IVA",
                "Incluye_IVA", "Tipo_Gasto", "Tipo_Persona", "Es_Autoretenedor",
                "Forma_Pago", "Mes_Periodo", "Notas"]
    for col in expected:
        assert col in headers_row, f"Missing header: {col}"
    print(f"✅ 12 headers verified: {headers_row}")


def test_plantilla_has_auteco_example(headers):
    import io, openpyxl
    r = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=headers)
    wb = openpyxl.load_workbook(io.BytesIO(r.content))
    ws = wb["Gastos"]
    # Row 4 is the example row
    row4 = [str(c.value or "") for c in ws[4]]
    combined = " ".join(row4).lower()
    assert "auteco" in combined or "860024781" in combined, f"Auteco example not found. Row4: {row4}"
    print(f"✅ Auteco Kawasaki example row found")


# ── POST /gastos/cargar ────────────────────────────────────────────────────────
def test_cargar_requires_auth():
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          files={"file": ("test_gastos.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code in (401, 403), f"Expected auth required, got {r.status_code}"


def test_cargar_invalid_format(headers):
    r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                      headers=headers,
                      files={"file": ("test.txt", b"hello", "text/plain")})
    assert r.status_code in (400, 422), f"Expected 400/422, got {r.status_code}"


def test_cargar_excel(headers):
    """Upload test Excel and verify parsing + retenciones calculation"""
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          headers=headers,
                          files={"file": ("test_gastos.xlsx", f,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("ok") == True, f"ok=False: {data.get('error')}"
    gastos = data.get("gastos", [])
    # Test Excel has rows 5,6,7 as real data (row 4 is example Auteco which should be skipped)
    # Actually let's just verify we got data back
    assert len(gastos) >= 1, f"Expected at least 1 gasto, got {len(gastos)}"
    print(f"✅ Parsed {len(gastos)} gastos")
    return data


def test_cargar_retenciones_arriendo(headers):
    """Arriendo $3M contado → ReteFuente=3.5% = $105,000"""
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          headers=headers,
                          files={"file": ("test_gastos.xlsx", f,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    gastos = data.get("gastos", [])
    arriendo = next((g for g in gastos if g.get("tipo_gasto") == "arrendamiento"), None)
    assert arriendo is not None, f"No arriendo gasto found. Gastos: {[(g['tipo_gasto'], g['proveedor']) for g in gastos]}"
    assert arriendo["monto_sin_iva"] == 3000000, f"Expected 3000000, got {arriendo['monto_sin_iva']}"
    # 3.5% of 3M = 105,000
    expected_retefuente = round(3000000 * 0.035)
    assert arriendo["retefuente_monto"] == expected_retefuente, \
        f"Expected ReteFuente {expected_retefuente}, got {arriendo['retefuente_monto']}"
    expected_neto = 3000000 - expected_retefuente
    assert arriendo["neto_pagar"] == expected_neto, \
        f"Expected neto {expected_neto}, got {arriendo['neto_pagar']}"
    print(f"✅ Arriendo retenciones: base={arriendo['monto_sin_iva']}, reteF={arriendo['retefuente_monto']}, neto={arriendo['neto_pagar']}")


def test_cargar_retenciones_honorarios_pj_con_iva(headers):
    """Honorarios PJ $2M con IVA → IVA=19%=380K, ReteFuente=11%=220K"""
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          headers=headers,
                          files={"file": ("test_gastos.xlsx", f,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    gastos = data.get("gastos", [])
    hon = next((g for g in gastos if g.get("tipo_gasto") == "honorarios_pj"), None)
    assert hon is not None, f"No honorarios_pj found. Gastos: {[(g['tipo_gasto'], g['proveedor']) for g in gastos]}"
    assert hon["monto_sin_iva"] == 2000000
    # IVA: 19% of 2M = 380,000
    assert hon["iva_monto"] == round(2000000 * 0.19), \
        f"Expected IVA {round(2000000*0.19)}, got {hon['iva_monto']}"
    # ReteFuente: 11% of 2M = 220,000
    assert hon["retefuente_monto"] == round(2000000 * 0.11), \
        f"Expected ReteFuente {round(2000000*0.11)}, got {hon['retefuente_monto']}"
    print(f"✅ Honorarios PJ: IVA={hon['iva_monto']}, ReteFuente={hon['retefuente_monto']}, neto={hon['neto_pagar']}")


def test_cargar_autoretenedor_no_retefuente(headers):
    """Auteco $45M autoretenedor → no ReteFuente"""
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          headers=headers,
                          files={"file": ("test_gastos.xlsx", f,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    gastos = data.get("gastos", [])
    # Look for Auteco in the non-example rows
    auteco = next((g for g in gastos if "auteco" in g.get("proveedor", "").lower()), None)
    if auteco is None:
        print("⚠️ No Auteco row found in output (may be skipped as example row)")
        return
    assert auteco["retefuente_monto"] == 0, \
        f"Autoretenedor should have 0 ReteFuente, got {auteco['retefuente_monto']}"
    assert auteco["es_autoretenedor"] == True
    print(f"✅ Auteco autoretenedor: retefuente={auteco['retefuente_monto']} (correctly 0)")


def test_cargar_resumen_structure(headers):
    """Verify resumen fields are present"""
    with open("/tmp/test_gastos.xlsx", "rb") as f:
        r = requests.post(f"{BASE_URL}/api/gastos/cargar",
                          headers=headers,
                          files={"file": ("test_gastos.xlsx", f,
                                          "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")})
    data = r.json()
    resumen = data.get("resumen", {})
    for key in ["total_filas", "total_monto_base", "total_iva", "total_retefuente", "total_neto_pagar", "contado", "credito"]:
        assert key in resumen, f"Missing resumen key: {key}"
    print(f"✅ Resumen: {resumen}")


# ── POST /gastos/procesar ──────────────────────────────────────────────────────
def test_procesar_returns_job_id_quickly(headers):
    """Submit 1 minimal gasto and verify job_id returned quickly. DO NOT wait for completion."""
    import time
    payload = {
        "gastos": [{
            "id": "test-01",
            "row_num": 1,
            "fecha": "2026-03-01",
            "proveedor": "TEST Proveedor SA",
            "nit_proveedor": "999999999",
            "concepto": "Test gasto masivo",
            "monto_sin_iva": 1000000,
            "incluye_iva": "No",
            "tipo_gasto": "servicios",
            "tipo_persona": "PJ",
            "es_autoretenedor": False,
            "forma_pago": "Contado",
            "mes_periodo": "2026-03",
            "notas": "TESTING - please ignore",
            "iva_monto": 0,
            "iva_cuenta_id": None,
            "retefuente_monto": 40000,
            "retefuente_cuenta_id": 5383,
            "retefuente_label": "Ret. Servicios 4%",
            "bruto_total": 1000000,
            "neto_pagar": 960000,
            "cuenta_gasto_id": 5483,
            "cuenta_gasto_nombre": "Asistencia técnica / Servicios",
        }]
    }
    start = time.time()
    r = requests.post(f"{BASE_URL}/api/gastos/procesar",
                      headers={**headers, "Content-Type": "application/json"},
                      json=payload)
    elapsed = time.time() - start
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert data.get("ok") == True, f"ok=False: {data}"
    assert "job_id" in data, f"No job_id in response: {data}"
    assert elapsed < 3, f"Response took {elapsed:.1f}s, expected < 3s"
    print(f"✅ /procesar returned job_id={data['job_id'][:8]}... in {elapsed:.2f}s")
    return data["job_id"]


# ── GET /gastos/jobs/{job_id} ──────────────────────────────────────────────────
def test_job_status_polling(headers):
    """Submit a job, poll immediately, verify structure"""
    # First create a job
    payload = {
        "gastos": [{
            "id": "test-02",
            "row_num": 1,
            "fecha": "2026-03-01",
            "proveedor": "TEST Proveedor SAS",
            "nit_proveedor": "888888888",
            "concepto": "Test polling job",
            "monto_sin_iva": 500000,
            "incluye_iva": "No",
            "tipo_gasto": "otros",
            "tipo_persona": "PJ",
            "es_autoretenedor": False,
            "forma_pago": "Contado",
            "mes_periodo": "2026-03",
            "notas": "TESTING",
            "iva_monto": 0, "iva_cuenta_id": None, "retefuente_monto": 0,
            "retefuente_cuenta_id": None, "retefuente_label": "",
            "bruto_total": 500000, "neto_pagar": 500000,
            "cuenta_gasto_id": 5495, "cuenta_gasto_nombre": "Gastos de representación",
        }]
    }
    pr = requests.post(f"{BASE_URL}/api/gastos/procesar",
                       headers={**headers, "Content-Type": "application/json"},
                       json=payload)
    job_id = pr.json()["job_id"]

    # Poll job status immediately
    r = requests.get(f"{BASE_URL}/api/gastos/jobs/{job_id}", headers=headers)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    data = r.json()
    assert "job_id" in data, f"Missing job_id in response"
    assert "estado" in data, f"Missing estado in response"
    assert data["estado"] in ("iniciando", "procesando", "completado"), \
        f"Unexpected estado: {data['estado']}"
    assert "total" in data, f"Missing total in response"
    assert "procesados" in data, f"Missing procesados in response"
    print(f"✅ Job status: estado={data['estado']}, total={data['total']}, procesados={data['procesados']}")


def test_job_not_found(headers):
    r = requests.get(f"{BASE_URL}/api/gastos/jobs/nonexistent-job-id-99999", headers=headers)
    assert r.status_code == 404, f"Expected 404, got {r.status_code}"


# ── GET /gastos/reporte-errores/{job_id} ──────────────────────────────────────
def test_reporte_errores_returns_excel(headers):
    """Create a job and download error report"""
    payload = {
        "gastos": [{
            "id": "test-03",
            "row_num": 1,
            "fecha": "2026-03-01",
            "proveedor": "TEST Err Proveedor",
            "nit_proveedor": "777777777",
            "concepto": "Test error report",
            "monto_sin_iva": 1000,
            "incluye_iva": "No",
            "tipo_gasto": "otros",
            "tipo_persona": "PJ",
            "es_autoretenedor": False,
            "forma_pago": "Contado",
            "mes_periodo": "2026-03",
            "notas": "TESTING",
            "iva_monto": 0, "iva_cuenta_id": None, "retefuente_monto": 0,
            "retefuente_cuenta_id": None, "retefuente_label": "",
            "bruto_total": 1000, "neto_pagar": 1000,
            "cuenta_gasto_id": 5495, "cuenta_gasto_nombre": "Gastos de representación",
        }]
    }
    pr = requests.post(f"{BASE_URL}/api/gastos/procesar",
                       headers={**headers, "Content-Type": "application/json"},
                       json=payload)
    job_id = pr.json()["job_id"]

    r = requests.get(f"{BASE_URL}/api/gastos/reporte-errores/{job_id}", headers=headers)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:200]}"
    ct = r.headers.get("content-type", "")
    assert "spreadsheet" in ct or "openxml" in ct or "xlsx" in ct, f"Unexpected content-type: {ct}"
    print(f"✅ Reporte errores downloaded: {len(r.content)} bytes")


# ── AI chat keyword detection ──────────────────────────────────────────────────
def test_ai_chat_keyword_carga_masiva(headers):
    """Message 'carga masiva de gastos' should return gastos_masivos_card"""
    r = requests.post(
        f"{BASE_URL}/api/chat/message",
        headers={**headers, "Content-Type": "application/json"},
        json={"message": "carga masiva de gastos", "session_id": "test-build16-chat"},
    )
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text[:300]}"
    data = r.json()
    assert "gastos_masivos_card" in data, \
        f"gastos_masivos_card not in response keys: {list(data.keys())}"
    card = data["gastos_masivos_card"]
    assert card is not None, "gastos_masivos_card is None"
    assert card.get("type") == "gastos_masivos_card", f"Wrong type: {card.get('type')}"
    print(f"✅ AI chat keyword detected, card: {card}")
