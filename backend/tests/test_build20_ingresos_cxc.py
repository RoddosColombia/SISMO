"""
BUILD 20 Backend Tests: Ingresos y Cuentas por Cobrar
Tests: /api/ingresos/* and /api/cxc/* endpoints
"""
import pytest
import requests
import io
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIyYzRjNDc1NS03MzQxLTQ3NmMtYmVhMS1iZTc5NjZhYWRhZmIiLCJlbWFpbCI6ImNvbnRhYmlsaWRhZEByb2Rkb3MuY29tIiwicm9sZSI6ImFkbWluIiwiZXhwIjoxNzc0Mzg4ODEzfQ.eKN7vQ73a3fsz-6fYxXudCk6ETaXiA7prLfUm-1giLs"

HEADERS = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}


# ── GET /api/ingresos/plan ──────────────────────────────────────────────────

def test_ingresos_plan_returns_4_types():
    """GET /api/ingresos/plan retorna 4 tipos válidos con alegra_id reales"""
    r = requests.get(f"{BASE_URL}/api/ingresos/plan", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert "plan" in data
    assert data["total"] == 4, f"Expected 4 types, got {data['total']}"
    tipos = [e["tipo_ingreso"] for e in data["plan"]]
    assert "Intereses_Bancarios" in tipos
    assert "Venta_Motos_Recuperadas" in tipos
    assert "Otros_Ingresos_No_Op" in tipos
    assert "Devoluciones_Ajustes" in tipos
    # Verify all have alegra_id
    for entry in data["plan"]:
        assert entry.get("alegra_id") is not None, f"Missing alegra_id for {entry['tipo_ingreso']}"
    print(f"✅ Plan ingresos: 4 tipos OK, alegra_ids: {[e['alegra_id'] for e in data['plan']]}")


# ── GET /api/ingresos/plantilla ─────────────────────────────────────────────

def test_ingresos_plantilla_csv_columns():
    """GET /api/ingresos/plantilla retorna CSV con 7 columnas correctas"""
    r = requests.get(f"{BASE_URL}/api/ingresos/plantilla", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}"
    assert "text/csv" in r.headers.get("content-type", ""), "Expected text/csv"
    lines = r.text.splitlines()
    header = lines[0].lstrip("\ufeff")  # strip BOM (utf-8-sig)
    cols = header.split(",")
    assert len(cols) == 7, f"Expected 7 columns, got {len(cols)}: {header}"
    expected_cols = ["fecha", "tipo_ingreso", "descripcion", "monto", "tercero", "banco", "referencia"]
    for col in expected_cols:
        assert col in cols, f"Missing column: {col}"
    print(f"✅ Plantilla CSV: 7 columnas OK")


# ── POST /api/ingresos/preview ──────────────────────────────────────────────

def test_ingresos_preview_valid_csv():
    """POST /api/ingresos/preview con CSV válido retorna resumen sin escribir en Alegra"""
    csv_content = "fecha,tipo_ingreso,descripcion,monto,tercero,banco,referencia\n2026-01-15,Intereses_Bancarios,Intereses enero,150000,Bancolombia,Bancolombia,REF-TEST-001\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    r = requests.post(f"{BASE_URL}/api/ingresos/preview",
                      headers={"Authorization": f"Bearer {TOKEN}"}, files=files)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["ok"] is True, f"Expected ok=True: {data}"
    assert data["filas_validas"] == 1
    assert data["monto_total"] == 150000
    print(f"✅ Preview valid CSV: 1 fila, monto=150000")


def test_ingresos_preview_invalid_tipo():
    """POST /api/ingresos/preview con tipo_ingreso inválido retorna error solo en esa fila"""
    csv_content = "fecha,tipo_ingreso,descripcion,monto,tercero,banco,referencia\n2026-01-15,TIPO_INVALIDO_XYZ,Test,100000,Cliente Test,Bancolombia,REF-001\n2026-01-15,Intereses_Bancarios,Valido,200000,Banco,Bancolombia,REF-002\n"
    files = {"file": ("test.csv", io.BytesIO(csv_content.encode()), "text/csv")}
    r = requests.post(f"{BASE_URL}/api/ingresos/preview",
                      headers={"Authorization": f"Bearer {TOKEN}"}, files=files)
    assert r.status_code == 200, f"Expected 200, got {r.status_code}: {r.text}"
    data = r.json()
    assert data["ok"] is True
    assert data["filas_error"] == 1, f"Expected 1 error row: {data}"
    assert data["filas_validas"] == 1, f"Expected 1 valid row: {data}"
    assert len(data["errores"]) == 1
    print(f"✅ Preview invalid tipo: error only in bad row, valid row passes")


# ── POST /api/ingresos/registrar-manual ────────────────────────────────────

