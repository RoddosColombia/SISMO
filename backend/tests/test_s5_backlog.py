"""test_s5_backlog.py — S5: Backlog de movimientos — análisis estático del router."""

import pytest
from pathlib import Path

SOURCE = (Path(__file__).parent.parent / "routers" / "contabilidad_pendientes.py").read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────────────────────
# T1: BacklogMovimientoRequest tiene campos banco, extracto, fecha, monto, tipo
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_request_campos_correctos():
    assert "class BacklogMovimientoRequest" in SOURCE, \
        "BacklogMovimientoRequest no definida en contabilidad_pendientes.py"
    assert "banco: str" in SOURCE, "BacklogMovimientoRequest no tiene campo banco"
    assert "extracto: str" in SOURCE, "BacklogMovimientoRequest no tiene campo extracto"
    assert "fecha: str" in SOURCE, "BacklogMovimientoRequest no tiene campo fecha"
    assert "monto: float" in SOURCE, "BacklogMovimientoRequest no tiene campo monto"
    assert "tipo: str" in SOURCE, "BacklogMovimientoRequest no tiene campo tipo"


# ──────────────────────────────────────────────────────────────────────────────
# T2: POST /backlog/crear — anti-dup hash MD5 → HTTP 409
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_crear_anti_dup_409():
    assert "409" in SOURCE, "backlog/crear no retorna HTTP 409 para duplicados"
    assert "hashlib" in SOURCE, "contabilidad_pendientes.py no importa hashlib"
    assert "backlog_hash" in SOURCE, "no hay campo backlog_hash para anti-dup"
    # hash se calcula antes del check
    hash_pos = SOURCE.find("backlog_hash")
    dup_check = SOURCE.find("409")
    assert hash_pos < dup_check, "hash debe calcularse antes de retornar 409"


# ──────────────────────────────────────────────────────────────────────────────
# T3: GET /backlog/listado?estado=pendiente → filtra por estado
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_listado_filtra_por_estado():
    assert "/backlog/listado" in SOURCE or "backlog/listado" in SOURCE, \
        "endpoint /backlog/listado no existe"
    # Verificar que el query dict usa "estado"
    listado_section = SOURCE[SOURCE.find("backlog_listado"):]
    assert '"estado"' in listado_section or "'estado'" in listado_section, \
        "backlog_listado no filtra por estado"


# ──────────────────────────────────────────────────────────────────────────────
# T4: GET /backlog/listado?banco=bbva → filtra por banco
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_listado_filtra_por_banco():
    listado_section = SOURCE[SOURCE.find("backlog_listado"):]
    assert '"banco"' in listado_section or "'banco'" in listado_section, \
        "backlog_listado no filtra por banco"


# ──────────────────────────────────────────────────────────────────────────────
# T5: PATCH /{id}/causar → usa request_with_verify para crear journal en Alegra
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_causar_usa_request_with_verify():
    assert "backlog_causar" in SOURCE, "función backlog_causar no existe"
    causar_section = SOURCE[SOURCE.find("backlog_causar"):]
    assert 'request_with_verify("journals"' in causar_section or \
           "request_with_verify('journals'" in causar_section, \
        "backlog_causar no usa request_with_verify para journals"
    assert "AlegraService" in causar_section, \
        "backlog_causar no usa AlegraService"


# ──────────────────────────────────────────────────────────────────────────────
# T6: PATCH /{id}/causar → estado="causado", journal_alegra_id no null
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_causar_actualiza_estado():
    causar_section = SOURCE[SOURCE.find("backlog_causar"):]
    assert '"causado"' in causar_section, \
        "backlog_causar no establece estado 'causado'"
    assert "journal_alegra_id" in causar_section, \
        "backlog_causar no guarda journal_alegra_id"
    # La asignación del estado debe ser DESPUÉS de request_with_verify
    verify_pos = causar_section.find("request_with_verify")
    causado_pos = causar_section.find('"causado"', verify_pos)
    assert causado_pos > verify_pos, \
        "estado 'causado' debe asignarse DESPUÉS de request_with_verify"


# ──────────────────────────────────────────────────────────────────────────────
# T7: PATCH /{id}/descartar → estado="descartado"
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_descartar_cambia_estado():
    assert "backlog_descartar" in SOURCE, "función backlog_descartar no existe"
    descartar_section = SOURCE[SOURCE.find("backlog_descartar"):]
    assert '"descartado"' in descartar_section, \
        "backlog_descartar no establece estado 'descartado'"
    # Verificar que usa update_one con $set
    assert "$set" in descartar_section, \
        "backlog_descartar no usa $set en update_one"


# ──────────────────────────────────────────────────────────────────────────────
# T8: GET /backlog/stats → total_pendientes, total_causados, total_descartados, por_banco
# ──────────────────────────────────────────────────────────────────────────────

def test_backlog_stats_estructura():
    assert "backlog_stats" in SOURCE, "función backlog_stats no existe"
    stats_section = SOURCE[SOURCE.find("backlog_stats"):]
    assert "total_pendientes" in stats_section, \
        "backlog_stats no retorna total_pendientes"
    assert "total_causados" in stats_section, \
        "backlog_stats no retorna total_causados"
    assert "total_descartados" in stats_section, \
        "backlog_stats no retorna total_descartados"
    assert "por_banco" in stats_section, \
        "backlog_stats no retorna por_banco"
    # Verificar que cuenta los 4 bancos
    assert "bbva" in stats_section, "backlog_stats no incluye bbva en por_banco"
    assert "bancolombia" in stats_section, "backlog_stats no incluye bancolombia"
