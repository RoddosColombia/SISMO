"""test_accounting_engine.py — Tests para clasificar_movimiento() en accounting_engine.py."""

import pytest
from services.accounting_engine import clasificar_movimiento


def test_doble_espacio_rappi_va_a_5413():
    """Bancolombia usa doble espacio: 'COMPRA EN  RAPPI COLO' — debe clasificar igual."""
    result = clasificar_movimiento("COMPRA EN  RAPPI COLO", banco_origen=5314)
    assert result.cuenta_debito == 5413, f"Esperado 5413, obtenido {result.cuenta_debito}"
    assert result.confianza >= 0.85


def test_doble_espacio_k_tronix_va_a_5484():
    result = clasificar_movimiento("COMPRA EN  K TRONIX C", banco_origen=5314)
    assert result.cuenta_debito == 5484


def test_doble_espacio_mc_donald_va_a_5413():
    result = clasificar_movimiento("COMPRA EN  MC DONALD", banco_origen=5314)
    assert result.cuenta_debito == 5413
