"""Suite de tests TDD — Phase 03 Plan 01: Acciones de Lectura ACTION_MAP.

Cubre los 5 action_type de lectura que FALTAN en execute_chat_action:
  - consultar_facturas
  - consultar_pagos
  - consultar_journals
  - consultar_cartera
  - consultar_plan_cuentas

FASE RED: Todos los tests deben FALLAR porque los handlers no existen aun en
ai_chat.py. La falla esperada es:
    ValueError: Accion no reconocida: consultar_facturas   (y similares)

Patrones de test:
  - asyncio.run() (no @pytest.mark.asyncio) — decision Phase 2
  - _make_mock_db() con is_demo=True
  - Mock AlegraService.request para verificar parametros
  - Lazy import de ai_chat dentro de cada test (ai_chat importa anthropic al
    top-level; el modulo no esta disponible en el entorno del worktree pero si
    en el entorno de ejecucion real — patron consistente con test_build23_f2)
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


# ── helpers ──────────────────────────────────────────────────────────────────

def _run(coro):
    """Run a coroutine synchronously using asyncio.run()."""
    return asyncio.run(coro)


def _make_mock_db(is_demo: bool = True):
    """Create a mock Motor database.

    Configures:
    - alegra_credentials.find_one to return demo credentials
    - loanbook.find() for consultar_cartera
    - cartera_pagos.find() for consultar_cartera
    """
    db = MagicMock()
    db.alegra_credentials = MagicMock()
    db.alegra_credentials.find_one = AsyncMock(
        return_value={"email": "", "token": "", "is_demo_mode": True}
    )

    # Mock loanbook collection for consultar_cartera
    mock_cursor = MagicMock()
    mock_cursor.to_list = AsyncMock(return_value=[
        {
            "codigo": "LB-2026-0001",
            "cliente": "Test Cliente",
            "estado": "activo",
            "saldo_pendiente": 5000000,
            "cuotas_pendientes": 10,
        }
    ])
    db.loanbook = MagicMock()
    db.loanbook.find = MagicMock(return_value=mock_cursor)

    # Mock cartera_pagos for consultar_cartera
    mock_pagos_cursor = MagicMock()
    mock_pagos_cursor.to_list = AsyncMock(return_value=[])
    db.cartera_pagos = MagicMock()
    db.cartera_pagos.find = MagicMock(return_value=mock_pagos_cursor)

    return db


MOCK_USER = {"id": "test-user", "username": "test", "role": "admin"}


# ── TestConsultarFacturas ─────────────────────────────────────────────────────


class TestConsultarFacturas:
    """Verifica que execute_chat_action('consultar_facturas', ...) funciona."""

    def test_returns_invoices(self):
        """Debe retornar success=True y una lista en 'facturas'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_facturas",
            {"fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "facturas" in result, f"Esperaba key 'facturas' en resultado: {result}"
        assert isinstance(result["facturas"], list), \
            f"result['facturas'] debe ser lista, es: {type(result['facturas'])}"

    def test_uses_limit_50(self):
        """AlegraService.request debe llamarse con params que incluyen limit=50."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()

        with patch("alegra_service.AlegraService.request", new_callable=AsyncMock) as mock_req:
            # Devolver datos de prueba
            mock_req.return_value = [
                {"id": "inv-001", "number": "FV-2026-001", "status": "open", "date": "2026-01-15"}
            ]
            result = _run(execute_chat_action(
                "consultar_facturas",
                {"fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"},
                db,
                MOCK_USER,
            ))

        # Verificar que se llamó request con limit=50
        assert mock_req.called, "AlegraService.request no fue llamado"
        call_kwargs = mock_req.call_args
        # Los params deben contener limit: 50
        params_used = None
        if call_kwargs.kwargs.get("params"):
            params_used = call_kwargs.kwargs["params"]
        elif len(call_kwargs.args) >= 4:
            params_used = call_kwargs.args[3]
        assert params_used is not None, \
            "request() no recibio params — limit=50 no fue enviado"
        assert params_used.get("limit") == 50, \
            f"Esperaba limit=50 en params, obtuvo: {params_used}"

    def test_date_format_yyyy_mm_dd(self):
        """Los params de fecha deben usar yyyy-MM-dd, no ISO-8601 con timezone."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()

        with patch("alegra_service.AlegraService.request", new_callable=AsyncMock) as mock_req:
            mock_req.return_value = []
            _run(execute_chat_action(
                "consultar_facturas",
                {"fecha_desde": "2026-01-01", "fecha_hasta": "2026-01-31"},
                db,
                MOCK_USER,
            ))

        assert mock_req.called, "AlegraService.request no fue llamado"
        call_kwargs = mock_req.call_args
        params_used = None
        if call_kwargs.kwargs.get("params"):
            params_used = call_kwargs.kwargs["params"]
        elif len(call_kwargs.args) >= 4:
            params_used = call_kwargs.args[3]

        assert params_used is not None, "request() no recibio params"

        # Verificar claves de fecha correctas (Alegra espera estos nombres)
        assert "date_afterOrNow" in params_used or "date_after" in params_used, \
            f"Params no tienen fecha inicio: {params_used}"
        assert "date_beforeOrNow" in params_used or "date_before" in params_used, \
            f"Params no tienen fecha fin: {params_used}"

        # Verificar formato yyyy-MM-dd — NO debe contener T ni Z
        fecha_val = params_used.get("date_afterOrNow") or params_used.get("date_after", "")
        assert "T" not in str(fecha_val), \
            f"Fecha tiene formato ISO-8601 con T, debe ser yyyy-MM-dd: {fecha_val}"
        assert "Z" not in str(fecha_val), \
            f"Fecha tiene timezone Z, debe ser yyyy-MM-dd: {fecha_val}"


# ── TestConsultarPagos ────────────────────────────────────────────────────────


class TestConsultarPagos:
    """Verifica que execute_chat_action('consultar_pagos', ...) funciona."""

    def test_type_in(self):
        """Tipo 'in' (pagos recibidos) debe retornar success=True y lista 'pagos'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_pagos",
            {"tipo": "in"},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "pagos" in result, f"Esperaba key 'pagos' en resultado: {result}"
        assert isinstance(result["pagos"], list), \
            f"result['pagos'] debe ser lista, es: {type(result['pagos'])}"

    def test_type_out(self):
        """Tipo 'out' (pagos realizados) debe retornar success=True y lista 'pagos'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_pagos",
            {"tipo": "out"},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "pagos" in result, f"Esperaba key 'pagos' en resultado: {result}"
        assert isinstance(result["pagos"], list), \
            f"result['pagos'] debe ser lista, es: {type(result['pagos'])}"


# ── TestConsultarJournals ─────────────────────────────────────────────────────


class TestConsultarJournals:
    """Verifica que execute_chat_action('consultar_journals', ...) funciona."""

    def test_returns_journals(self):
        """Debe retornar success=True y lista en 'journals'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_journals",
            {"fecha_desde": "2026-02-01", "fecha_hasta": "2026-02-28"},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "journals" in result, f"Esperaba key 'journals' en resultado: {result}"
        assert isinstance(result["journals"], list), \
            f"result['journals'] debe ser lista, es: {type(result['journals'])}"


# ── TestConsultarCartera ──────────────────────────────────────────────────────


class TestConsultarCartera:
    """Verifica que execute_chat_action('consultar_cartera', ...) lee MongoDB, no Alegra."""

    def test_reads_mongodb_not_alegra(self):
        """Cartera viene de MongoDB (loanbook), NO de AlegraService.request."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()

        with patch("alegra_service.AlegraService.request", new_callable=AsyncMock) as mock_req:
            result = _run(execute_chat_action(
                "consultar_cartera",
                {},
                db,
                MOCK_USER,
            ))

        # AlegraService.request NO debe haber sido llamado
        assert not mock_req.called, \
            "consultar_cartera llamo a AlegraService.request — debe leer MongoDB directo"

        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "cartera" in result, f"Esperaba key 'cartera' en resultado: {result}"


# ── TestConsultarPlanCuentas ──────────────────────────────────────────────────


class TestConsultarPlanCuentas:
    """Verifica que execute_chat_action('consultar_plan_cuentas', ...) funciona."""

    def test_returns_categories(self):
        """Debe retornar success=True y lista en 'cuentas'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_plan_cuentas",
            {},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        assert "cuentas" in result, f"Esperaba key 'cuentas' en resultado: {result}"
        assert isinstance(result["cuentas"], list), \
            f"result['cuentas'] debe ser lista, es: {type(result['cuentas'])}"

    def test_includes_id_5493(self):
        """ID 5493 (Gastos Generales — fallback obligatorio) debe aparecer en 'cuentas'."""
        from ai_chat import execute_chat_action
        db = _make_mock_db()
        result = _run(execute_chat_action(
            "consultar_plan_cuentas",
            {},
            db,
            MOCK_USER,
        ))
        assert result["success"] is True, f"Esperaba success=True, obtuvo: {result}"
        cuentas = result.get("cuentas", [])

        # Buscar ID 5493 en el arbol de cuentas (puede ser int o string)
        def _find_id(accounts, target_id):
            for acc in accounts:
                if str(acc.get("id", "")) == str(target_id):
                    return True
                sub = acc.get("subAccounts") or acc.get("children") or []
                if _find_id(sub, target_id):
                    return True
            return False

        found = _find_id(cuentas, 5493)
        assert found, \
            f"ID 5493 (Gastos Generales fallback) no encontrado en las {len(cuentas)} cuentas retornadas. " \
            f"Este ID es obligatorio segun CLAUDE.md (NUNCA usar 5495)."
