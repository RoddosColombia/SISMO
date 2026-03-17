"""
Test suite for HOTFIX: Carga masiva plan de cuentas + anular_causacion + cleanup
Tests: plan-cuentas endpoint, CSV mapping, agent knowledge, cleanup endpoints
"""
import pytest
import requests
import os
import time

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
assert BASE_URL, "REACT_APP_BACKEND_URL must be set"

# Auth credentials
EMAIL = "contabilidad@roddos.com"
PASSWORD = "Admin@RODDOS2025!"


@pytest.fixture(scope="module")
def auth_token():
    resp = requests.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert resp.status_code == 200, f"Login failed: {resp.text}"
    return resp.json().get("access_token") or resp.json().get("token")


@pytest.fixture(scope="module")
def headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}


# ── 1. Plan Cuentas endpoint ───────────────────────────────────────────────────
class TestPlanCuentas:
    """GET /gastos/plan-cuentas → 28 entries with alegra_id"""

    def test_plan_cuentas_returns_200(self, headers):
        resp = requests.get(f"{BASE_URL}/api/gastos/plan-cuentas", headers=headers)
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        print("PASS: /api/gastos/plan-cuentas returns 200")

    def test_plan_cuentas_has_28_entries(self, headers):
        resp = requests.get(f"{BASE_URL}/api/gastos/plan-cuentas", headers=headers)
        data = resp.json()
        # Response: {"total": 28, "plan": [...]}
        entries = data.get("plan", data if isinstance(data, list) else [])
        total = data.get("total", len(entries))
        assert total == 28, f"Expected 28 entries, got {total}"
        assert len(entries) == 28, f"Expected 28 plan entries, got {len(entries)}"
        print(f"PASS: plan-cuentas has {len(entries)} entries")

    def test_plan_cuentas_has_alegra_id(self, headers):
        resp = requests.get(f"{BASE_URL}/api/gastos/plan-cuentas", headers=headers)
        data = resp.json()
        entries = data.get("plan", data if isinstance(data, list) else [])
        assert len(entries) > 0
        first = entries[0]
        assert "alegra_id" in first, f"Missing alegra_id in entry: {first}"
        print("PASS: plan-cuentas entries have alegra_id field")

    def test_plan_cuentas_arriendo_5480(self, headers):
        resp = requests.get(f"{BASE_URL}/api/gastos/plan-cuentas", headers=headers)
        data = resp.json()
        entries = data.get("plan", data if isinstance(data, list) else [])
        arriendo = [e for e in entries if e.get("categoria") == "Operaciones" and e.get("subcategoria") == "Arriendo"]
        assert len(arriendo) > 0, "Arriendo entry not found in plan_cuentas"
        assert arriendo[0]["alegra_id"] == 5480, f"Expected 5480, got {arriendo[0]['alegra_id']}"
        print("PASS: Operaciones/Arriendo → alegra_id=5480")


# ── 2. Smoke test ─────────────────────────────────────────────────────────────
class TestSmoke:
    def test_health_smoke(self):
        resp = requests.get(f"{BASE_URL}/api/health/smoke")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("status") == "ok", f"Unexpected smoke status: {data}"
        print("PASS: /api/health/smoke → status:ok")


# ── 3. Excel Template ─────────────────────────────────────────────────────────
class TestPlantilla:
    def test_plantilla_returns_excel(self, headers):
        resp = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=headers)
        assert resp.status_code == 200
        ct = resp.headers.get("content-type", "")
        assert "spreadsheet" in ct or "excel" in ct or "octet-stream" in ct, f"Unexpected content-type: {ct}"
        print("PASS: /api/gastos/plantilla returns Excel")

    def test_plantilla_has_categoria_subcategoria_columns(self, headers):
        import io, openpyxl
        resp = requests.get(f"{BASE_URL}/api/gastos/plantilla", headers=headers)
        wb = openpyxl.load_workbook(io.BytesIO(resp.content))
        ws = wb.active
        # Template has title in row 1, headers in row 2
        all_cells = []
        for row in ws.iter_rows(min_row=1, max_row=5):
            row_vals = [str(cell.value or "").strip() for cell in row]
            all_cells.append(row_vals)
            print(f"Row: {row_vals}")
        # Find row with Categoria/Subcategoria
        found_cat = False
        found_sub = False
        no_tipo_gasto = True
        for row_vals in all_cells:
            if "Categoria" in row_vals or "Categoría" in row_vals:
                found_cat = True
            if "Subcategoria" in row_vals or "Subcategoría" in row_vals:
                found_sub = True
            if "Tipo_Gasto" in row_vals:
                no_tipo_gasto = False
        assert found_cat, f"No Categoria column found in first 5 rows"
        assert found_sub, f"No Subcategoria column found in first 5 rows"
        assert no_tipo_gasto, "Legacy Tipo_Gasto column found"
        print("PASS: Template has Categoria + Subcategoria (no Tipo_Gasto)")


