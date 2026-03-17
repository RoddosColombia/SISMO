"""
Test suite for CSV-only gastos upload (iteration 52).
Tests: GET /gastos/plantilla, POST /gastos/cargar CSV/XLSX validation.
"""
import pytest
import requests
import os
import io

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyYzRjNDc1NS03MzQxLTQ3NmMtYmVhMS1iZTc5NjZhYWRhZmIiLCJlbWFpbCI6ImNvbnRhYmlsaWRhZEByb2Rkb3MuY29tIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzc0Mzg1NDkzfQ.v-AdYEWJZ9G0KEAdDlF2w0iMVxuRHFtxc91l3QvLih8"

HEADERS = {"Authorization": f"Bearer {TOKEN}"}

VALID_CSV = (
    "fecha,categoria,subcategoria,descripcion,monto,proveedor,referencia\n"
    "2026-01-05,Operaciones,Arriendo,Arriendo sede enero,3500000,Inmobiliaria SAS,FAC-001\n"
    "2026-01-10,Personal,Honorarios,Asesoria contable,1200000,Juan Garcia,HO-001\n"
)

INVALID_CAT_CSV = (
    "fecha,categoria,subcategoria,descripcion,monto,proveedor,referencia\n"
    "2026-01-05,CategoriaInexistente,SubcatInexistente,Test gasto,500000,Proveedor Test,REF-001\n"
)

INVALID_SUBCAT_CSV = (
    "fecha,categoria,subcategoria,descripcion,monto,proveedor,referencia\n"
    "2026-01-05,Operaciones,SubcategoriaInexistente,Test gasto,500000,Proveedor Test,REF-002\n"
)


# 1. GET /gastos/plantilla — retorna CSV
def test_plantilla_content_type():
    res = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=HEADERS)
    assert res.status_code == 200, f"Expected 200, got {res.status_code}"
    ct = res.headers.get("content-type", "")
    assert "text/csv" in ct, f"Expected text/csv content-type, got: {ct}"
    print(f"✅ Content-Type: {ct}")


def test_plantilla_filename_is_csv():
    res = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=HEADERS)
    assert res.status_code == 200
    cd = res.headers.get("content-disposition", "")
    assert ".csv" in cd, f"Expected .csv in Content-Disposition, got: {cd}"
    assert ".xlsx" not in cd, f"Should not have .xlsx in Content-Disposition"
    print(f"✅ Content-Disposition: {cd}")


def test_plantilla_has_7_columns():
    res = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=HEADERS)
    assert res.status_code == 200
    text = res.text
    # Find header line (non-comment)
    for line in text.splitlines():
        if not line.strip().startswith("#") and line.strip():
            cols = [c.strip().lstrip("\ufeff") for c in line.split(",")]  # strip BOM
            assert cols == ["fecha", "categoria", "subcategoria", "descripcion", "monto", "proveedor", "referencia"], \
                f"Columns mismatch: {cols}"
            print(f"✅ 7 columns present: {cols}")
            return
    pytest.fail("No header line found in CSV template")


def test_plantilla_has_comment_lines():
    res = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=HEADERS)
    text = res.text
    comment_lines = [l for l in text.splitlines() if l.strip().startswith("#")]
    assert len(comment_lines) > 0, "Expected comment lines starting with '#'"
    print(f"✅ Found {len(comment_lines)} comment lines")


# 2. POST /gastos/cargar — reject .xlsx
def test_cargar_rejects_xlsx():
    fake_xlsx = b"PK\x03\x04fake xlsx content"
    files = {"file": ("gastos.xlsx", io.BytesIO(fake_xlsx), "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    assert res.status_code == 200  # API returns 200 with ok=False
    data = res.json()
    assert data.get("ok") is False, f"Expected ok=False for .xlsx, got: {data}"
    # Check for 'convierte' or 'csv' in error message
    error_msg = (data.get("error") or "").lower()
    assert "csv" in error_msg or "convierte" in error_msg, f"Error should mention csv/convierte: {error_msg}"
    print(f"✅ .xlsx rejected: {data.get('error')[:80]}")


# 3. POST /gastos/cargar — valid CSV with correct categories
def test_cargar_valid_csv_returns_ok():
    files = {"file": ("gastos.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True, f"Expected ok=True, got: {data}"
    assert data.get("total_filas") == 2, f"Expected 2 rows, got: {data.get('total_filas')}"
    print(f"✅ Valid CSV processed: {data.get('total_filas')} gastos")


def test_cargar_valid_csv_cuenta_operaciones_arriendo():
    """Operaciones/Arriendo should map to alegra_id 5480."""
    files = {"file": ("gastos.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    data = res.json()
    assert data.get("ok") is True
    gastos = data.get("gastos", [])
    arriendo = next((g for g in gastos if "Arriendo" in g.get("subcategoria", "")), None)
    assert arriendo is not None, "Arriendo row not found"
    assert arriendo["cuenta_gasto_id"] == 5480, f"Expected 5480, got: {arriendo['cuenta_gasto_id']}"
    print(f"✅ Operaciones/Arriendo → cuenta_id={arriendo['cuenta_gasto_id']} ({arriendo['cuenta_gasto_nombre']})")


def test_cargar_valid_csv_cuenta_personal_honorarios():
    """Personal/Honorarios should map to alegra_id 5475."""
    files = {"file": ("gastos.csv", io.BytesIO(VALID_CSV.encode("utf-8")), "text/csv")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    data = res.json()
    gastos = data.get("gastos", [])
    honorarios = next((g for g in gastos if g.get("subcategoria") == "Honorarios"), None)
    assert honorarios is not None, "Honorarios row not found"
    assert honorarios["cuenta_gasto_id"] == 5475, f"Expected 5475, got: {honorarios['cuenta_gasto_id']}"
    print(f"✅ Personal/Honorarios → cuenta_id={honorarios['cuenta_gasto_id']}")


# 4. Fallback for invalid category
def test_cargar_invalid_category_uses_fallback_5493():
    files = {"file": ("gastos.csv", io.BytesIO(INVALID_CAT_CSV.encode("utf-8")), "text/csv")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True, f"Should not reject invalid category, got: {data}"
    gastos = data.get("gastos", [])
    assert len(gastos) == 1
    assert gastos[0]["cuenta_gasto_id"] == 5493, f"Expected fallback 5493, got: {gastos[0]['cuenta_gasto_id']}"
    advertencias = data.get("advertencias", [])
    assert len(advertencias) > 0, "Should have warnings for invalid category"
    print(f"✅ Invalid category fallback to 5493, warning: {advertencias[0][:80]}")


# 5. Fallback for invalid subcategory (valid category)
def test_cargar_invalid_subcategory_uses_fallback_5493():
    files = {"file": ("gastos.csv", io.BytesIO(INVALID_SUBCAT_CSV.encode("utf-8")), "text/csv")}
    res = requests.post(f"{BASE_URL}/api/gastos/cargar", headers=HEADERS, files=files)
    assert res.status_code == 200
    data = res.json()
    assert data.get("ok") is True, f"Should not reject invalid subcategory, got: {data}"
    gastos = data.get("gastos", [])
    assert len(gastos) == 1
    assert gastos[0]["cuenta_gasto_id"] == 5493, f"Expected fallback 5493, got: {gastos[0]['cuenta_gasto_id']}"
    advertencias = data.get("advertencias", [])
    assert len(advertencias) > 0, "Should have warnings for invalid subcategory"
    print(f"✅ Invalid subcategory fallback to 5493, warning: {advertencias[0][:80]}")
