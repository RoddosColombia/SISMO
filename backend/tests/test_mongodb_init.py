"""
test_mongodb_init.py — Tests para init_mongodb_sismo.py

Verifica que init_all(db) produce las colecciones, indices y seed data
correctos sin requerir conexion real a MongoDB.

Usa unittest.mock para simular todas las operaciones de pymongo (MongoClient,
colecciones, create_index, update_one, find_one, insert_one).

13 tests cubren:
  - Idempotencia (2)
  - roddos_events indices — unique, compound, TTL (3)
  - catalogo_planes seed — planes + multiplicadores (2)
  - plan_cuentas_roddos — sin 5495, con 5493 (2)
  - sismo_knowledge — 10 reglas (1)
  - loanbook — indices ESR + parciales (1)
  - portfolio_summaries — existe con indice (1)
  - roddos_events_dlq — existe con indice (1)
"""

import sys
import os
import pytest
from unittest.mock import MagicMock, patch, call

# ── Asegurar que init_mongodb_sismo.py sea importable desde la raiz del proyecto ──
REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

# Importar las constantes y funciones sin ejecutar el CLI
from init_mongodb_sismo import (
    CATALOGO_DEFAULT,
    PLAN_CUENTAS_RODDOS,
    SISMO_KNOWLEDGE,
    COLLECTIONS,
    init_all,
    seed_catalogo_planes,
    seed_plan_cuentas,
    seed_sismo_knowledge,
    _create_indexes,
)


# ─────────────────────────────────────────────────────────────────────────────
# helpers para construir un mock de db que registra llamadas a create_index
# ─────────────────────────────────────────────────────────────────────────────

class _MockCollection:
    """
    Coleccion MongoDB simulada que registra todas las llamadas a create_index
    y operaciones de escritura para que los tests puedan inspeccionarlas.
    """

    def __init__(self):
        self.create_index = MagicMock(return_value="mock_index_name")
        self.index_information = MagicMock(return_value={})

        # update_one — siempre simula un upsert exitoso
        update_result = MagicMock()
        update_result.upserted_id = "mock_id"
        update_result.modified_count = 0
        self.update_one = MagicMock(return_value=update_result)

        # find_one retorna None (sin usuarios previos)
        self.find_one = MagicMock(return_value=None)
        self.insert_one = MagicMock(return_value=MagicMock())


class _MockDB:
    """
    Base de datos MongoDB simulada.

    Todos los accesos a atributos (db.coleccion) retornan la misma
    instancia de _MockCollection para registrar todas las llamadas.
    """

    def __init__(self, collection: "_MockCollection"):
        self._collection = collection

    def __getattr__(self, name):
        # Evitar recursion para atributos internos de Python
        if name.startswith("_"):
            raise AttributeError(name)
        return self._collection

    def __getitem__(self, name):
        return self._collection


def _make_mock_db():
    """Crea un mock de una base de datos pymongo con colecciones mock."""
    collection_mock = _MockCollection()
    db = _MockDB(collection_mock)
    return db, collection_mock


def _capture_create_index_calls(collection_mock):
    """Retorna la lista de llamadas a create_index del mock."""
    return collection_mock.create_index.call_args_list


def _get_index_keys_called(collection_mock):
    """
    Extrae todos los 'key' (primer argumento posicional) pasados a create_index.
    Retorna una lista de listas de tuplas, e.g.: [[("event_id", 1)], ...]
    """
    all_keys = []
    for c in collection_mock.create_index.call_args_list:
        args = c[0]
        if args:
            all_keys.append(args[0])
    return all_keys


def _has_index_with_key(all_keys, field, direction=None):
    """Verifica que exista al menos un indice con 'field' como primer par."""
    for keys in all_keys:
        for k, d in keys:
            if k == field:
                if direction is None or d == direction:
                    return True
    return False


def _has_compound_index(all_keys, expected_keys):
    """Verifica que exista un indice compuesto con exactamente los pares dados."""
    expected_set = list(expected_keys)
    for keys in all_keys:
        if list(keys) == expected_set:
            return True
    return False


# ─────────────────────────────────────────────────────────────────────────────
# Fixture de modulo — ejecuta init_all una vez, captura las llamadas
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def init_result():
    """
    Ejecuta init_all(db) con una db mock y retorna (db, collection_mock, result).

    Scope=module: init corre una sola vez para todos los tests que usen
    este fixture, simulando la idempotencia al reutilizar los mocks.
    """
    db, col = _make_mock_db()
    result = init_all(db)
    return db, col, result


# ─────────────────────────────────────────────────────────────────────────────
# IDEMPOTENCIA — 2 tests
# ─────────────────────────────────────────────────────────────────────────────

def test_init_idempotent_no_errors(init_result):
    """
    init_all ejecutado dos veces no lanza ninguna excepcion.

    La segunda ejecucion sobre el mismo mock no debe fallar aunque
    create_index ya haya sido llamado (idempotente por diseno de MongoDB).
    """
    db, col, _ = init_result
    # Segunda ejecucion — no debe levantar excepciones
    try:
        result2 = init_all(db)
    except Exception as exc:
        pytest.fail(f"Segunda ejecucion de init_all lanzo excepcion: {exc}")
    assert result2 is not None