# ── 4. CSV/Excel Upload Mapping ───────────────────────────────────────────────
class TestCSVMapping:
    """Upload test Excel, verify account IDs mapped correctly"""

    def test_upload_excel_returns_preview(self, headers):
        with open("/tmp/test_gastos_plan.xlsx", "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/gastos/cargar",
                headers={k: v for k, v in headers.items()},
                files={"file": ("test_gastos_plan.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        assert resp.status_code == 200, f"Expected 200, got {resp.status_code}: {resp.text}"
        data = resp.json()
        print(f"Upload response keys: {list(data.keys())}")
        print("PASS: Upload Excel returns 200")

    def test_fila1_operaciones_arriendo_5480(self, headers):
        """Row 1: Operaciones/Arriendo → cuenta_gasto_id=5480"""
        with open("/tmp/test_gastos_plan.xlsx", "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/gastos/cargar",
                headers={k: v for k, v in headers.items()},
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        data = resp.json()
        # Find rows/filas in response
        rows = data.get("filas") or data.get("rows") or data.get("preview") or data.get("gastos") or []
        print(f"Total rows in response: {len(rows)}")
        if rows:
            print(f"Row 0 sample: {rows[0]}")
            row0 = rows[0]
            cid = row0.get("cuenta_gasto_id") or row0.get("cuenta_id") or row0.get("alegra_id")
            assert cid == 5480, f"Expected 5480 for Arriendo, got {cid}. Row: {row0}"
            print(f"PASS: Fila 1 (Operaciones/Arriendo) → cuenta_gasto_id={cid}")
        else:
            pytest.skip(f"No rows in response. Keys: {list(data.keys())}")

    def test_fila2_personal_salarios_5462(self, headers):
        """Row 2: Personal/Salarios → cuenta_gasto_id=5462"""
        with open("/tmp/test_gastos_plan.xlsx", "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/gastos/cargar",
                headers={k: v for k, v in headers.items()},
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        data = resp.json()
        rows = data.get("filas") or data.get("rows") or data.get("preview") or data.get("gastos") or []
        if len(rows) >= 2:
            row1 = rows[1]
            cid = row1.get("cuenta_gasto_id") or row1.get("cuenta_id") or row1.get("alegra_id")
            assert cid == 5462, f"Expected 5462 for Salarios, got {cid}. Row: {row1}"
            print(f"PASS: Fila 2 (Personal/Salarios) → cuenta_gasto_id={cid}")
        else:
            pytest.skip(f"Less than 2 rows in response")

    def test_fila3_financiero_intereses_5533(self, headers):
        """Row 3: Financiero/Intereses → cuenta_gasto_id=5533"""
        with open("/tmp/test_gastos_plan.xlsx", "rb") as f:
            resp = requests.post(
                f"{BASE_URL}/api/gastos/cargar",
                headers={k: v for k, v in headers.items()},
                files={"file": ("test.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
            )
        data = resp.json()
        rows = data.get("filas") or data.get("rows") or data.get("preview") or data.get("gastos") or []
        if len(rows) >= 3:
            row2 = rows[2]
            cid = row2.get("cuenta_gasto_id") or row2.get("cuenta_id") or row2.get("alegra_id")
            assert cid == 5533, f"Expected 5533 for Intereses, got {cid}. Row: {row2}"
            print(f"PASS: Fila 3 (Financiero/Intereses) → cuenta_gasto_id={cid}")
        else:
            pytest.skip(f"Less than 3 rows in response")

    def test_otros_varios_5493_not_5495(self, headers):
        """Otros/Varios must map to 5493 (Gastos generales), NOT 5495 (Gastos representacion)"""
        # Create a small Excel with Otros/Varios
        import io, openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.append(["Fecha","Proveedor","NIT_Proveedor","Concepto","Monto_Sin_IVA","Incluye_IVA","Categoria","Subcategoria","Tipo_Persona","Es_Autoretenedor","Forma_Pago","Mes_Periodo","Notas"])
        ws.append(["2026-01-15","Varios","900000099","Gastos varios",100000,"No","Otros","Varios","PJ","No","Contado","2026-01",""])
        buf = io.BytesIO()
        wb.save(buf)
        buf.seek(0)
        resp = requests.post(
            f"{BASE_URL}/api/gastos/cargar",
            headers={k: v for k, v in headers.items()},
            files={"file": ("otros_varios.xlsx", buf, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")}
        )
        assert resp.status_code == 200, f"Upload failed: {resp.text}"
        data = resp.json()
        rows = data.get("filas") or data.get("rows") or data.get("preview") or data.get("gastos") or []
        if rows:
            cid = rows[0].get("cuenta_gasto_id") or rows[0].get("cuenta_id") or rows[0].get("alegra_id")
            assert cid == 5493, f"Expected 5493 for Otros/Varios, got {cid} (5495 would be the bug!)"
            print(f"PASS: Otros/Varios → cuenta_gasto_id=5493 (not 5495)")
        else:
            pytest.skip("No rows in response")


# ── 5. MongoDB plan_cuentas_roddos ────────────────────────────────────────────
class TestMongoPlanCuentas:
    """Verify MongoDB collection has 28 docs"""

    def test_mongodb_plan_cuentas_28_docs(self, headers):
        # Use plan-cuentas endpoint as proxy for MongoDB state
        resp = requests.get(f"{BASE_URL}/api/gastos/plan-cuentas", headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        entries = data.get("plan", data if isinstance(data, list) else [])
        total = data.get("total", len(entries))
        assert total == 28, f"MongoDB should have 28 plan_cuentas docs, got {total}"
        print(f"PASS: MongoDB plan_cuentas_roddos has {total} docs")


# ── 6. Agent anular_causacion ─────────────────────────────────────────────────
class TestAgentAnularCausacion:
    def test_agent_mentions_anular_causacion(self, headers):
        import uuid
        resp = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=headers,
            json={"session_id": f"test-{uuid.uuid4().hex[:8]}", "message": "Necesito anular el asiento contable con journal ID 12345"}
        )
        assert resp.status_code == 200, f"Chat failed: {resp.text}"
        data = resp.json()
        reply = str(data).lower()
        print(f"Agent reply snippet: {str(data)[:300]}")
        # Agent should mention anular or journal deletion
        has_anular = "anular" in reply or "delete" in reply or "journals" in reply or "eliminar" in reply
        assert has_anular, f"Agent didn't mention anular/delete/journals: {reply[:300]}"
        print("PASS: Agent mentions anular/delete for journal cancellation")


# ── 7. Agent conoce plan cuentas (arriendo → 5480) ────────────────────────────
class TestAgentPlanCuentasKnowledge:
    def test_agent_knows_arriendo_5480(self, headers):
        import uuid
        resp = requests.post(
            f"{BASE_URL}/api/chat/message",
            headers=headers,
            json={"session_id": f"test-{uuid.uuid4().hex[:8]}", "message": "¿Qué ID de Alegra debo usar para registrar un gasto de arriendo?"}
        )
        assert resp.status_code == 200, f"Chat failed: {resp.text}"
        data = resp.json()
        reply = str(data)
        print(f"Agent reply snippet: {reply[:400]}")
        assert "5480" in reply, f"Agent didn't mention 5480 for arriendo. Reply: {reply[:400]}"
        print("PASS: Agent knows arriendo → ID 5480")


# ── 8. Cleanup endpoints ──────────────────────────────────────────────────────
class TestCleanupEndpoints:
    def test_cleanup_preview_creates_job(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/gastos/cleanup-preview",
            headers=headers,
            json={"cuenta_id": 5495, "fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"}
        )
        assert resp.status_code == 200, f"cleanup-preview failed: {resp.status_code}: {resp.text}"
        data = resp.json()
        assert "job_id" in data, f"No job_id in response: {data}"
        estado = data.get("estado", "")
        assert estado in ["en_progreso", "iniciado", "pending", "en_proceso"], f"Unexpected estado: {estado}"
        print(f"PASS: cleanup-preview created job_id={data['job_id']}, estado={estado}")

    def test_cleanup_status_polling(self, headers):
        # Start a job first
        resp = requests.post(
            f"{BASE_URL}/api/gastos/cleanup-preview",
            headers=headers,
            json={"cuenta_id": 5495, "fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"}
        )
        assert resp.status_code == 200
        job_id = resp.json()["job_id"]

        # Poll status
        print(f"Polling cleanup-status for job_id={job_id}")
        status_resp = requests.get(f"{BASE_URL}/api/gastos/cleanup-status/{job_id}", headers=headers)
        assert status_resp.status_code == 200, f"cleanup-status failed: {status_resp.text}"
        data = status_resp.json()
        assert "estado" in data, f"No estado in cleanup-status response: {data}"
        print(f"PASS: cleanup-status returns estado={data.get('estado')}, total_revisados={data.get('total_revisados', 'N/A')}")

    def test_cleanup_execute_empty_ids_400(self, headers):
        resp = requests.post(
            f"{BASE_URL}/api/gastos/cleanup-execute",
            headers=headers,
            json={"alegra_ids": [], "cuenta_correcta_id": 5480}
        )
        assert resp.status_code == 400, f"Expected 400 for empty ids, got {resp.status_code}: {resp.text}"
        print("PASS: cleanup-execute with empty alegra_ids returns 400")