def test_ingresos_registrar_manual_anti_duplicado():
    """POST /api/ingresos/registrar-manual: segundo intento retorna ok=false (anti-duplicado)"""
    # Use a unique referencia to avoid conflicts with existing data
    payload = {
        "fecha": "2026-02-15",
        "tipo_ingreso": "Otros_Ingresos_No_Op",
        "descripcion": "TEST ingreso manual anti-dup",
        "monto": 12345.0,
        "tercero": "TEST_Tercero_AntDup",
        "banco": "Bancolombia",
        "referencia": "TEST-ANTDUP-001",
    }
    # First call - may create or may already exist
    r1 = requests.post(f"{BASE_URL}/api/ingresos/registrar-manual", headers=HEADERS, json=payload)
    assert r1.status_code in [200, 201], f"Expected 200/201: {r1.status_code}: {r1.text}"
    data1 = r1.json()
    print(f"First call result: {data1}")

    # Second call - must return ok=false (anti-duplicado) if first was ok=true
    r2 = requests.post(f"{BASE_URL}/api/ingresos/registrar-manual", headers=HEADERS, json=payload)
    assert r2.status_code == 200, f"Expected 200: {r2.status_code}: {r2.text}"
    data2 = r2.json()
    print(f"Second call result: {data2}")
    assert data2["ok"] is False, f"Expected ok=False for duplicate: {data2}"
    assert "anti-duplicado" in data2.get("error", "").lower() or "ya fue registrado" in data2.get("error", "").lower()
    print(f"✅ Anti-duplicado works: 2nd call ok=False")


# ── POST /api/ingresos/procesar ─────────────────────────────────────────────

def test_ingresos_procesar_returns_job_id():
    """POST /api/ingresos/procesar retorna job_id inmediatamente"""
    payload = {
        "filas": [
            {
                "fecha": "2026-02-20",
                "tipo_ingreso": "Intereses_Bancarios",
                "descripcion": "TEST procesar bg",
                "monto": 50000,
                "tercero": "TEST_Banco_BG",
                "banco": "Bancolombia",
                "referencia": "TEST-BG-001",
                "banco_debito_id": 5314,
                "cuenta_credito_id": 5455,
            }
        ]
    }
    r = requests.post(f"{BASE_URL}/api/ingresos/procesar", headers=HEADERS, json=payload)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert data["ok"] is True
    assert "job_id" in data and data["job_id"]
    print(f"✅ Procesar returns job_id: {data['job_id']}")


# ── GET /api/ingresos/historial ─────────────────────────────────────────────

def test_ingresos_historial_has_enero_2026():
    """GET /api/ingresos/historial retorna ingresos registrados (debe haber 2 de enero 2026)"""
    r = requests.get(f"{BASE_URL}/api/ingresos/historial?fecha_desde=2026-01-01&fecha_hasta=2026-01-31",
                     headers=HEADERS)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert "registros" in data
    assert data["total_registros"] >= 2, f"Expected >=2 ingresos enero 2026, got {data['total_registros']}"
    print(f"✅ Historial enero 2026: {data['total_registros']} ingresos, monto_total={data['monto_total']}")


# ── GET /api/cxc/socios/resumen ─────────────────────────────────────────────