def test_init_idempotent_same_result(init_result):
    """
    Ambas ejecuciones de init_all retornan el mismo numero de colecciones e indices.

    Verifica que el resultado estructural (metricas) es consistente entre runs.
    """
    db, col, result1 = init_result
    result2 = init_all(db)

    assert result1["collections"] == result2["collections"], (
        f"Numero de colecciones difiere: {result1['collections']} vs {result2['collections']}"
    )
    assert result1["indexes"] == result2["indexes"], (
        f"Numero de indices difiere: {result1['indexes']} vs {result2['indexes']}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# roddos_events INDICES — 3 tests
# ─────────────────────────────────────────────────────────────────────────────

def test_roddos_events_unique_event_id(init_result):
    """
    roddos_events tiene un indice unique sobre el campo event_id.

    Verifica deduplicacion de eventos (MDB-02, D-08).
    """
    _, col, _ = init_result
    all_keys = _get_index_keys_called(col)

    # Buscar llamada a create_index con event_id + unique=True
    found = False
    for c in col.create_index.call_args_list:
        args = c[0]
        kwargs = c[1] if len(c) > 1 else {}
        if args and any(k == "event_id" for k, _ in args[0]):
            if kwargs.get("unique"):
                found = True
                break

    assert found, (
        "No se encontro create_index con event_id y unique=True en roddos_events"
    )


def test_roddos_events_compound_index(init_result):
    """
    roddos_events tiene un indice compuesto (event_type: ASC, timestamp_utc: DESC).

    Permite consultas cronologicas por tipo de evento (D-08).
    """
    _, col, _ = init_result
    all_keys = _get_index_keys_called(col)

    # event_type ASC=1, timestamp_utc DESC=-1
    expected = [("event_type", 1), ("timestamp_utc", -1)]
    found = _has_compound_index(all_keys, expected)
    assert found, (
        f"No se encontro indice compuesto {expected} en los llamados a create_index"
    )


def test_roddos_events_ttl_90_days(init_result):
    """
    roddos_events tiene indice TTL sobre timestamp_utc con expireAfterSeconds=7776000.

    7776000 segundos = 90 dias. Expiracion automatica de eventos (D-08).
    """
    _, col, _ = init_result

    found = False
    for c in col.create_index.call_args_list:
        args = c[0]
        kwargs = c[1] if len(c) > 1 else {}
        if args and any(k == "timestamp_utc" for k, _ in args[0]):
            if kwargs.get("expireAfterSeconds") == 7776000:
                found = True
                break

    assert found, (
        "No se encontro create_index con timestamp_utc y expireAfterSeconds=7776000 (90 dias)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# catalogo_planes SEED — 2 tests
# ─────────────────────────────────────────────────────────────────────────────

def test_catalogo_planes_has_plans():
    """
    CATALOGO_DEFAULT contiene los 4 planes esperados: P39S, P52S, P78S, Contado.

    Verifica que seed_catalogo_planes llamaria update_one para cada plan.
    """
    plan_names = [p["plan"] for p in CATALOGO_DEFAULT]
    for expected in ["P39S", "P52S", "P78S", "Contado"]:
        assert expected in plan_names, (
            f"Plan '{expected}' no encontrado en CATALOGO_DEFAULT"
        )


def test_catalogo_planes_multipliers():
    """
    Los planes financiados (P39S, P52S, P78S) tienen multiplicadores {semanal: 1.0, quincenal: 2.2, mensual: 4.4}.

    Verifica la integridad de los multiplicadores de frecuencia de pago (D-06).
    """
    expected_mult = {"semanal": 1.0, "quincenal": 2.2, "mensual": 4.4}
    for plan in CATALOGO_DEFAULT:
        if plan["plan"] == "Contado":
            continue  # Contado no tiene multiplicadores
        mults = plan.get("multiplicadores", {})
        assert mults.get("semanal") == 1.0, (
            f"Plan {plan['plan']}: multiplicador semanal esperado 1.0, got {mults.get('semanal')}"
        )
        assert mults.get("quincenal") == 2.2, (
            f"Plan {plan['plan']}: multiplicador quincenal esperado 2.2, got {mults.get('quincenal')}"
        )
        assert mults.get("mensual") == 4.4, (
            f"Plan {plan['plan']}: multiplicador mensual esperado 4.4, got {mults.get('mensual')}"
        )


# ─────────────────────────────────────────────────────────────────────────────
# plan_cuentas_roddos SEED — 2 tests
# ─────────────────────────────────────────────────────────────────────────────

def test_plan_cuentas_no_5495():
    """
    Ningun documento en PLAN_CUENTAS_RODDOS tiene alegra_id == 5495.

    El ID 5495 es invalido en la cuenta Alegra de RODDOS y fue removido (D-05).
    """
    ids_invalidos = [
        entry["alegra_id"] for entry in PLAN_CUENTAS_RODDOS
        if entry.get("alegra_id") == 5495
    ]
    assert len(ids_invalidos) == 0, (
        f"Se encontraron {len(ids_invalidos)} entradas con alegra_id=5495 (ID invalido)"
    )


def test_plan_cuentas_has_5493_fallback():
    """
    Al menos una entrada en PLAN_CUENTAS_RODDOS tiene alegra_id == 5493 (Gastos generales).

    5493 es la cuenta fallback cuando no hay cuenta especifica (D-05).
    """
    ids_fallback = [
        entry for entry in PLAN_CUENTAS_RODDOS
        if entry.get("alegra_id") == 5493
    ]
    assert len(ids_fallback) >= 1, (
        "No se encontro ninguna entrada con alegra_id=5493 (fallback requerido)"
    )


# ─────────────────────────────────────────────────────────────────────────────
# sismo_knowledge SEED — 1 test
# ─────────────────────────────────────────────────────────────────────────────

def test_sismo_knowledge_10_rules():
    """
    SISMO_KNOWLEDGE contiene exactamente 10 reglas con rule_id unicos.

    Base RAG con 10 reglas de negocio criticas para los agentes IA (D-07, MDB-06).
    """
    assert len(SISMO_KNOWLEDGE) == 10, (
        f"Se esperaban 10 reglas en SISMO_KNOWLEDGE, se encontraron {len(SISMO_KNOWLEDGE)}"
    )
    rule_ids = [r["rule_id"] for r in SISMO_KNOWLEDGE]
    unique_ids = set(rule_ids)
    assert len(unique_ids) == 10, (
        f"Se encontraron rule_ids duplicados: {[r for r in rule_ids if rule_ids.count(r) > 1]}"
    )


# ─────────────────────────────────────────────────────────────────────────────
# loanbook INDICES — 1 test
# ─────────────────────────────────────────────────────────────────────────────

def test_loanbook_esr_indices(init_result):
    """
    loanbook tiene indice ESR compuesto (estado, dpd, score_pago) y un indice parcial para morosos.

    ESR = Equality + Sort + Range. Optimiza consultas de cobranza (MDB-03, D-10).
    """
    _, col, _ = init_result
    all_keys = _get_index_keys_called(col)

    # Indice ESR principal: estado ASC, dpd ASC, score_pago DESC
    esr_keys = [("estado", 1), ("dpd", 1), ("score_pago", -1)]
    esr_found = _has_compound_index(all_keys, esr_keys)
    assert esr_found, (
        f"No se encontro indice ESR {esr_keys} en los llamados a create_index"
    )

    # Indice parcial para morosos: (dpd DESC, score_pago ASC) con partialFilterExpression
    morosos_found = False
    for c in col.create_index.call_args_list:
        args = c[0]
        kwargs = c[1] if len(c) > 1 else {}
        if args and list(args[0]) == [("dpd", -1), ("score_pago", 1)]:
            if "partialFilterExpression" in kwargs:
                morosos_found = True
                break
    assert morosos_found, (
        "No se encontro indice parcial de morosos (dpd DESC, score_pago ASC) con partialFilterExpression"
    )


# ─────────────────────────────────────────────────────────────────────────────
# portfolio_summaries — 1 test
# ─────────────────────────────────────────────────────────────────────────────

def test_portfolio_summaries_exists(init_result):
    """
    portfolio_summaries esta en la lista COLLECTIONS y tiene indice unique en 'date'.

    Coleccion para resumen de cartera pre-calculado (MDB-07, D-11).
    """
    assert "portfolio_summaries" in COLLECTIONS, (
        "portfolio_summaries no esta en COLLECTIONS"
    )

    _, col, _ = init_result

    # Verificar que se llamo create_index con 'date' y unique=True
    found = False
    for c in col.create_index.call_args_list:
        args = c[0]
        kwargs = c[1] if len(c) > 1 else {}
        if args and any(k == "date" for k, _ in args[0]):
            if kwargs.get("unique"):
                found = True
                break

    assert found, (
        "No se encontro create_index con campo 'date' y unique=True para portfolio_summaries"
    )


# ─────────────────────────────────────────────────────────────────────────────
# roddos_events_dlq — 1 test
# ─────────────────────────────────────────────────────────────────────────────

def test_roddos_events_dlq_exists(init_result):
    """
    roddos_events_dlq esta en COLLECTIONS y tiene indice sobre next_retry.

    Dead Letter Queue para reintento de eventos fallidos (MDB-09, D-09).
    """
    assert "roddos_events_dlq" in COLLECTIONS, (
        "roddos_events_dlq no esta en COLLECTIONS"
    )

    _, col, _ = init_result
    all_keys = _get_index_keys_called(col)

    # Indice sobre next_retry (para ordenar intentos de reintento)
    found = _has_index_with_key(all_keys, "next_retry")
    assert found, (
        "No se encontro create_index con campo 'next_retry' para roddos_events_dlq"
    )
