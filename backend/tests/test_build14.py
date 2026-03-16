"""Build 14 backend tests: ReteICA, hard delete proveedores, Mercately settings/gestiones/webhook"""
import pytest
import requests
import os

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")

AUTH_PAYLOAD = {"email": "contabilidad@roddos.com", "password": "Admin@RODDOS2025!"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json=AUTH_PAYLOAD)
    assert r.status_code == 200, f"Auth failed: {r.text}"
    return r.json().get("access_token") or r.json().get("token")


@pytest.fixture(scope="module")
def auth(token):
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {token}", "Content-Type": "application/json"})
    return s


# ── TAREA 0: ReteICA ──────────────────────────────────────────────────────────

class TestReteICA:
    def test_iva_status_200(self, auth):
        r = auth.get(f"{BASE_URL}/api/impuestos/iva-status")
        assert r.status_code == 200, r.text

    def test_retica_tarifa_pct_is_0414(self, auth):
        r = auth.get(f"{BASE_URL}/api/impuestos/iva-status")
        data = r.json()
        retica = data.get("retica", {})
        assert "tarifa_pct" in retica, f"tarifa_pct missing in retica: {retica}"
        assert retica["tarifa_pct"] == 0.414, f"Expected 0.414, got {retica['tarifa_pct']}"

    def test_retica_no_tarifa_anual_pct(self, auth):
        r = auth.get(f"{BASE_URL}/api/impuestos/iva-status")
        data = r.json()
        retica = data.get("retica", {})
        assert "tarifa_anual_pct" not in retica, "tarifa_anual_pct should NOT be present in retica"

    def test_retica_nota_contains_por_operacion(self, auth):
        r = auth.get(f"{BASE_URL}/api/impuestos/iva-status")
        nota = r.json().get("retica", {}).get("nota", "")
        assert "por operación gravada" in nota or "por operacion gravada" in nota.lower(), f"Note: {nota}"


# ── TAREA 1: Hard delete proveedores ─────────────────────────────────────────

class TestHardDeleteProveedor:
    TEST_NAME = "TEST_PROVEEDOR_BUILD14_DELETE"

    def test_create_test_proveedor(self, auth):
        r = auth.post(f"{BASE_URL}/api/proveedores/config", json={
            "nombre": self.TEST_NAME, "nit": "9000000099",
            "es_autoretenedor": False, "tipo_retencion": "compras_2.5"
        })
        assert r.status_code == 200

    def test_proveedor_exists_before_delete(self, auth):
        r = auth.get(f"{BASE_URL}/api/proveedores/config")
        names = [p["nombre"] for p in r.json().get("proveedores", [])]
        assert self.TEST_NAME in names, f"{self.TEST_NAME} not found in {names}"

    def test_hard_delete_returns_ok(self, auth):
        r = auth.delete(f"{BASE_URL}/api/proveedores/config/{self.TEST_NAME}")
        assert r.status_code == 200
        assert r.json().get("ok") is True
        assert r.json().get("deleted") is True

    def test_proveedor_gone_after_delete(self, auth):
        r = auth.get(f"{BASE_URL}/api/proveedores/config")
        names = [p["nombre"] for p in r.json().get("proveedores", [])]
        assert self.TEST_NAME not in names, f"{self.TEST_NAME} still present after delete"

    def test_deleted_proveedor_not_marked_eliminado(self, auth):
        """Hard delete: document must not exist with notas=ELIMINADO"""
        r = auth.get(f"{BASE_URL}/api/proveedores/config/{self.TEST_NAME}")
        data = r.json()
        # Either not found, or found=False
        assert not data.get("found", False), "Proveedor should be completely gone (hard delete)"


# ── BUILD 14: Mercately settings ──────────────────────────────────────────────

class TestMercatelySettings:
    def test_get_mercately_returns_200(self, auth):
        r = auth.get(f"{BASE_URL}/api/settings/mercately")
        assert r.status_code == 200, r.text

    def test_get_mercately_has_required_fields(self, auth):
        r = auth.get(f"{BASE_URL}/api/settings/mercately")
        d = r.json()
        for field in ["global_activo", "horario_inicio", "horario_fin", "templates_activos", "datos_bancarios"]:
            assert field in d, f"Missing field: {field}"

    def test_get_mercately_templates_has_t1_to_t5(self, auth):
        r = auth.get(f"{BASE_URL}/api/settings/mercately")
        templates = r.json().get("templates_activos", {})
        for t in ["T1", "T2", "T3", "T4", "T5"]:
            assert t in templates, f"Missing template key: {t}"

    def test_post_mercately_saves_global_activo_false(self, auth):
        # GET current config first
        cur = auth.get(f"{BASE_URL}/api/settings/mercately").json()
        payload = {
            "api_key": "__keep__",
            "phone_number": cur.get("phone_number", ""),
            "whitelist": cur.get("whitelist", []),
            "ceo_number": cur.get("ceo_number", ""),
            "destinatarios_resumen": cur.get("destinatarios_resumen", []),
            "global_activo": False,
            "horario_inicio": cur.get("horario_inicio", "08:00"),
            "horario_fin": cur.get("horario_fin", "19:00"),
            "templates_activos": cur.get("templates_activos", {}),
            "datos_bancarios": cur.get("datos_bancarios", ""),
        }
        r = auth.post(f"{BASE_URL}/api/settings/mercately", json=payload)
        assert r.status_code == 200, r.text

    def test_get_mercately_reflects_global_activo_false(self, auth):
        r = auth.get(f"{BASE_URL}/api/settings/mercately")
        assert r.json().get("global_activo") is False

    def test_restore_global_activo_true(self, auth):
        cur = auth.get(f"{BASE_URL}/api/settings/mercately").json()
        payload = {
            "api_key": "__keep__",
            "phone_number": cur.get("phone_number", ""),
            "whitelist": cur.get("whitelist", []),
            "ceo_number": cur.get("ceo_number", ""),
            "destinatarios_resumen": cur.get("destinatarios_resumen", []),
            "global_activo": True,
            "horario_inicio": cur.get("horario_inicio", "08:00"),
            "horario_fin": cur.get("horario_fin", "19:00"),
            "templates_activos": cur.get("templates_activos", {}),
            "datos_bancarios": cur.get("datos_bancarios", ""),
        }
        r = auth.post(f"{BASE_URL}/api/settings/mercately", json=payload)
        assert r.status_code == 200


# ── BUILD 14: Mercately gestiones ─────────────────────────────────────────────

class TestMercatelyGestiones:
    def test_get_gestiones_200(self, auth):
        r = auth.get(f"{BASE_URL}/api/mercately/gestiones")
        assert r.status_code == 200, r.text

    def test_get_gestiones_structure(self, auth):
        r = auth.get(f"{BASE_URL}/api/mercately/gestiones")
        d = r.json()
        assert "gestiones" in d
        assert "total" in d
        assert isinstance(d["gestiones"], list)
        assert isinstance(d["total"], int)


# ── BUILD 14: Mercately webhook ───────────────────────────────────────────────

class TestMercatelyWebhook:
    def test_webhook_returns_ok_true(self, auth):
        payload = {
            "contact": {"phone": "573001234567", "name": "Test User"},
            "message": {"text": "Hola", "type": "text"},
        }
        r = requests.post(f"{BASE_URL}/api/mercately/webhook", json=payload)
        assert r.status_code == 200, r.text
        assert r.json().get("ok") is True