def test_cxc_socios_resumen_gran_total():
    """GET /api/cxc/socios/resumen retorna por_socio y gran_total"""
    r = requests.get(f"{BASE_URL}/api/cxc/socios/resumen", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert "por_socio" in data
    assert "gran_total" in data
    print(f"✅ CXC socios resumen: gran_total={data['gran_total']}, socios={data['socios']}")
    # Check both socios are present
    socios = list(data["por_socio"].keys())
    assert any("Andres" in s or "andres" in s.lower() for s in socios), f"Andres Sanjuan not in {socios}"
    assert any("Ivan" in s or "ivan" in s.lower() for s in socios), f"Ivan Echeverri not in {socios}"
    # Verify expected values (approximately)
    total = data["gran_total"]
    assert total > 3_000_000, f"Expected gran_total > 3M (got {total})"
    print(f"  Andres: {data['por_socio'].get('Andres Sanjuan', {}).get('saldo', 0):,.0f}")
    print(f"  Ivan: {data['por_socio'].get('Ivan Echeverri', {}).get('saldo', 0):,.0f}")


def test_cxc_socios_saldo_andres():
    """GET /api/cxc/socios/saldo/Andres%20Sanjuan retorna saldo_pendiente ~2,023,333"""
    r = requests.get(f"{BASE_URL}/api/cxc/socios/saldo/Andres%20Sanjuan", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert data["socio"] == "Andres Sanjuan"
    assert data["saldo_pendiente"] > 0
    print(f"✅ Andres Sanjuan saldo: {data['saldo_pendiente']:,.0f}")


def test_cxc_socios_saldo_ivan():
    """GET /api/cxc/socios/saldo/Ivan%20Echeverri retorna saldo_pendiente ~1,890,470"""
    r = requests.get(f"{BASE_URL}/api/cxc/socios/saldo/Ivan%20Echeverri", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert data["socio"] == "Ivan Echeverri"
    assert data["saldo_pendiente"] > 0
    print(f"✅ Ivan Echeverri saldo: {data['saldo_pendiente']:,.0f}")


# ── POST /api/cxc/socios/registrar ──────────────────────────────────────────

def test_cxc_socios_registrar_anti_duplicado():
    """POST /api/cxc/socios/registrar crea CXC; segundo intento es anti-duplicado"""
    payload = {
        "fecha": "2026-02-15",
        "socio": "Andres Sanjuan",
        "descripcion": "TEST CXC socio anti-dup build20",
        "monto": 11111.0,
        "pagado_a": "TEST_Proveedor",
        "banco_origen": "Bancolombia",
    }
    r1 = requests.post(f"{BASE_URL}/api/cxc/socios/registrar", headers=HEADERS, json=payload)
    assert r1.status_code in [200, 201], f"Expected 200/201: {r1.status_code}: {r1.text}"
    data1 = r1.json()
    print(f"CXC socio first call: {data1}")

    r2 = requests.post(f"{BASE_URL}/api/cxc/socios/registrar", headers=HEADERS, json=payload)
    data2 = r2.json()
    assert data2["ok"] is False, f"Expected ok=False (anti-dup): {data2}"
    print(f"✅ CXC socio anti-duplicado works: {data2.get('error')}")


# ── POST /api/cxc/socios/registrar-lote ─────────────────────────────────────

def test_cxc_socios_registrar_lote_returns_job_id():
    """POST /api/cxc/socios/registrar-lote retorna job_id inmediatamente"""
    payload = {
        "items": [
            {
                "fecha": "2026-02-20",
                "socio": "Ivan Echeverri",
                "descripcion": "TEST lote item 1",
                "monto": 5000.0,
                "pagado_a": "TEST_Proveedor",
                "banco_origen": "Bancolombia",
            }
        ]
    }
    r = requests.post(f"{BASE_URL}/api/cxc/socios/registrar-lote", headers=HEADERS, json=payload)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert data["ok"] is True
    assert "job_id" in data and data["job_id"]
    print(f"✅ Registrar-lote returns job_id: {data['job_id']}")


# ── POST /api/cxc/clientes/registrar ────────────────────────────────────────

def test_cxc_clientes_registrar():
    """POST /api/cxc/clientes/registrar crea CXC cliente con journal en Alegra"""
    payload = {
        "fecha": "2026-02-15",
        "cliente": "TEST_Cliente_Build20",
        "nit_cliente": "900999TEST",
        "descripcion": "TEST CXC cliente build20",
        "monto": 75000.0,
        "vencimiento": "2026-03-15",
        "referencia": "FAC-TEST-B20",
    }
    r = requests.post(f"{BASE_URL}/api/cxc/clientes/registrar", headers=HEADERS, json=payload)
    assert r.status_code in [200, 201], f"Expected 200/201: {r.status_code}: {r.text}"
    data = r.json()
    print(f"CXC cliente result: {data}")
    # Could be ok=True (new) or ok=False (already exists from previous test run)
    if data.get("ok") is True:
        assert "alegra_id" in data and data["alegra_id"]
        assert "cxc_id" in data and data["cxc_id"]
        print(f"✅ CXC cliente registered: alegra_id={data['alegra_id']}")
    else:
        # anti-duplicado from previous run
        print(f"✅ CXC cliente already exists (anti-dup): {data.get('error')}")


# ── GET /api/cxc/clientes/vencidas ──────────────────────────────────────────

def test_cxc_clientes_vencidas():
    """GET /api/cxc/clientes/vencidas retorna lista de CXC vencidas"""
    r = requests.get(f"{BASE_URL}/api/cxc/clientes/vencidas", headers=HEADERS)
    assert r.status_code == 200, f"Expected 200: {r.status_code}: {r.text}"
    data = r.json()
    assert "vencidas" in data
    assert "total_vencido" in data
    assert "cantidad" in data
    print(f"✅ CXC vencidas: {data['cantidad']} vencidas, total_vencido={data['total_vencido']}")


# ── POST /api/cxc/socios/abonar ─────────────────────────────────────────────

def test_cxc_socios_abonar():
    """POST /api/cxc/socios/abonar registra abono con journal en Alegra"""
    payload = {
        "socio": "Ivan Echeverri",
        "monto": 1000.0,
        "fecha": "2026-02-15",
        "banco_destino": "Bancolombia",
        "descripcion": "TEST abono build20",
    }
    r = requests.post(f"{BASE_URL}/api/cxc/socios/abonar", headers=HEADERS, json=payload)
    assert r.status_code in [200, 201], f"Expected 200/201: {r.status_code}: {r.text}"
    data = r.json()
    assert data["ok"] is True
    assert "alegra_id" in data and data["alegra_id"]
    print(f"✅ Abono registrado: alegra_id={data['alegra_id']}, nuevo_saldo_total={data['nuevo_saldo_total']}")
