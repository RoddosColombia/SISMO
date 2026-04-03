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


# ══════════════════════════════════════════════════════════════════════════════
# 6 REGLAS NUEVAS BBVA + FIX CXC GAST ABREVIADO
# ══════════════════════════════════════════════════════════════════════════════

def test_cxc_gast_abreviado_andres_va_a_5413():
    """BBVA abrevia 'GASTO' como 'GAST': 'CXC GAST SOCIO ANDRES' → 5413 (NO 5329)."""
    result = clasificar_movimiento("CXC GAST SOCIO ANDRES", banco_origen=5314)
    assert result.cuenta_debito == 5413, f"Esperado 5413, obtenido {result.cuenta_debito}"
    assert result.cuenta_credito == 5314


def test_cxc_gast_abreviado_ivan_va_a_5413():
    """BBVA abrevia 'GASTO' como 'GAST': 'CXC GAST SOCIO IVAN' → 5413 (NO 5329)."""
    result = clasificar_movimiento("CXC GAST SOCIO IVAN", banco_origen=5314)
    assert result.cuenta_debito == 5413, f"Esperado 5413, obtenido {result.cuenta_debito}"
    assert result.cuenta_credito == 5314


def test_servicios_publicos_no_clasifica_cxc_gasto():
    """'CXC GASTO ANDRES ENEL' NO debe caer en servicios públicos — debe ser 5413."""
    result = clasificar_movimiento("CXC GASTO ANDRES ENEL", banco_origen=5314)
    assert result.cuenta_debito != 5485, "servicios_publicos NO debe clasificar descripciones con 'cxc' o 'socio'"


def test_abono_intereses_ganados_va_a_5456():
    """'ABONO INTERESES GANADOS BBVA' → 5456 Ingresos Financieros."""
    result = clasificar_movimiento("ABONO INTERESES GANADOS BBVA", banco_origen=5314)
    assert result.cuenta_credito == 5456, f"Esperado 5456, obtenido {result.cuenta_credito}"
    assert result.confianza >= 0.85


def test_bbva_comision_bbvac_va_a_5508():
    """'COMISION BBVAC' → 5508 Comisiones Bancarias."""
    result = clasificar_movimiento("COMISION BBVAC", banco_origen=5314)
    assert result.cuenta_debito == 5508, f"Esperado 5508, obtenido {result.cuenta_debito}"
    assert result.cuenta_credito == 5314


def test_bbva_intereses_raul_va_a_5534():
    """'INTERESES RAUL GARCIA' → 5534 Intereses Rentistas."""
    result = clasificar_movimiento("INTERESES RAUL GARCIA", banco_origen=5314)
    assert result.cuenta_debito == 5534, f"Esperado 5534, obtenido {result.cuenta_debito}"


def test_bbva_liquidacion_liliana_va_a_5462():
    """'LIQUIDACION LILIANA MARTINEZ' → 5462 Sueldos y Salarios."""
    result = clasificar_movimiento("LIQUIDACION LILIANA MARTINEZ", banco_origen=5314)
    assert result.cuenta_debito == 5462, f"Esperado 5462, obtenido {result.cuenta_debito}"


def test_bbva_aseo_monica_va_a_5482():
    """'ASEO MONICA' → 5482 Aseo y Vigilancia."""
    result = clasificar_movimiento("ASEO MONICA", banco_origen=5314)
    assert result.cuenta_debito == 5482, f"Esperado 5482, obtenido {result.cuenta_debito}"
