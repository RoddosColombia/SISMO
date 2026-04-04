"""test_s3_ingresos_cuotas.py — S3: registrar pago cartera + journal en Alegra (análisis estático)."""

import re
import pytest
from pathlib import Path

CARTERA_SOURCE = (Path(__file__).parent.parent / "routers" / "cartera.py").read_text(encoding="utf-8")


# T1: registrar pago → POST /journals en Alegra
def test_registrar_pago_llama_post_journals():
    assert 'request_with_verify("journals"' in CARTERA_SOURCE or \
           "request_with_verify('journals'" in CARTERA_SOURCE, \
        "cartera.py no llama POST /journals en Alegra al registrar pago"


# T2: journal usa request_with_verify
def test_journal_usa_request_with_verify():
    assert "request_with_verify" in CARTERA_SOURCE, \
        "cartera.py no usa request_with_verify — viola ROG-1"
    # Verificar que NO usa service.request() directo para journals
    lines = [l for l in CARTERA_SOURCE.splitlines() if not l.strip().startswith("#")]
    raw_journal_posts = [l for l in lines
                         if "service.request(" in l and '"journals"' in l and '"POST"' in l]
    assert len(raw_journal_posts) == 0, \
        f"cartera.py tiene service.request() directo a /journals: {raw_journal_posts}"


# T3: cuota pagada → loanbook.cuotas[N].estado == "pagada" con journal_alegra_id
def test_cuota_se_marca_pagada_con_journal_id():
    assert '"pagada"' in CARTERA_SOURCE or "'pagada'" in CARTERA_SOURCE, \
        "cartera.py no marca la cuota como 'pagada'"
    assert "alegra_journal_id" in CARTERA_SOURCE, \
        "cartera.py no guarda el alegra_journal_id en la cuota"
    # El estado "pagada" debe asignarse DESPUÉS del request_with_verify
    verify_pos = CARTERA_SOURCE.find("request_with_verify")
    pagada_pos = CARTERA_SOURCE.find('"pagada"')
    assert pagada_pos > verify_pos, \
        "La cuota se marca 'pagada' ANTES de verificar con Alegra — debe ser DESPUÉS"


# T4: cuota pagada → evento pago.cuota.registrado en roddos_events
def test_evento_pago_cuota_registrado():
    assert "pago.cuota.registrado" in CARTERA_SOURCE, \
        "cartera.py no publica evento 'pago.cuota.registrado'"
    assert "roddos_events" in CARTERA_SOURCE, \
        "cartera.py no inserta en roddos_events"


# T5: cuota pagada → cfo_cache invalidado
def test_cfo_cache_invalidado():
    assert "invalidar_cache_cfo" in CARTERA_SOURCE, \
        "cartera.py no invalida el CFO cache después de registrar pago"


# T6: Alegra falla → cuota NO queda en "pagada" (HTTPException previene la asignación)
def test_alegra_falla_cuota_no_se_marca_pagada():
    # La asignación cuotas[idx]["estado"] = "pagada" debe ocurrir DESPUÉS de verificar _verificado
    # Buscamos la asignación exacta, no la query filter
    assign_pagada_pos = CARTERA_SOURCE.find('["estado"] = "pagada"')
    assert assign_pagada_pos > 0, 'No se encontró la asignación cuotas[idx]["estado"] = "pagada"'
    # El check de _verificado debe estar antes
    verificado_check = CARTERA_SOURCE.find('journal_response.get("_verificado")')
    assert verificado_check > 0, "No existe check de _verificado antes de marcar cuota pagada"
    assert assign_pagada_pos > verificado_check, \
        "La cuota se marcaría 'pagada' sin verificar el journal en Alegra"


# T7: monto journal == monto cuota
def test_monto_journal_igual_monto_cuota():
    assert "monto_pago" in CARTERA_SOURCE, \
        "cartera.py no usa monto_pago en el journal"
    assert "debit" in CARTERA_SOURCE or "credit" in CARTERA_SOURCE, \
        "El journal en cartera.py no tiene entradas débito/crédito"
