"""
BUILD 0.1 test-gate — cartera_legacy collection + endpoints.

Tests:
  1. Collection can be created + a document inserted (schema valid)
  2. GET /api/cartera-legacy returns 200 with pagination
  3. GET /api/cartera-legacy/stats returns 200
  4. GET /api/cartera-legacy/{codigo} returns 404 on unknown, 200 on known
"""
import asyncio
import pytest
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

# ── 1. Schema validation ───────────────────────────────────────────────────────

def test_loanbook_legacy_schema_valid():
    """LoanbookLegacyDoc can be instantiated with required fields."""
    from routers.cartera_legacy import LoanbookLegacyDoc

    doc = LoanbookLegacyDoc(
        codigo_sismo="LG-80075452-1",
        cedula="80075452",
        numero_credito_original="1",
        nombre_completo="Andrés Sanjuan",
        aliado="RODDOS_Directo",
        estado="activo",
        estado_legacy_excel="Al Día",
        saldo_actual=5_000_000.0,
        saldo_inicial=8_000_000.0,
    )
    assert doc.codigo_sismo == "LG-80075452-1"
    assert doc.saldo_actual == 5_000_000.0
    assert doc.pagos_recibidos == []
    assert doc.alegra_contact_id is None


def test_loanbook_legacy_schema_with_pagos():
    """LoanbookLegacyDoc accepts pagos_recibidos list."""
    from routers.cartera_legacy import LoanbookLegacyDoc, PagoRegistrado

    pago = PagoRegistrado(fecha="2026-03-15", monto=500_000.0, alegra_journal_id="123")
    doc = LoanbookLegacyDoc(
        codigo_sismo="LG-123-1",
        cedula="123",
        numero_credito_original="1",
        nombre_completo="Test Cliente",
        aliado="Motai",
        estado="activo",
        estado_legacy_excel="En Mora",
        saldo_actual=3_000_000.0,
        saldo_inicial=3_500_000.0,
        pagos_recibidos=[pago],
    )
    assert len(doc.pagos_recibidos) == 1
    assert doc.pagos_recibidos[0].monto == 500_000.0


# ── 2-4. Endpoint smoke tests (mock DB) ───────────────────────────────────────

@pytest.mark.asyncio
async def test_list_endpoint_returns_empty_when_no_data():
    """GET /cartera-legacy returns success=True + empty list when DB empty."""
    from routers.cartera_legacy import list_cartera_legacy

    async def _empty_aiter():
        return
        yield  # makes it an async generator

    mock_cursor = MagicMock()
    mock_cursor.sort.return_value = mock_cursor
    mock_cursor.skip.return_value = mock_cursor
    mock_cursor.limit.return_value = mock_cursor
    # __aiter__ is called as a bound method (receives self), so wrap it
    mock_cursor.__aiter__ = lambda self: _empty_aiter()

    with patch("routers.cartera_legacy.db") as mock_db:
        mock_db.loanbook_legacy.count_documents = AsyncMock(return_value=0)
        mock_db.loanbook_legacy.find.return_value = mock_cursor

        result = await list_cartera_legacy(
            estado=None, aliado=None, en_mora=None,
            page=1, limit=50,
            current_user={"id": "test", "role": "admin"},
        )

    assert result["success"] is True
    assert result["data"] == []
    assert result["total"] == 0


@pytest.mark.asyncio
async def test_stats_endpoint_returns_success():
    """GET /cartera-legacy/stats returns success=True."""
    from routers.cartera_legacy import get_cartera_legacy_stats

    # Simulate empty aggregate
    async def fake_agg(pipeline):
        return
        yield  # make it async generator

    with patch("routers.cartera_legacy.db") as mock_db:
        mock_db.loanbook_legacy.aggregate.return_value.__aiter__ = AsyncMock(
            return_value=iter([])
        )

        async def empty_gen(*args, **kwargs):
            return
            yield

        mock_db.loanbook_legacy.aggregate = lambda p: empty_gen()

        result = await get_cartera_legacy_stats(
            current_user={"id": "test", "role": "admin"},
        )

    assert result["success"] is True
    assert "data" in result


@pytest.mark.asyncio
async def test_detalle_endpoint_404_on_unknown():
    """GET /cartera-legacy/{codigo} raises 404 when not found."""
    from routers.cartera_legacy import get_cartera_legacy_detalle
    from fastapi import HTTPException

    with patch("routers.cartera_legacy.db") as mock_db:
        mock_db.loanbook_legacy.find_one = AsyncMock(return_value=None)

        with pytest.raises(HTTPException) as exc_info:
            await get_cartera_legacy_detalle(
                codigo="LG-NOEXISTE-1",
                current_user={"id": "test", "role": "admin"},
            )

    assert exc_info.value.status_code == 404


@pytest.mark.asyncio
async def test_detalle_endpoint_200_on_known():
    """GET /cartera-legacy/{codigo} returns doc when found."""
    from routers.cartera_legacy import get_cartera_legacy_detalle

    mock_doc = {
        "_id": "fake_oid",
        "codigo_sismo": "LG-80075452-1",
        "cedula": "80075452",
        "numero_credito_original": "1",
        "nombre_completo": "Andrés Sanjuan",
        "aliado": "RODDOS_Directo",
        "estado": "activo",
        "estado_legacy_excel": "Al Día",
        "saldo_actual": 5_000_000.0,
        "saldo_inicial": 8_000_000.0,
        "pagos_recibidos": [],
    }

    with patch("routers.cartera_legacy.db") as mock_db:
        mock_db.loanbook_legacy.find_one = AsyncMock(return_value=mock_doc)

        result = await get_cartera_legacy_detalle(
            codigo="LG-80075452-1",
            current_user={"id": "test", "role": "admin"},
        )

    assert result["success"] is True
    assert result["data"]["codigo_sismo"] == "LG-80075452-1"
    assert "_id" not in result["data"]  # must be stripped
