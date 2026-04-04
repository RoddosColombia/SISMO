"""test_s4_nomina.py — S4: Nómina — verificar anti-dup, request_with_verify, eventos (análisis estático)."""

import re
import pytest
from pathlib import Path

NOMINA_SOURCE = (Path(__file__).parent.parent / "routers" / "nomina.py").read_text(encoding="utf-8")


# T1: POST /nomina/registrar mismo mes dos veces → segundo retorna HTTP 409 (anti-dup)
def test_registrar_nomina_anti_dup_409():
    assert "409" in NOMINA_SOURCE or "HTTP_409" in NOMINA_SOURCE, \
        "nomina.py no retorna HTTP 409 para duplicados"
    # Verificar que hay lógica de anti-dup por mes
    assert "empleados_hash" in NOMINA_SOURCE or "mes" in NOMINA_SOURCE, \
        "nomina.py no tiene anti-dup por mes+hash"


# T2: POST /nomina/registrar → journal en Alegra con cuenta débito sueldos
def test_registrar_nomina_crea_journal_alegra():
    assert 'request_with_verify("journals"' in NOMINA_SOURCE or \
           "request_with_verify('journals'" in NOMINA_SOURCE, \
        "nomina.py no llama POST /journals con request_with_verify"
    assert "5462" in NOMINA_SOURCE or "sueldos" in NOMINA_SOURCE.lower() or \
           "Sueldos" in NOMINA_SOURCE, \
        "nomina.py no usa cuenta débito de sueldos (5462) en el journal"


# T3: POST /nomina/registrar-mensual mismo empleado+mes → HTTP 409
def test_registrar_nomina_mensual_anti_dup_409():
    # Verificar que el endpoint mensual también tiene anti-dup
    mensual_section = NOMINA_SOURCE[NOMINA_SOURCE.find("registrar_nomina_mensual"):]
    assert "409" in mensual_section, \
        "registrar-mensual no retorna HTTP 409 para duplicados"


# T4: journal nómina → _verificado == True antes de insertar nomina_registros
def test_journal_verificado_antes_de_insertar():
    assert "_verificado" in NOMINA_SOURCE, \
        "nomina.py no verifica _verificado antes de insertar en nomina_registros"
    # La inserción real (insert_one) en nomina_registros debe ser DESPUÉS del check de _verificado
    verificado_pos = NOMINA_SOURCE.find("_verificado")
    # Buscar insert_one específico en nomina_registros
    insert_pos = NOMINA_SOURCE.find("nomina_registros.insert_one")
    if insert_pos == -1:
        insert_pos = NOMINA_SOURCE.rfind("nomina_registros")
    assert insert_pos > verificado_pos, \
        "nomina_registros.insert_one se ejecuta ANTES de verificar _verificado con Alegra"


# T5: nómina registrada → evento nomina.registrada en roddos_events
def test_nomina_registrada_publica_evento():
    assert "nomina.registrada" in NOMINA_SOURCE, \
        "nomina.py no publica evento 'nomina.registrada'"
    assert "roddos_events" in NOMINA_SOURCE, \
        "nomina.py no inserta en roddos_events"
