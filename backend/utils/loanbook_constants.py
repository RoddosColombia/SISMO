"""
loanbook_constants.py — Constantes y helpers para modo de pago RODDOS.

Frecuencias soportadas:
  semanal   → cuota_base × 1       (cada 7 días  — cada miércoles)
  quincenal → cuota_base × 2.175   (cada 14 días — cada 2 miércoles)
  mensual   → cuota_base × 4.33    (cada 28 días — cada 4 miércoles)

REGLA: redondeo SIEMPRE hacia arriba (math.ceil) — nunca hacia abajo.

Tests:
  calcular_cuota_valor(130000, "quincenal") == 282750
  calcular_cuota_valor(149900, "quincenal") == 325973
  calcular_cuota_valor(179900, "semanal")   == 179900
  calcular_cuota_valor(149900, "mensual")   == 648967
  calcular_cuota_valor(130000, "mensual")   == 562900
"""
import math

MULTIPLICADORES_PAGO: dict[str, float] = {
    "semanal":   1.0,
    "quincenal": 2.175,
    "mensual":   4.33,
}

DIAS_ENTRE_COBROS: dict[str, int] = {
    "semanal":   7,
    "quincenal": 14,
    "mensual":   28,
}

MODOS_VALIDOS = frozenset(MULTIPLICADORES_PAGO.keys())


def calcular_cuota_valor(cuota_base: int, modo_pago: str) -> int:
    """Calcula el valor de la cuota según la frecuencia de pago.

    Args:
        cuota_base: Valor de la cuota semanal base (entero, en COP).
        modo_pago:  "semanal" | "quincenal" | "mensual"

    Returns:
        Valor de la cuota redondeado hacia arriba (math.ceil), siempre int.
    """
    multiplicador = MULTIPLICADORES_PAGO.get(modo_pago, 1.0)
    return math.ceil(cuota_base * multiplicador)


def dias_entre_cuotas(modo_pago: str) -> int:
    """Retorna el número de días entre cuotas para el modo de pago dado."""
    return DIAS_ENTRE_COBROS.get(modo_pago, 7)


def resumen_cuota(cuota_base: int, modo_pago: str) -> str:
    """Retorna string legible con el cálculo de la cuota para mostrar al usuario.

    Ejemplo: "Cuota quincenal: $325.973 (base $149.900 × 2.175, redondeado arriba)"
    """
    mult = MULTIPLICADORES_PAGO.get(modo_pago, 1.0)
    valor = calcular_cuota_valor(cuota_base, modo_pago)
    modo_label = modo_pago.capitalize()
    if mult == 1.0:
        return f"Cuota {modo_label}: ${valor:,.0f}".replace(",", ".")
    return (
        f"Cuota {modo_label}: ${valor:,.0f} "
        f"(base ${cuota_base:,.0f} × {mult}, redondeado arriba)"
    ).replace(",", ".")
