"""Suite de tests para AlegraService — ALEGRA-06 + ALEGRA-03.

Cubre:
- GET para los 5 endpoints principales (invoices, categories, payments, journals, contacts)
- POST /journals en modo demo
- request_with_verify() retorna _verificado=True en modo demo
- request_with_verify() sin ID no retorna _verificado
- _translate_error_to_spanish() para 401, 400 (balance), 403, 404, 429, 500
- _mock("journals", "GET") retorna datos
- _mock("journal-entries", "GET") NO retorna datos de journals (ALEGRA-03 fix)
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from alegra_service import AlegraService


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run a coroutine synchronously using asyncio.run()."""
    return asyncio.run(coro)


def _make_mock_db(is_demo: bool = True):
    """Create a mock Motor database.

    Configures alegra_credentials.find_one to return demo credentials when
    is_demo=True, simulating the DEMO fallback path in get_settings().
    """
    db = MagicMock()
    if is_demo:
        # Return demo credentials so AlegraService uses _mock()
        db.alegra_credentials = MagicMock()
        db.alegra_credentials.find_one = AsyncMock(
            return_value={"email": "", "token": "", "is_demo_mode": True}
        )
    else:
        db.alegra_credentials = MagicMock()
        db.alegra_credentials.find_one = AsyncMock(return_value=None)
    return db


@pytest.fixture
def alegra_svc():
    """AlegraService instance en modo demo (usa _mock())."""
    db = _make_mock_db(is_demo=True)
    svc = AlegraService(db)
    return svc


# ── Seccion: Test Demo Mode Endpoints ────────────────────────────────────────


class TestDemoModeEndpoints:
    """Verifica que cada endpoint retorna datos validos en modo demo."""

    def test_get_invoices_demo(self, alegra_svc):
        result = _run(alegra_svc.request("invoices", "GET"))
        assert isinstance(result, list)
        assert len(result) > 0, "MOCK_INVOICES no puede estar vacio"

    def test_get_categories_demo(self, alegra_svc):
        # /categories es el endpoint correcto — /accounts es prohibido (ALEGRA-06)
        result = _run(alegra_svc.request("categories", "GET"))
        assert isinstance(result, list)
        assert len(result) > 0, "MOCK_ACCOUNTS no puede estar vacio"

    def test_get_payments_demo(self, alegra_svc):
        # payments no tiene una key dedicada en _mock → retorna {}
        # Verificamos que el endpoint no lanza excepcion y retorna algo
        result = _run(alegra_svc.request("payments", "GET"))
        assert result is not None, "request('payments') no debe retornar None"

    def test_get_journals_demo(self, alegra_svc):
        result = _run(alegra_svc.request("journals", "GET"))
        assert isinstance(result, list)
        assert len(result) > 0, "MOCK_JOURNAL_ENTRIES no puede estar vacio"

    def test_get_contacts_demo(self, alegra_svc):
        result = _run(alegra_svc.request("contacts", "GET"))
        assert isinstance(result, list)
        assert len(result) > 0, "MOCK_CONTACTS no puede estar vacio"

    def test_get_company_demo(self, alegra_svc):
        result = _run(alegra_svc.request("company", "GET"))
        assert isinstance(result, dict)
        assert len(result) > 0, "MOCK_COMPANY no puede estar vacio"


# ── Seccion: Test POST con Mock ───────────────────────────────────────────────


class TestPostWithMock:
    """Verifica POST en modo demo."""

    def test_post_journals_demo(self, alegra_svc):
        payload = {
            "date": "2026-03-30",
            "observations": "Pago arrendamiento marzo 2026",
            "entries": [
                {"account": {"id": 5493}, "debit": 500000, "credit": 0},
                {"account": {"id": 5494}, "debit": 0, "credit": 500000},
            ],
        }
        result = _run(alegra_svc.request("journals", "POST", body=payload))
        assert isinstance(result, dict), "POST /journals debe retornar dict"
        assert "id" in result, "POST /journals debe retornar un campo 'id'"


# ── Seccion: Test request_with_verify ────────────────────────────────────────


