"""test_s0_consultar_journals.py — S0: consultar_journals en ACTION_MAP + handler sin timeout bug."""

import re
import pytest
from pathlib import Path

AI_CHAT_PATH = Path(__file__).parent.parent / "ai_chat.py"
AI_CHAT_SOURCE = AI_CHAT_PATH.read_text(encoding="utf-8")


def _get_action_map():
    """Importa ACTION_MAP desde ai_chat (sin ejecutar FastAPI)."""
    import sys, types
    # Patch heavy imports para evitar side effects
    for mod in ["anthropic", "motor", "motor.motor_asyncio", "database"]:
        if mod not in sys.modules:
            sys.modules[mod] = types.ModuleType(mod)
    # Extraer ACTION_MAP del source con regex
    match = re.search(r'ACTION_MAP\s*=\s*\{([^}]+)\}', AI_CHAT_SOURCE, re.DOTALL)
    assert match, "ACTION_MAP no encontrado en ai_chat.py"
    block = match.group(1)
    keys = re.findall(r'"(\w+)"\s*:', block)
    return keys


# T1: "consultar_journals" debe estar en ACTION_MAP
def test_consultar_journals_en_action_map():
    keys = _get_action_map()
    assert "consultar_journals" in keys, (
        f"'consultar_journals' no está en ACTION_MAP. Claves encontradas: {keys}"
    )


# T2: el handler NO debe asignar date_afterOrNow ni date_beforeOrNow como params (solo comentarios OK)
def test_handler_no_usa_date_params_que_causan_timeout():
    match = re.search(
        r'(# ACTION-03.*?consultar_journals.*?)(?=# ACTION-0[4-9]|if action_type not in ACTION_MAP)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el bloque del handler consultar_journals"
    bloque = match.group(1)
    # Eliminar líneas de comentario antes de verificar
    lineas_codigo = [l for l in bloque.splitlines() if not l.strip().startswith("#")]
    codigo = "\n".join(lineas_codigo)
    assert "date_afterOrNow" not in codigo, \
        "Handler consultar_journals asigna date_afterOrNow en código → causa TIMEOUT"
    assert "date_beforeOrNow" not in codigo, \
        "Handler consultar_journals asigna date_beforeOrNow en código → causa TIMEOUT"


# T3: el handler filtra localmente cuando se pasa fecha_desde
def test_handler_filtra_localmente_por_fecha():
    match = re.search(
        r'(# ACTION-03.*?consultar_journals.*?)(?=# ACTION-0[4-9]|if action_type not in ACTION_MAP)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el bloque del handler consultar_journals"
    bloque = match.group(1)
    # Debe tener lógica de filtrado local
    assert 'fecha_desde' in bloque, "Handler no filtra localmente por fecha_desde"
    assert 'j.get("date"' in bloque or "j['date']" in bloque or 'j.get(\'date\'' in bloque, \
        "Handler no accede a j['date'] para filtrado local"


# T4: el handler limita a máximo 30 journals
def test_handler_limita_30_journals():
    match = re.search(
        r'(# ACTION-03.*?consultar_journals.*?)(?=# ACTION-0[4-9]|if action_type not in ACTION_MAP)',
        AI_CHAT_SOURCE,
        re.DOTALL,
    )
    assert match, "No se encontró el bloque del handler consultar_journals"
    bloque = match.group(1)
    assert "30" in bloque, "Handler no limita a 30 journals ([:30] o similar no encontrado)"
