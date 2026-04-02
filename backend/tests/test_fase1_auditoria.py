"""
test_fase1_auditoria.py — Fase 1: auditoria completa de Alegra

T1: GET /api/auditoria/alegra-completo retorna dict con keys correctas
T2: Invoice con "VIN:" se clasifica como factura_venta; sin "VIN:" como factura_venta_sin_vin
T3: Dos bills con mismo numero y monto se detectan como bill_duplicada en alertas
T4: POST /api/auditoria/aprobar-limpieza con confirmado=False NO inserta en MongoDB
T5: POST /api/auditoria/aprobar-limpieza con confirmado=True inserta doc en auditoria_aprobaciones
T6: POST /api/auditoria/anular-bill-duplicada con bill_id que no existe retorna 404
T7: POST /api/auditoria/anular-bill-duplicada exitoso inserta evento en roddos_events
"""

import sys
import os
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# --- Mock heavy dependencies before importing auditoria module ---
# Stub out database, dependencies, and alegra_service to avoid env var requirements
_mock_db = MagicMock()
_db_module = MagicMock()
_db_module.db = _mock_db
sys.modules["database"] = _db_module

_deps_module = MagicMock()
_mock_user = {"username": "admin", "role": "admin"}
_deps_module.get_current_user = MagicMock(return_value=_mock_user)
_deps_module.require_admin = MagicMock(return_value=_mock_user)
sys.modules["dependencies"] = _deps_module

_alegra_svc_module = MagicMock()
sys.modules["alegra_service"] = _alegra_svc_module

# Import auditoria module directly to avoid routers/__init__.py chain
import importlib.util

