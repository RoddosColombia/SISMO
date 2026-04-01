"""
260401-esw — Global66 Webhook Router: Test Suite (T1-T7)

Tests for:
  - HMAC-SHA256 signature validation
  - MD5 anti-duplication guard
  - High-confidence (>=0.70) routing to Alegra journals
  - Low-confidence (<0.70) routing to conciliacion_partidas
  - GET /sync daily counts

CRITICAL: NEVER /journal-entries (ERROR-008), NEVER ID 5495 (ERROR-009)
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
os.environ.setdefault("GLOBAL66_WEBHOOK_SECRET", "test-global66-secret")

import pytest
import hmac
import hashlib
import json
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from fastapi import FastAPI


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB connection."""
    db = MagicMock()
    db.global66_transacciones_procesadas = AsyncMock()
    db.global66_transacciones_procesadas.find_one = AsyncMock(return_value=None)
    db.global66_transacciones_procesadas.insert_one = AsyncMock()
    db.conciliacion_partidas = AsyncMock()
    db.conciliacion_partidas.insert_one = AsyncMock()
    db.roddos_events = AsyncMock()
    db.roddos_events.insert_one = AsyncMock()

    # Mock count_documents for sync endpoint
    db.global66_transacciones_procesadas.count_documents = AsyncMock(return_value=0)

    return db


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "id": "test_user_123",
        "email": "test@roddos.com",
        "nombre": "Test User"
    }


@pytest.fixture
def webhook_secret():
    return "test-global66-secret"


def _make_signature(body: bytes, secret: str) -> str:
    """Helper: generate valid HMAC-SHA256 signature."""
    return hmac.new(
        secret.encode("utf-8"),
        body,
        hashlib.sha256
    ).hexdigest()


