"""
260401-fq4 — Admin Seed Endpoint: Test Suite (T1-T3)

Tests for:
  - POST /api/admin/run-seed knowledge_base -> documentos_cargados == len(SISMO_KNOWLEDGE)
  - GET  /api/admin/seed-status -> returns sismo_knowledge and plan_cuentas_roddos counts
  - POST /api/admin/run-seed invalid_name -> HTTP 400
"""
# ── ISOLATION: stub unavailable modules before any router import chain ──
import sys
import os
from unittest.mock import MagicMock

_STUBS = [
    "qrcode", "qrcode.image", "qrcode.image.svg",
    "cryptography", "cryptography.fernet",
    "pdfplumber",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

# Ensure env vars exist so database.py / other modules don't crash on import
os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/sismo_test")
os.environ.setdefault("DB_NAME", "sismo_test")
os.environ.setdefault("ALEGRA_EMAIL", "test@test.com")
os.environ.setdefault("ALEGRA_TOKEN", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

# ── sys.path para importar init_mongodb_sismo.py desde la raiz del proyecto ──
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

BACKEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

from init_mongodb_sismo import SISMO_KNOWLEDGE, PLAN_CUENTAS_RODDOS

import pytest
from unittest.mock import AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB async db with seed collections."""
    db = MagicMock()

    # sismo_knowledge collection
    db.sismo_knowledge = MagicMock()
    db.sismo_knowledge.update_one = AsyncMock(return_value=MagicMock(upserted_id="x"))
    db.sismo_knowledge.count_documents = AsyncMock(return_value=len(SISMO_KNOWLEDGE))

    # plan_cuentas_roddos collection
    db.plan_cuentas_roddos = MagicMock()
    db.plan_cuentas_roddos.update_one = AsyncMock(return_value=MagicMock(upserted_id="x"))
    db.plan_cuentas_roddos.count_documents = AsyncMock(return_value=len(PLAN_CUENTAS_RODDOS))

    return db


@pytest.fixture
def mock_admin_user():
    """Mock admin user returned by require_admin."""
    return {
        "id": "admin_001",
        "email": "admin@roddos.com",
        "nombre": "Admin RODDOS",
        "rol": "admin",
    }


@pytest.fixture
def test_client(mock_db, mock_admin_user):
    """FastAPI TestClient with mocked db and require_admin via dependency_overrides."""
    import dependencies
    from routers.admin_seeds import router

    app = FastAPI()
    app.include_router(router, prefix="/api")

    # Override require_admin dependency so tests don't need real JWT
    async def _mock_require_admin():
        return mock_admin_user

    app.dependency_overrides[dependencies.require_admin] = _mock_require_admin

    with patch("routers.admin_seeds.db", mock_db):
        client = TestClient(app)
        yield client, mock_db

    app.dependency_overrides.clear()


# ══════════════════════════════════════════════════════════════════════════════
# T1: POST /api/admin/run-seed knowledge_base → documentos_cargados == len(SISMO_KNOWLEDGE)
# ══════════════════════════════════════════════════════════════════════════════

def test_run_seed_knowledge_base(test_client):
    """
    T1: POST /api/admin/run-seed con seed_name='knowledge_base' debe:
    - Llamar update_one len(SISMO_KNOWLEDGE) veces en sismo_knowledge
    - Retornar documentos_cargados == len(SISMO_KNOWLEDGE) y status 'ok'
    """
    client, mock_db = test_client

    response = client.post(
        "/api/admin/run-seed",
        json={"seed_name": "knowledge_base"},
    )

    assert response.status_code == 200, (
        f"Esperado 200, recibido {response.status_code}: {response.text}"
    )

    data = response.json()
    assert data["status"] == "ok", f"status debe ser 'ok', recibido: {data['status']}"
    assert data["documentos_cargados"] == len(SISMO_KNOWLEDGE), (
        f"documentos_cargados debe ser {len(SISMO_KNOWLEDGE)}, recibido: {data['documentos_cargados']}"
    )
    assert data["seed_name"] == "knowledge_base"

    # Verificar que update_one fue llamado para cada doc de SISMO_KNOWLEDGE
    assert mock_db.sismo_knowledge.update_one.call_count == len(SISMO_KNOWLEDGE), (
        f"update_one debio llamarse {len(SISMO_KNOWLEDGE)} veces, "
        f"se llamo {mock_db.sismo_knowledge.update_one.call_count} veces"
    )

    print(f"T1 PASO: knowledge_base seed cargó {data['documentos_cargados']} documentos")


# ══════════════════════════════════════════════════════════════════════════════
# T2: GET /api/admin/seed-status → retorna conteos de ambas colecciones
# ══════════════════════════════════════════════════════════════════════════════

def test_seed_status(test_client):
    """
    T2: GET /api/admin/seed-status debe retornar dict con sismo_knowledge y plan_cuentas_roddos
    como enteros.
    """
    client, mock_db = test_client

    response = client.get("/api/admin/seed-status")

    assert response.status_code == 200, (
        f"Esperado 200, recibido {response.status_code}: {response.text}"
    )

    data = response.json()

    assert "sismo_knowledge" in data, f"Falta key 'sismo_knowledge' en respuesta: {data}"
    assert "plan_cuentas_roddos" in data, f"Falta key 'plan_cuentas_roddos' en respuesta: {data}"

    assert isinstance(data["sismo_knowledge"], int), (
        f"sismo_knowledge debe ser int, recibido: {type(data['sismo_knowledge'])}"
    )
    assert isinstance(data["plan_cuentas_roddos"], int), (
        f"plan_cuentas_roddos debe ser int, recibido: {type(data['plan_cuentas_roddos'])}"
    )

    assert data["sismo_knowledge"] == len(SISMO_KNOWLEDGE)
    assert data["plan_cuentas_roddos"] == len(PLAN_CUENTAS_RODDOS)

    print(f"T2 PASO: seed-status retornó sismo_knowledge={data['sismo_knowledge']}, plan_cuentas_roddos={data['plan_cuentas_roddos']}")


# ══════════════════════════════════════════════════════════════════════════════
# T3: POST /api/admin/run-seed invalid_name → HTTP 400
# ══════════════════════════════════════════════════════════════════════════════

def test_run_seed_invalid_name(test_client):
    """
    T3: POST /api/admin/run-seed con seed_name inválido debe retornar HTTP 400.
    """
    client, _ = test_client

    response = client.post(
        "/api/admin/run-seed",
        json={"seed_name": "nonexistent"},
    )

    assert response.status_code == 400, (
        f"seed_name invalido debe retornar 400, recibido: {response.status_code}"
    )

    data = response.json()
    assert "detail" in data, f"Respuesta 400 debe tener 'detail': {data}"
    assert "nonexistent" in data["detail"] or "invalido" in data["detail"].lower(), (
        f"El mensaje de error debe mencionar el seed_name invalido: {data['detail']}"
    )

    print(f"T3 PASO: seed_name invalido rechazado con 400: {data['detail']}")