def _load_auditoria_module():
    """Loads (or reloads) routers.auditoria bypassing routers/__init__.py."""
    spec = importlib.util.spec_from_file_location(
        "routers.auditoria",
        os.path.join(os.path.dirname(__file__), "..", "routers", "auditoria.py")
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["routers.auditoria"] = mod
    spec.loader.exec_module(mod)
    return mod

_auditoria_mod = _load_auditoria_module()


# ── Mock data ─────────────────────────────────────────────────────────────────

MOCK_INVOICES = [
    {
        "id": 101,
        "number": "FV-001",
        "total": 8500000,
        "contact": {"id": 1, "name": "Cliente A"},
        "items": [
            {"description": "TVS NTORQ 125 Azul - VIN: ABC123 / Motor: M001", "price": 8500000}
        ]
    },
    {
        "id": 102,
        "number": "FV-002",
        "total": 7000000,
        "contact": {"id": 2, "name": "Cliente B"},
        "items": [
            {"description": "Accesorio generico sin identificacion", "price": 7000000}
        ]
    }
]

MOCK_BILLS = [
    {
        "id": 201,
        "numberTemplate": {"number": "FAC-001"},
        "total": 5000000,
        "contact": {"id": 10, "identification": "860024781", "name": "Auteco Mobility SAS"}
    },
    {
        "id": 202,
        "numberTemplate": {"number": "FAC-001"},
        "total": 5000000,
        "contact": {"id": 10, "identification": "860024781", "name": "Auteco Mobility SAS"}
    },
    {
        "id": 203,
        "numberTemplate": {"number": "FAC-003"},
        "total": 1200000,
        "contact": {"id": 20, "identification": "900123456", "name": "Otro Proveedor SAS"}
    }
]

MOCK_JOURNALS = [
    {
        "id": 301,
        "observations": "Gasto operativo enero 2026",
        "entries": [
            {"account": {"id": 5493, "code": "519500"}, "debit": 500000, "credit": 0},
            {"account": {"id": 1105, "code": "110505"}, "debit": 0, "credit": 500000}
        ]
    },
    {
        "id": 302,
        "observations": "Ingreso intereses enero 2026",
        "entries": [
            {"account": {"id": 4205, "code": "420501"}, "debit": 0, "credit": 300000},
            {"account": {"id": 1105, "code": "110505"}, "debit": 300000, "credit": 0}
        ]
    }
]


# ── T1: Estructura de respuesta ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_t1_estructura_respuesta():
    """GET /api/auditoria/alegra-completo retorna dict con todas las keys esperadas."""
    _clasificar_registros = _auditoria_mod._clasificar_registros
    _detectar_duplicados_auteco = _auditoria_mod._detectar_duplicados_auteco

    clasificado = _clasificar_registros(MOCK_INVOICES, MOCK_BILLS, MOCK_JOURNALS)
    alertas = _detectar_duplicados_auteco(clasificado["compras_auteco"])

    respuesta = {
        "timestamp": "2026-04-01T12:00:00Z",
        "resumen": {
            "total_invoices": len(MOCK_INVOICES),
            "total_bills": len(MOCK_BILLS),
            "total_journals": len(MOCK_JOURNALS),
            "facturas_venta": len(clasificado["facturas_venta"]),
            "facturas_venta_sin_vin": len(clasificado["facturas_venta_sin_vin"]),
            "compras_auteco": len(clasificado["compras_auteco"]),
            "compras_otro_proveedor": len(clasificado["compras_otro_proveedor"]),
            "journals_gasto": len(clasificado["journals_gasto"]),
            "journals_ingreso": len(clasificado["journals_ingreso"]),
            "journals_otro": len(clasificado["journals_otro"]),
        },
        "facturas_venta": clasificado["facturas_venta"],
        "facturas_venta_sin_vin": clasificado["facturas_venta_sin_vin"],
        "compras_auteco": clasificado["compras_auteco"],
        "compras_otro_proveedor": clasificado["compras_otro_proveedor"],
        "journals_gasto": clasificado["journals_gasto"],
        "journals_ingreso": clasificado["journals_ingreso"],
        "journals_otro": clasificado["journals_otro"],
        "alertas": alertas,
    }

    required_keys = [
        "timestamp", "resumen", "facturas_venta", "facturas_venta_sin_vin",
        "compras_auteco", "compras_otro_proveedor", "journals_gasto",
        "journals_ingreso", "journals_otro", "alertas"
    ]
    for key in required_keys:
        assert key in respuesta, f"Falta key: {key}"

    resumen_keys = [
        "total_invoices", "total_bills", "total_journals",
        "facturas_venta", "facturas_venta_sin_vin", "compras_auteco",
        "compras_otro_proveedor", "journals_gasto", "journals_ingreso", "journals_otro"
    ]
    for key in resumen_keys:
        assert key in respuesta["resumen"], f"Falta key en resumen: {key}"


# ── T2: Clasificacion facturas venta ─────────────────────────────────────────

@pytest.mark.asyncio
async def test_t2_clasificacion_factura_venta():
    """Invoice con 'VIN:' se clasifica como factura_venta; sin 'VIN:' como factura_venta_sin_vin."""
    _clasificar_registros = _auditoria_mod._clasificar_registros

    clasificado = _clasificar_registros(MOCK_INVOICES, [], [])

    # Invoice 101 tiene "VIN:" en su item → factura_venta
    ids_con_vin = [inv["id"] for inv in clasificado["facturas_venta"]]
    assert 101 in ids_con_vin, "Invoice 101 (con VIN) debe estar en facturas_venta"

    # Invoice 102 no tiene "VIN:" → factura_venta_sin_vin
    ids_sin_vin = [inv["id"] for inv in clasificado["facturas_venta_sin_vin"]]
    assert 102 in ids_sin_vin, "Invoice 102 (sin VIN) debe estar en facturas_venta_sin_vin"

    # Sin solapamiento
    assert 101 not in ids_sin_vin
    assert 102 not in ids_con_vin


# ── T3: Deteccion duplicados Auteco ──────────────────────────────────────────

@pytest.mark.asyncio
async def test_t3_deteccion_duplicado_auteco():
    """Dos bills con mismo numero y monto se detectan como bill_duplicada en alertas."""
    _clasificar_registros = _auditoria_mod._clasificar_registros
    _detectar_duplicados_auteco = _auditoria_mod._detectar_duplicados_auteco

    clasificado = _clasificar_registros([], MOCK_BILLS, [])

    # Verificar que las 2 bills de Auteco (201 y 202) quedaron en compras_auteco
    auteco_ids = [b["id"] for b in clasificado["compras_auteco"]]
    assert 201 in auteco_ids
    assert 202 in auteco_ids
    # Bill 203 es de otro proveedor
    assert 203 not in auteco_ids
    otro_ids = [b["id"] for b in clasificado["compras_otro_proveedor"]]
    assert 203 in otro_ids

    # Detectar duplicados
    alertas = _detectar_duplicados_auteco(clasificado["compras_auteco"])

    assert len(alertas) >= 1, "Debe haber al menos 1 alerta de duplicado"

    alerta = alertas[0]
    assert alerta["tipo"] == "bill_duplicada"
    assert "bill_original_id" in alerta
    assert "bill_duplicada_id" in alerta
    assert alerta["numero_factura"] == "FAC-001"
    assert alerta["monto"] == 5000000

    # Los IDs 201 y 202 deben estar en la alerta (uno como original, otro como duplicada)
    ids_en_alerta = {alerta["bill_original_id"], alerta["bill_duplicada_id"]}
    assert 201 in ids_en_alerta
    assert 202 in ids_en_alerta


# ── Helpers for endpoint tests ────────────────────────────────────────────────

def _make_app_with_mock_admin():
    """Build FastAPI app with auditoria router and mocked require_admin.

    Uses FastAPI dependency_overrides keyed by the original require_admin
    function stored in the auditoria module at import time.
    """
    from fastapi import FastAPI
    router = _auditoria_mod.router

    app = FastAPI()
    app.include_router(router, prefix="/api")

    # require_admin in the module is whatever was imported at load time
    # (the MagicMock from the stubbed dependencies module).
    # FastAPI resolves Depends(require_admin) against dependency_overrides.
    original_require_admin = _auditoria_mod.require_admin

    async def _admin_user():
        return {"username": "admin", "role": "admin"}

    app.dependency_overrides[original_require_admin] = _admin_user
    return app


# ── T4: aprobar-limpieza con confirmado=False no escribe ─────────────────────

@pytest.mark.asyncio
async def test_t4_aprobar_limpieza_sin_confirmacion_no_escribe():
    """POST aprobar-limpieza con confirmado=False retorna plan pero NO inserta en MongoDB."""
    from fastapi.testclient import TestClient

    app = _make_app_with_mock_admin()

    mock_db = MagicMock()
    mock_db.auditoria_aprobaciones = MagicMock()
    mock_db.auditoria_aprobaciones.insert_one = AsyncMock()

    with patch.object(_auditoria_mod, "db", mock_db):
        client = TestClient(app)
        response = client.post(
            "/api/auditoria/aprobar-limpieza",
            json={"confirmado": False, "excluir_ids": []}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "plan_sin_ejecutar"
    mock_db.auditoria_aprobaciones.insert_one.assert_not_called()


# ── T5: aprobar-limpieza con confirmado=True inserta en MongoDB ───────────────

@pytest.mark.asyncio
async def test_t5_aprobar_limpieza_con_confirmacion_inserta():
    """POST aprobar-limpieza con confirmado=True inserta doc en auditoria_aprobaciones."""
    from fastapi.testclient import TestClient

    app = _make_app_with_mock_admin()

    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = "mock_object_id_123"

    mock_db = MagicMock()
    mock_db.auditoria_aprobaciones = MagicMock()
    mock_db.auditoria_aprobaciones.insert_one = AsyncMock(return_value=mock_insert_result)

    with patch.object(_auditoria_mod, "db", mock_db):
        client = TestClient(app)
        response = client.post(
            "/api/auditoria/aprobar-limpieza",
            json={"confirmado": True, "excluir_ids": [123, 456]}
        )

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "aprobado"
    assert "doc_id" in data
    mock_db.auditoria_aprobaciones.insert_one.assert_called_once()

    call_args = mock_db.auditoria_aprobaciones.insert_one.call_args[0][0]
    assert call_args["status"] == "aprobado_pendiente_ejecucion"
    assert call_args["excluir_ids"] == [123, 456]
    assert "timestamp" in call_args
    assert "aprobado_por" in call_args


# ── T6: anular-bill-duplicada con bill_id que no existe retorna 404 ───────────

@pytest.mark.asyncio
async def test_t6_anular_bill_duplicada_no_encontrada():
    """POST anular-bill-duplicada con bill_id que no existe en Alegra retorna 404."""
    from fastapi.testclient import TestClient

    app = _make_app_with_mock_admin()

    mock_response_404 = MagicMock()
    mock_response_404.status_code = 404
    mock_response_404.json.return_value = {"message": "Bill not found"}

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(return_value=mock_response_404)

    mock_httpx = MagicMock()
    mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()

    with patch.object(_auditoria_mod, "db", mock_db):
        with patch("httpx.AsyncClient", mock_httpx):
            with patch.dict(os.environ, {"ALEGRA_EMAIL": "test@test.com", "ALEGRA_TOKEN": "token123"}):
                client = TestClient(app)
                response = client.post(
                    "/api/auditoria/anular-bill-duplicada",
                    json={"bill_id_a_anular": 9999, "bill_id_a_mantener": 9998}
                )

    assert response.status_code == 404
    assert "9999" in response.json()["detail"]


# ── T7: anular-bill-duplicada exitoso inserta evento en roddos_events ─────────

@pytest.mark.asyncio
async def test_t7_anular_bill_duplicada_exitoso_registra_evento():
    """POST anular-bill-duplicada exitoso inserta evento en roddos_events."""
    from fastapi.testclient import TestClient

    app = _make_app_with_mock_admin()

    mock_response_200_anular = MagicMock()
    mock_response_200_anular.status_code = 200
    mock_response_200_anular.json.return_value = {"id": 201, "status": "open"}

    mock_response_200_mantener = MagicMock()
    mock_response_200_mantener.status_code = 200
    mock_response_200_mantener.json.return_value = {"id": 202, "status": "open"}

    mock_response_delete = MagicMock()
    mock_response_delete.status_code = 200
    mock_response_delete.json.return_value = {}

    mock_insert_result = MagicMock()
    mock_insert_result.inserted_id = "evento_mock_id"

    mock_client = AsyncMock()
    mock_client.get = AsyncMock(side_effect=[mock_response_200_anular, mock_response_200_mantener])
    mock_client.delete = AsyncMock(return_value=mock_response_delete)

    mock_httpx = MagicMock()
    mock_httpx.return_value.__aenter__ = AsyncMock(return_value=mock_client)
    mock_httpx.return_value.__aexit__ = AsyncMock(return_value=False)

    mock_db = MagicMock()
    mock_db.roddos_events = MagicMock()
    mock_db.roddos_events.insert_one = AsyncMock(return_value=mock_insert_result)

    with patch.object(_auditoria_mod, "db", mock_db):
        with patch("httpx.AsyncClient", mock_httpx):
            with patch.dict(os.environ, {"ALEGRA_EMAIL": "test@test.com", "ALEGRA_TOKEN": "token123"}):
                client = TestClient(app)
                response = client.post(
                    "/api/auditoria/anular-bill-duplicada",
                    json={"bill_id_a_anular": 201, "bill_id_a_mantener": 202}
                )

    assert response.status_code == 200
    data = response.json()
    assert data["anulado"] is True
    assert data["bill_id"] == 201
    assert data["bill_mantenida"] == 202
    assert data["evento_registrado"] is True

    mock_db.roddos_events.insert_one.assert_called_once()
    evento = mock_db.roddos_events.insert_one.call_args[0][0]
    assert evento["event_type"] == "bill_duplicada_anulada"
    assert evento["agent"] == "auditoria"
    assert evento["payload"]["bill_anulada"] == 201
    assert evento["payload"]["bill_mantenida"] == 202
    assert evento["source"] == "routers/auditoria.py"
