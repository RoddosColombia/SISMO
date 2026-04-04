"""test_s1_chat_transaccional.py — S1: crear_causacion usa request_with_verify + retenciones."""

import re
import pytest
from pathlib import Path

AI_CHAT_SOURCE = (Path(__file__).parent.parent / "ai_chat.py").read_text(encoding="utf-8")


# T1: crear_causacion usa request_with_verify, NO service.request() directo para /journals POST
def test_crear_causacion_usa_request_with_verify():
    # Extraer el bloque del handler crear_causacion (F2)
    match = re.search(
        r'(if action_type == "crear_causacion".*?)(?=# ── Special case: crear_factura_venta)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el handler crear_causacion (F2)"
    bloque = match.group(1)
    assert "request_with_verify" in bloque, \
        "crear_causacion NO usa request_with_verify — viola ROG-1"
    # Verificar que NO llama service.request("journals", "POST" directamente en el bloque
    # (el service.request genérico de abajo aplica a otros action_types)
    lines = [l for l in bloque.splitlines() if not l.strip().startswith("#")]
    raw_journal_post = [l for l in lines
                        if 'service.request(' in l and '"journals"' in l and '"POST"' in l]
    assert len(raw_journal_post) == 0, \
        f"crear_causacion tiene service.request() directo a /journals: {raw_journal_post}"


# T2: arriendo $3.614.953 → cuenta 5480 + ReteFuente 3.5% calculado
def test_arriendo_retiene_3_5_pct():
    from services.accounting_engine import calcular_retenciones
    ret = calcular_retenciones(
        tipo_proveedor="PN",
        tipo_gasto="arrendamiento",
        monto_bruto=3_614_953,
        es_autoretenedor=False,
        aplica_iva=False,
        aplica_reteica=False,
    )
    assert ret["retefuente_pct"] == pytest.approx(0.035, rel=1e-3), \
        f"Arriendo debe tener ReteFuente 3.5%, obtenido: {ret['retefuente_pct']}"
    assert ret["retefuente_valor"] == pytest.approx(3_614_953 * 0.035, rel=1e-3)


# T3: honorarios persona natural $800.000 → ReteFuente 10%
def test_honorarios_pn_retiene_10_pct():
    from services.accounting_engine import calcular_retenciones
    ret = calcular_retenciones(
        tipo_proveedor="PN",
        tipo_gasto="honorarios",
        monto_bruto=800_000,
        es_autoretenedor=False,
        aplica_iva=False,
        aplica_reteica=False,
    )
    assert ret["retefuente_pct"] == pytest.approx(0.10, rel=1e-3), \
        f"Honorarios PN debe tener ReteFuente 10%, obtenido: {ret['retefuente_pct']}"


# T4: Alegra HTTP 200 → respuesta incluye journal_id (campo "id")
def test_crear_causacion_retorna_journal_id():
    # Verificar que el handler retorna el campo 'id' en éxito
    match = re.search(
        r'(if action_type == "crear_causacion".*?)(?=# ── Special case: crear_factura_venta)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el handler crear_causacion"
    bloque = match.group(1)
    assert '"id"' in bloque or "'id'" in bloque, \
        "Handler crear_causacion no retorna campo 'id' en la respuesta de éxito"
    assert "alegra_id" in bloque or "journal_id" in bloque, \
        "Handler crear_causacion no extrae el ID real de Alegra"


# T5: Alegra error → respuesta en español, no stacktrace
def test_crear_causacion_error_en_espanol():
    match = re.search(
        r'(if action_type == "crear_causacion".*?)(?=# ── Special case: crear_factura_venta)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el handler crear_causacion"
    bloque = match.group(1)
    # Debe tener manejo de excepción con mensaje en español
    assert "Error al crear asiento" in bloque or "error al crear" in bloque.lower() or \
           "falló" in bloque or "fallo" in bloque, \
        "Handler crear_causacion no tiene mensaje de error en español para el usuario"