@pytest.fixture
def valid_payload():
    return {
        "transaction_id": "GLB-TX-001",
        "tipo": "credit",
        "monto": 500000.0,
        "descripcion": "transferencia pago cuota cliente",
        "fecha": "2026-04-01",
        "confianza": 0.85,
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Rechaza firma inválida → 401
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_rejects_invalid_signature(mock_db, valid_payload):
    """
    T1: POST /global66/webhook con firma incorrecta debe retornar 401.
    """
    from routers.global66 import procesar_webhook_global66

    body_bytes = json.dumps(valid_payload).encode("utf-8")
    bad_signature = "sha256=invalidsignature"

    from fastapi import Request
    from starlette.datastructures import Headers

    # Build mock request
    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.headers = {"X-Global66-Signature": bad_signature}

    from fastapi import HTTPException
    with patch("routers.global66.db", mock_db):
        with patch.dict(os.environ, {"GLOBAL66_WEBHOOK_SECRET": "test-global66-secret"}):
            with pytest.raises(HTTPException) as exc_info:
                await procesar_webhook_global66(mock_request)

    assert exc_info.value.status_code == 401, (
        f"Firma invalida debe retornar 401, recibido {exc_info.value.status_code}"
    )
    print("T1 PASÓ: Firma invalida rechazada con 401")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Rechaza ausencia de firma → 401
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_rejects_missing_signature(mock_db, valid_payload):
    """
    T2: POST /global66/webhook sin header X-Global66-Signature debe retornar 401.
    """
    from routers.global66 import procesar_webhook_global66

    body_bytes = json.dumps(valid_payload).encode("utf-8")

    from fastapi import Request, HTTPException

    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.headers = {}  # No signature header

    with patch("routers.global66.db", mock_db):
        with patch.dict(os.environ, {"GLOBAL66_WEBHOOK_SECRET": "test-global66-secret"}):
            with pytest.raises(HTTPException) as exc_info:
                await procesar_webhook_global66(mock_request)

    assert exc_info.value.status_code == 401, (
        f"Firma ausente debe retornar 401, recibido {exc_info.value.status_code}"
    )
    print("T2 PASÓ: Firma ausente rechazada con 401")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Duplicado → 409 en segunda llamada
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_duplicate_transaction(mock_db, valid_payload, webhook_secret):
    """
    T3: Si transaction_id ya fue procesado (hash_tx en BD), retornar 409.
    """
    from routers.global66 import procesar_webhook_global66

    # Simulate that hash_tx already exists
    existing_hash = hashlib.md5(valid_payload["transaction_id"].encode()).hexdigest()
    mock_db.global66_transacciones_procesadas.find_one = AsyncMock(return_value={
        "hash_tx": existing_hash,
        "transaction_id": valid_payload["transaction_id"],
        "estado": "procesado",
    })

    body_bytes = json.dumps(valid_payload).encode("utf-8")
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    from fastapi import Request, HTTPException

    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.headers = {"X-Global66-Signature": signature}

    with patch("routers.global66.db", mock_db):
        with patch.dict(os.environ, {"GLOBAL66_WEBHOOK_SECRET": webhook_secret}):
            with pytest.raises(HTTPException) as exc_info:
                await procesar_webhook_global66(mock_request)

    assert exc_info.value.status_code == 409, (
        f"Duplicado debe retornar 409, recibido {exc_info.value.status_code}"
    )
    assert "duplicado" in str(exc_info.value.detail).lower(), (
        "El error debe mencionar 'duplicado'"
    )
    print("T3 PASÓ: Transaccion duplicada rechazada con 409")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Alta confianza (>=0.70) → crea journal en Alegra
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_high_confianza_creates_journal(mock_db, webhook_secret):
    """
    T4: payload con confianza=0.85 → llama request_with_verify("journals", "POST", ...)
    y retorna _verificado=True.
    """
    from routers.global66 import procesar_webhook_global66

    payload = {
        "transaction_id": "GLB-TX-HIGH-001",
        "tipo": "credit",
        "monto": 500000.0,
        "descripcion": "transferencia cliente cartera",
        "fecha": "2026-04-01",
        "confianza": 0.85,
    }

    mock_journal = {
        "id": "JE-GLB-001",
        "_verificado": True,
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.headers = {"X-Global66-Signature": signature}

    with patch("routers.global66.db", mock_db):
        with patch("routers.global66.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(return_value=mock_journal)

            with patch.dict(os.environ, {"GLOBAL66_WEBHOOK_SECRET": webhook_secret}):
                result = await procesar_webhook_global66(mock_request)

    assert mock_service.request_with_verify.called, "request_with_verify debe ser llamado"
    call_args = mock_service.request_with_verify.call_args
    assert call_args[0][0] == "journals", (
        "Debe usar /journals NUNCA /journal-entries (ERROR-008)"
    )
    assert call_args[0][1] == "POST", "Metodo debe ser POST"
    assert result["_verificado"] is True, "Respuesta debe incluir _verificado=True"
    print("T4 PASÓ: Alta confianza → journal creado en Alegra")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Baja confianza (<0.70) → inserta en conciliacion_partidas + evento
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_low_confianza_routes_to_conciliacion(mock_db, webhook_secret):
    """
    T5: payload con confianza=0.50 → inserta en conciliacion_partidas con
    estado="pendiente" y publica evento global66.movimiento.pendiente.
    """
    from routers.global66 import procesar_webhook_global66

    payload = {
        "transaction_id": "GLB-TX-LOW-001",
        "tipo": "unknown",
        "monto": 50000.0,
        "descripcion": "movimiento sin clasificar",
        "fecha": "2026-04-01",
        "confianza": 0.50,
    }

    body_bytes = json.dumps(payload).encode("utf-8")
    signature = hmac.new(
        webhook_secret.encode("utf-8"),
        body_bytes,
        hashlib.sha256
    ).hexdigest()

    from fastapi import Request

    mock_request = MagicMock(spec=Request)
    mock_request.body = AsyncMock(return_value=body_bytes)
    mock_request.headers = {"X-Global66-Signature": signature}

    captured_conciliacion = None
    captured_event = None

    async def capture_conciliacion(doc):
        nonlocal captured_conciliacion
        captured_conciliacion = doc

    async def capture_event(doc):
        nonlocal captured_event
        captured_event = doc

    mock_db.conciliacion_partidas.insert_one = AsyncMock(side_effect=capture_conciliacion)
    mock_db.roddos_events.insert_one = AsyncMock(side_effect=capture_event)

    with patch("routers.global66.db", mock_db):
        with patch.dict(os.environ, {"GLOBAL66_WEBHOOK_SECRET": webhook_secret}):
            result = await procesar_webhook_global66(mock_request)

    assert result["procesado"] is False, "Baja confianza debe retornar procesado=False"
    assert "confianza_baja" in result.get("motivo", ""), "Motivo debe ser confianza_baja"

    assert captured_conciliacion is not None, "Debe insertar en conciliacion_partidas"
    assert captured_conciliacion["estado"] == "pendiente", "Estado debe ser pendiente"
    assert captured_conciliacion["origen"] == "global66", "Origen debe ser global66"
    assert captured_conciliacion["transaction_id"] == "GLB-TX-LOW-001"

    assert captured_event is not None, "Debe publicar evento"
    assert "global66" in captured_event.get("event_type", "").lower(), (
        "event_type debe contener 'global66'"
    )
    print("T5 PASÓ: Baja confianza → conciliacion_partidas + evento publicado")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Confianza calculada desde scoring cuando no viene en payload
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_webhook_confianza_from_scoring(mock_db, webhook_secret):
    """
    T6: Payload SIN campo 'confianza' → usa _calcular_confianza(monto, descripcion).
    monto=500000 + descripcion con 'transferencia' + tipo='credit' → debe ser >= 0.70.
    """
    from routers.global66 import _calcular_confianza

    # Test scoring function directly
    score = _calcular_confianza(500000.0, "transferencia pago mensual", "credit")
    assert score >= 0.70, (
        f"Scoring con monto>0, keyword 'transferencia', tipo='credit' debe ser >=0.70, got {score}"
    )

    # Also test that low-signal payload scores low
    score_low = _calcular_confianza(0.0, "sin datos relevantes", "desconocido")
    assert score_low < 0.70, (
        f"Scoring sin señales debe ser <0.70, got {score_low}"
    )

    print(f"T6 PASÓ: scoring alto={score:.2f}, bajo={score_low:.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7: GET /sync retorna counts del día
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_sync_returns_counts(mock_db, mock_user):
    """
    T7: GET /global66/sync retorna {sincronizados, pendientes, errores, fecha}.
    """
    from routers.global66 import obtener_sync_global66

    mock_db.global66_transacciones_procesadas.count_documents = AsyncMock(
        side_effect=[5, 2, 1]  # sincronizados, pendientes, errores
    )

    with patch("routers.global66.db", mock_db):
        result = await obtener_sync_global66(mock_user)

    assert "sincronizados" in result, "Respuesta debe tener 'sincronizados'"
    assert "pendientes" in result, "Respuesta debe tener 'pendientes'"
    assert "errores" in result, "Respuesta debe tener 'errores'"
    assert "fecha" in result, "Respuesta debe tener 'fecha'"
    assert result["sincronizados"] == 5
    assert result["pendientes"] == 2
    assert result["errores"] == 1
    print(f"T7 PASÓ: sync retornó sincronizados={result['sincronizados']}, pendientes={result['pendientes']}, errores={result['errores']}")