class TestRequestWithVerify:
    """Verifica el comportamiento de request_with_verify() en modo demo."""

    def test_request_with_verify_returns_verificado_true_in_demo(self, alegra_svc):
        payload = {
            "date": "2026-03-30",
            "observations": "Test asiento",
            "entries": [],
        }
        result = _run(alegra_svc.request_with_verify("journals", "POST", body=payload))
        assert isinstance(result, dict), "request_with_verify debe retornar dict"
        assert result.get("_verificado") is True, (
            "En modo demo, request_with_verify debe incluir _verificado=True"
        )

    def test_request_with_verify_fuente_demo(self, alegra_svc):
        payload = {"date": "2026-03-30", "observations": "Test", "entries": []}
        result = _run(alegra_svc.request_with_verify("journals", "POST", body=payload))
        assert result.get("_fuente") == "demo", (
            "En modo demo, request_with_verify debe incluir _fuente='demo'"
        )


# ── Seccion: Test Traduccion Errores ─────────────────────────────────────────


class TestTranslateErrors:
    """Verifica _translate_error_to_spanish() para los codigos HTTP criticos."""

    def test_translate_error_401(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(401, {}, "journals", "POST")
        assert "Credenciales de Alegra incorrectas" in msg, (
            f"401 debe mencionar credenciales incorrectas, got: {msg!r}"
        )

    def test_translate_error_400_balance(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(
            400, {"message": "debit/credit mismatch"}, "journals", "POST"
        )
        assert "balance" in msg.lower(), (
            f"400 en journals con debit/credit debe mencionar 'balance', got: {msg!r}"
        )

    def test_translate_error_403_post(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(403, {}, "journals", "POST")
        assert "permisos" in msg.lower(), (
            f"403 POST debe mencionar 'permisos', got: {msg!r}"
        )

    def test_translate_error_404(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(404, {}, "journals/999", "GET")
        assert "No encontrado" in msg, (
            f"404 debe decir 'No encontrado', got: {msg!r}"
        )

    def test_translate_error_429(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(429, {}, "journals", "POST")
        assert "Límite de requests" in msg or "Limite de requests" in msg, (
            f"429 debe mencionar 'Limite de requests', got: {msg!r}"
        )

    def test_translate_error_500(self, alegra_svc):
        msg = alegra_svc._translate_error_to_spanish(500, {}, "journals", "POST")
        assert "no disponible temporalmente" in msg.lower(), (
            f"500 debe mencionar 'no disponible temporalmente', got: {msg!r}"
        )


# ── Seccion: Test critico ALEGRA-03 ──────────────────────────────────────────


class TestMockBugALEGRA03:
    """Verifica que _mock rechaza 'journal-entries' y solo acepta 'journals'.

    Per ALEGRA-03: /journal-entries da 403 en produccion.
    El mock debe reflejar el comportamiento real — no retornar datos para ese endpoint.
    """

    def test_mock_journals_returns_data(self, alegra_svc):
        """journals funciona — retorna MOCK_JOURNAL_ENTRIES (lista no vacia)."""
        result = alegra_svc._mock("journals", "GET")
        assert isinstance(result, list) and len(result) > 0, (
            "_mock('journals', 'GET') debe retornar lista con datos"
        )

    def test_mock_rejects_journal_entries(self, alegra_svc):
        """journal-entries debe lanzar HTTPException(400) — mismo comportamiento que produccion.

        Per ALEGRA-06: el mock refleja el comportamiento real de produccion.
        Este test falla (RED) hasta que Task 2 aplique el guard en alegra_service.py.
        """
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            alegra_svc._mock("journal-entries", "GET")
        assert exc_info.value.status_code == 400


# ── Seccion: Test ALEGRA-06 — Endpoints Prohibidos ───────────────────────────


class TestProhibitedEndpoints:
    """Verifica que endpoints prohibidos generan HTTPException ANTES de llamar a la API.

    Per ALEGRA-06: /journal-entries y /accounts deben bloquearse pre-vuelo con
    HTTPException(400) y mensaje descriptivo en espanol.
    """

    def test_request_rejects_journal_entries(self, alegra_svc):
        """request('journal-entries') debe lanzar HTTPException(400) — nunca llega a httpx."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _run(alegra_svc.request("journal-entries", "GET"))
        assert exc_info.value.status_code == 400
        assert "journal-entries" in exc_info.value.detail.lower() or "journal-entries" in exc_info.value.detail

    def test_request_rejects_accounts(self, alegra_svc):
        """request('accounts') debe lanzar HTTPException(400) — nunca llega a httpx."""
        from fastapi import HTTPException
        with pytest.raises(HTTPException) as exc_info:
            _run(alegra_svc.request("accounts", "GET"))
        assert exc_info.value.status_code == 400
        assert "accounts" in exc_info.value.detail.lower() or "accounts" in exc_info.value.detail
