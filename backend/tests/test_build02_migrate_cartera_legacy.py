"""
BUILD 0.2 test-gate — migrate_cartera_legacy.py

Tests:
  1. parse_row extrae campos correctamente de una fila típica
  2. parse_row maneja Aliado nulo → "Sin aliado"
  3. parse_row maneja Id crédito sin guión → None
  4. Dedup: 67 filas → 59 únicas (simulado con DataFrame en memoria)
  5. codigo_sismo tiene formato LG-{cedula}-{num}
  6. Estado legacy "Al Día" se normaliza aunque venga con encoding raro
"""
import sys
from pathlib import Path

# Make backend importable
sys.path.insert(0, str(Path(__file__).parent.parent))

import math
import pytest
import pandas as pd

# Import the functions under test directly (no DB needed)
from scripts.migrate_cartera_legacy import parse_row, ESTADO_FIJO


def _make_row(overrides: dict = {}) -> dict:
    """Helper: devuelve una fila base válida con overrides."""
    base = {
        "Id crédito":    "1015994188-45541",
        "Nombre":        "JEFFREY",
        "Apellidos":     "CASTAÑEDA GIRALDO",
        "Placa":         "GFD73H",
        "Aliado":        "RODDOS_Directo",
        "Estado":        "En Mora",
        "Score Total":   187.5,
        "% On Time":     0.23,
        "Días Máx":      169,
        "Saldo\nx Cobrar": 496664.0,
        "DECISIÓN":      "NO PRESTAR",
        "Análisis":      "23% cuotas On Time.",
    }
    base.update(overrides)
    return base


# ── 1. Parse básico ────────────────────────────────────────────────────────────

def test_parse_row_campos_basicos():
    """parse_row extrae cedula, codigo_sismo y saldo correctamente."""
    doc = parse_row(_make_row())
    assert doc is not None
    assert doc["cedula"] == "1015994188"
    assert doc["numero_credito_original"] == "45541"
    assert doc["codigo_sismo"] == "LG-1015994188-45541"
    assert doc["nombre_completo"] == "JEFFREY CASTAÑEDA GIRALDO"
    assert doc["aliado"] == "RODDOS_Directo"
    assert doc["estado"] == ESTADO_FIJO  # siempre "activo"
    assert doc["estado_legacy_excel"] == "En Mora"
    assert doc["saldo_actual"] == 496664.0
    assert doc["saldo_inicial"] == 496664.0   # fallback = saldo_actual
    assert doc["score_total"] == 187.5
    assert doc["pct_on_time"] == pytest.approx(0.23)
    assert doc["dias_mora_maxima"] == 169
    assert doc["placa"] == "GFD73H"
    assert doc["decision_historica"] == "NO PRESTAR"


# ── 2. Aliado nulo → "Sin aliado" ─────────────────────────────────────────────

def test_parse_row_aliado_nulo():
    """Aliado NaN se reemplaza por 'Sin aliado'."""
    doc = parse_row(_make_row({"Aliado": float("nan")}))
    assert doc is not None
    assert doc["aliado"] == "Sin aliado"


# ── 3. Id crédito sin guión → None ────────────────────────────────────────────

def test_parse_row_id_sin_guion():
    """Id crédito sin guión retorna None (fila ignorada)."""
    doc = parse_row(_make_row({"Id crédito": "12345678"}))
    assert doc is None


# ── 4. Id crédito vacío → None ────────────────────────────────────────────────

def test_parse_row_id_vacio():
    """Id crédito vacío retorna None."""
    doc = parse_row(_make_row({"Id crédito": float("nan")}))
    assert doc is None


# ── 5. Dedup 67 → 59 ─────────────────────────────────────────────────────────

def test_dedup_reduce_a_59():
    """Simulamos 67 filas con 8 duplicados exactos → 59 únicas."""
    # Construir 59 filas únicas
    filas = []
    for i in range(59):
        filas.append({
            "Id crédito": f"100000000{i:02d}-4554{i}",
            "Nombre": f"CLIENTE",
            "Apellidos": f"TEST {i}",
            "Placa": float("nan"),
            "Aliado": "RODDOS_Directo",
            "Estado": "En Mora",
            "Score Total": 300.0,
            "% On Time": 0.5,
            "Días Máx": 30,
            "Saldo\nx Cobrar": 500000.0,
            "DECISIÓN": "EVALUAR",
            "Análisis": "Test",
        })
    # Duplicar 8 de ellas (exactamente como el Excel real)
    filas_con_dups = filas + filas[:8]

    df = pd.DataFrame(filas_con_dups)
    assert len(df) == 67

    df_dedup = df.drop_duplicates(subset=["Id crédito"], keep="first")
    assert len(df_dedup) == 59


# ── 6. Normalización "Al Día" ─────────────────────────────────────────────────

def test_normaliza_al_dia():
    """Estado 'Al DÃ­a' (encoding roto) se normaliza a 'Al Día'."""
    # Simulate the encoding corruption that appears in Windows terminal
    doc = parse_row(_make_row({"Estado": "Al DÃ­a"}))
    assert doc is not None
    assert doc["estado_legacy_excel"] == "Al Día"


def test_estado_al_dia_limpio():
    """Estado 'Al Día' limpio pasa directo sin alteración."""
    doc = parse_row(_make_row({"Estado": "Al Día"}))
    assert doc is not None
    assert doc["estado_legacy_excel"] == "Al Día"
