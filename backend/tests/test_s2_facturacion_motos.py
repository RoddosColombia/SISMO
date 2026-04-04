"""test_s2_facturacion_motos.py — S2: Verificar gaps en ventas.py (análisis estático)."""

import re
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

VENTAS_SOURCE = (Path(__file__).parent.parent / "routers" / "ventas.py").read_text(encoding="utf-8")


# T1: POST sin VIN → HTTP 400 (validación existe)
def test_vin_vacio_retorna_400():
    assert "VIN obligatorio" in VENTAS_SOURCE or "moto_chasis" in VENTAS_SOURCE, \
        "No se encontró validación de VIN en ventas.py"
    assert "status_code=400" in VENTAS_SOURCE, "No hay HTTP 400 en ventas.py"
    # Verificar que la validación ocurre ANTES de llamar Alegra
    vin_check_pos = VENTAS_SOURCE.find("VIN obligatorio")
    alegra_post_pos = VENTAS_SOURCE.find('request_with_verify("invoices"')
    assert vin_check_pos < alegra_post_pos, \
        "La validación de VIN debe ocurrir ANTES de llamar Alegra"


# T2: POST sin motor → HTTP 400
def test_motor_vacio_retorna_400():
    assert "Motor obligatorio" in VENTAS_SOURCE, \
        "No se encontró validación de motor en ventas.py"
    motor_check_pos = VENTAS_SOURCE.find("Motor obligatorio")
    alegra_post_pos = VENTAS_SOURCE.find('request_with_verify("invoices"')
    assert motor_check_pos < alegra_post_pos, \
        "La validación de motor debe ocurrir ANTES de llamar Alegra"


# T3: moto estado != "Disponible" → HTTP 400
def test_moto_no_disponible_retorna_400():
    assert '"Disponible"' in VENTAS_SOURCE, \
        "No se verifica moto.estado == Disponible"
    assert "no se puede vender" in VENTAS_SOURCE or "no está Disponible" in VENTAS_SOURCE or \
           "Debe estar Disponible" in VENTAS_SOURCE, \
        "No hay mensaje de error claro cuando moto no está Disponible"


# T4: factura creada → ítem Alegra contiene "VIN:" en description o name
def test_item_alegra_contiene_vin():
    assert "VIN:" in VENTAS_SOURCE, \
        "El ítem de Alegra no incluye 'VIN:' en description o name"
    # Verificar que aparece en el payload de la factura (cerca de observations o product_description)
    assert "product_description" in VENTAS_SOURCE or "observations" in VENTAS_SOURCE, \
        "No se construye descripción del producto con VIN"


# T5: factura creada → inventario_motos.estado == "Vendida"
def test_inventario_actualiza_a_vendida():
    assert '"Vendida"' in VENTAS_SOURCE, \
        "inventario_motos no se actualiza a 'Vendida'"
    # Debe ocurrir DESPUÉS del request_with_verify exitoso
    alegra_post_pos = VENTAS_SOURCE.find('request_with_verify("invoices"')
    vendida_pos = VENTAS_SOURCE.find('"Vendida"', alegra_post_pos)
    assert vendida_pos > alegra_post_pos, \
        "El estado 'Vendida' debe asignarse DESPUÉS del request_with_verify"


# T6: factura creada → loanbook.estado == "pendiente_entrega"
def test_loanbook_en_pendiente_entrega():
    assert '"pendiente_entrega"' in VENTAS_SOURCE, \
        "loanbook no se crea con estado 'pendiente_entrega'"


# T7: factura creada → evento "factura.venta.creada" en roddos_events
def test_evento_factura_venta_publicado():
    assert "factura.venta.creada" in VENTAS_SOURCE, \
        "No se publica evento 'factura.venta.creada' en roddos_events"
    assert "roddos_events" in VENTAS_SOURCE, \
        "No se inserta en la colección roddos_events"


# T8: usa request_with_verify para POST /invoices
def test_usa_request_with_verify_para_invoices():
    assert 'request_with_verify("invoices"' in VENTAS_SOURCE or \
           "request_with_verify('invoices'" in VENTAS_SOURCE, \
        "ventas.py NO usa request_with_verify para POST /invoices — viola ROG-1"
