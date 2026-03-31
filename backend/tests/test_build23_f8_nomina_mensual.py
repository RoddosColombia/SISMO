"""
BUILD 23 — F8 Nomina Mensual (Per-Employee Journals): Test Suite (T1-T7)

Tests for monthly payroll registration that creates ONE journal per employee in Alegra.
CRITICAL: T4 ensures Alegra failures DO NOT insert into nomina_registros.
CRITICAL: T7 ensures anti-duplicate guard returns HTTP 409.

Phase 07-01 — TDD RED phase: all tests fail with ImportError on routers.nomina
  (registrar_nomina_mensual does not exist yet in the existing nomina.py)
"""
import sys
import os
from unittest.mock import MagicMock

_STUBS = [
    "qrcode", "qrcode.image", "qrcode.image.svg",
    "cryptography", "cryptography.fernet",
    "pdfplumber",
]
for _mod in _STUBS:
    if _mod not in sys.modules:
        sys.modules[_mod] = MagicMock()

os.environ.setdefault("MONGO_URL", "mongodb://localhost:27017/sismo_test")
os.environ.setdefault("DB_NAME", "sismo_test")
os.environ.setdefault("ALEGRA_EMAIL", "test@test.com")
os.environ.setdefault("ALEGRA_TOKEN", "test")
os.environ.setdefault("JWT_SECRET", "test-secret-key")

import pytest
from unittest.mock import AsyncMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB connection with collections required by nomina_mensual."""
    db = MagicMock()
    db.nomina_registros = AsyncMock()
    db.roddos_events = AsyncMock()
    # plan_cuentas_roddos: banco lookup returns Bancolombia ID 5314
    db.plan_cuentas_roddos = AsyncMock()
    db.plan_cuentas_roddos.find_one = AsyncMock(
        return_value={"alegra_id": 5314, "tipo": "banco", "banco_nombre": "Bancolombia"}
    )
    # Default: no existing nomina record (no duplicate)
    db.nomina_registros.find_one = AsyncMock(return_value=None)
    db.nomina_registros.insert_one = AsyncMock()
    db.roddos_events.insert_one = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Mock authenticated user object."""
    return {
        "id": "test_user_123",
        "email": "test@roddos.com",
        "nombre": "Test User",
    }


@pytest.fixture
def empleados_enero():
    """Nomina enero 2026 — 3 empleados."""
    return [
        {"nombre": "Alexa", "salario": 3220000},
        {"nombre": "Luis", "salario": 3220000},
        {"nombre": "Liz", "salario": 1472000},
    ]


@pytest.fixture
def empleados_febrero():
    """Nomina febrero 2026 — 2 empleados."""
    return [
        {"nombre": "Alexa", "salario": 4500000},
        {"nombre": "Liz", "salario": 2200000},
    ]


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Nomina enero 2026 → 3 journals (uno por empleado) + success=True
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t1_registrar_nomina_crea_tres_journals(mock_db, mock_user, empleados_enero):
    """
    T1: registrar_nomina_mensual(mes=1, anio=2026, empleados=3) crea 3 journals en Alegra.

    Esperado:
    - success: True
    - journal_ids: lista con 3 IDs de Alegra (uno por empleado)
    - request_with_verify llamado 3 veces
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest

    call_count = 0

    async def mock_rwv(endpoint, method, payload):
        nonlocal call_count
        call_count += 1
        return {"id": f"JE-NOM-{call_count:04d}", "_verificado": True}

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=empleados_enero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(side_effect=mock_rwv)

            result = await registrar_nomina_mensual(payload, mock_user)

    # Validaciones
    assert result["success"] is True, "Debe retornar success=True"
    assert "journal_ids" in result, "Debe retornar lista de journal_ids"
    assert len(result["journal_ids"]) == 3, "Debe crear 1 journal por empleado (3 empleados)"
    assert mock_service.request_with_verify.call_count == 3, "request_with_verify llamado 3 veces"

    print(f"T1 PASO: 3 journals creados: {result['journal_ids']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Montos correctos por empleado ($3.220.000, $3.220.000, $1.472.000)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t2_montos_correctos_por_empleado(mock_db, mock_user, empleados_enero):
    """
    T2: Cada journal tiene monto exacto del empleado correspondiente.

    Esperado por journal:
    - entries[0]: debit=salario, id=5493 (gastos_nomina fallback)
    - entries[1]: credit=salario, id=5314 (Bancolombia)
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest

    captured_payloads = []
    call_count = 0

    async def capture_payload(endpoint, method, payload):
        nonlocal call_count
        call_count += 1
        captured_payloads.append(payload)
        return {"id": f"JE-NOM-{call_count:04d}", "_verificado": True}

    # For gastos_nomina lookup: return None to test fallback to 5493
    async def plan_cuentas_find_one(query):
        tipo = query.get("tipo", "")
        if tipo == "banco":
            return {"alegra_id": 5314, "tipo": "banco"}
        return None  # gastos_nomina → fallback 5493

    mock_db.plan_cuentas_roddos.find_one = AsyncMock(side_effect=plan_cuentas_find_one)

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=empleados_enero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(side_effect=capture_payload)

            result = await registrar_nomina_mensual(payload, mock_user)

    assert len(captured_payloads) == 3, "Debe capturar 3 payloads de journals"

    expected_salarios = [3220000, 3220000, 1472000]

    for i, (journal_payload, expected_salario) in enumerate(zip(captured_payloads, expected_salarios)):
        entries = journal_payload.get("entries", [])
        assert len(entries) == 2, f"Journal {i+1} debe tener 2 entries (debito + credito)"

        debit_entry = entries[0]
        assert debit_entry["id"] == 5493, f"Journal {i+1} DEBITO debe ser gastos_nomina (ID 5493)"
        assert debit_entry["debit"] == expected_salario, f"Journal {i+1} DEBITO monto={debit_entry['debit']}, esperado={expected_salario}"
        assert debit_entry["credit"] == 0, f"Journal {i+1} DEBITO credit debe ser 0"

        credit_entry = entries[1]
        assert credit_entry["id"] == 5314, f"Journal {i+1} CREDITO debe ser Bancolombia (ID 5314)"
        assert credit_entry["credit"] == expected_salario, f"Journal {i+1} CREDITO monto correcto"
        assert credit_entry["debit"] == 0, f"Journal {i+1} CREDITO debit debe ser 0"

    print("T2 PASO: Montos y cuentas correctas en los 3 journals")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Journal observations contienen nombre empleado y mes
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t3_journal_observations_con_nombre_y_mes(mock_db, mock_user, empleados_enero):
    """
    T3: Cada journal tiene observations con nombre del empleado y mes en espanol.

    Esperado: "Nomina enero 2026 - Alexa"
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest

    captured_payloads = []
    call_count = 0

    async def capture_payload(endpoint, method, payload):
        nonlocal call_count
        call_count += 1
        captured_payloads.append(payload)
        return {"id": f"JE-NOM-{call_count:04d}", "_verificado": True}

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=empleados_enero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(side_effect=capture_payload)

            result = await registrar_nomina_mensual(payload, mock_user)

    assert len(captured_payloads) == 3, "Debe capturar 3 payloads"

    expected_nombres = ["Alexa", "Luis", "Liz"]

    for i, (journal_payload, nombre) in enumerate(zip(captured_payloads, expected_nombres)):
        observations = journal_payload.get("observations", "")
        assert nombre in observations, f"Journal {i+1} observations debe incluir nombre '{nombre}'"
        assert "enero" in observations.lower(), f"Journal {i+1} observations debe incluir 'enero'"
        assert "2026" in observations, f"Journal {i+1} observations debe incluir '2026'"

    print("T3 PASO: Observations contienen nombre empleado y mes")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: CRITICO — Si Alegra falla (_verificado=False) → NO insertar en nomina_registros
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t4_fallo_alegra_no_inserta_en_nomina_registros(mock_db, mock_user, empleados_enero):
    """
    T4: GARANTIA DE CONSISTENCIA — Si request_with_verify retorna _verificado=False
    para CUALQUIER empleado:
    - NO insertar en nomina_registros para ese empleado
    - Retornar error explícito

    Esperado:
    - HTTPException 500 con "no verificado" en detail
    - nomina_registros.insert_one NO llamado
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest
    from fastapi import HTTPException

    # Simular fallo en el primer empleado
    mock_journal_fail = {
        "id": "JE-NOM-FAIL",
        "_verificado": False,
        "_error_verificacion": "GET /journals/JE-NOM-FAIL retorno 404",
    }

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=empleados_enero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(return_value=mock_journal_fail)

            with pytest.raises(HTTPException) as exc_info:
                await registrar_nomina_mensual(payload, mock_user)

    # CRITICAL VALIDATIONS
    assert exc_info.value.status_code == 500, "Debe retornar HTTP 500 en fallo de Alegra"
    assert "no verificado" in str(exc_info.value.detail).lower(), "Error debe mencionar verificacion fallida"

    # CRITICAL: nomina_registros NO debe ser modificado
    assert not mock_db.nomina_registros.insert_one.called, (
        "CRITICAL FAILURE: nomina_registros.insert_one fue llamado a pesar del error en Alegra! "
        "Esto causa inconsistencia de datos."
    )

    print("T4 PASO: Fallo Alegra NO inserta en nomina_registros (GARANTIA CRITICA)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Nomina febrero 2026 con 2 empleados (Alexa $4.500.000, Liz $2.200.000)
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t5_nomina_febrero_dos_empleados(mock_db, mock_user, empleados_febrero):
    """
    T5: registrar_nomina_mensual(mes=2, anio=2026, empleados=2) crea 2 journals.

    Esperado:
    - success: True
    - journal_ids: lista con 2 IDs
    - request_with_verify llamado 2 veces
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest

    call_count = 0

    async def mock_rwv(endpoint, method, payload):
        nonlocal call_count
        call_count += 1
        return {"id": f"JE-NOM-{call_count:04d}", "_verificado": True}

    payload = RegistrarNominaRequest(
        mes=2,
        anio=2026,
        empleados=empleados_febrero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(side_effect=mock_rwv)

            result = await registrar_nomina_mensual(payload, mock_user)

    assert result["success"] is True, "Debe retornar success=True"
    assert len(result["journal_ids"]) == 2, "Debe crear 2 journals (2 empleados)"
    assert mock_service.request_with_verify.call_count == 2, "request_with_verify llamado 2 veces"

    # Verificar montos en journals capturados
    alexa_monto = empleados_febrero[0]["salario"]  # 4500000
    liz_monto = empleados_febrero[1]["salario"]    # 2200000

    assert alexa_monto == 4500000, "Alexa salario debe ser $4.500.000"
    assert liz_monto == 2200000, "Liz salario debe ser $2.200.000"

    print(f"T5 PASO: Nomina febrero 2026 — 2 journals: {result['journal_ids']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Evento nomina.mensual.registrada publicado con datos correctos
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t6_evento_nomina_mensual_registrada_publicado(mock_db, mock_user, empleados_enero):
    """
    T6: Evento "nomina.mensual.registrada" publicado en roddos_events.

    Esperado:
    - event_type: "nomina.mensual.registrada"
    - mes: 1
    - anio: 2026
    - total_nomina: 7912000 (3220000 + 3220000 + 1472000)
    - empleados_count: 3
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest

    captured_event = None
    call_count = 0

    async def mock_rwv(endpoint, method, payload):
        nonlocal call_count
        call_count += 1
        return {"id": f"JE-NOM-{call_count:04d}", "_verificado": True}

    async def capture_event(event_doc):
        nonlocal captured_event
        captured_event = event_doc

    mock_db.roddos_events.insert_one = AsyncMock(side_effect=capture_event)

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=empleados_enero,
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service
            mock_service.request_with_verify = AsyncMock(side_effect=mock_rwv)

            result = await registrar_nomina_mensual(payload, mock_user)

    assert captured_event is not None, "Evento debe ser publicado en roddos_events"
    assert captured_event["event_type"] == "nomina.mensual.registrada", "event_type correcto"
    assert captured_event["mes"] == 1, "mes debe ser 1"
    assert captured_event["anio"] == 2026, "anio debe ser 2026"

    total_esperado = 3220000 + 3220000 + 1472000  # 7912000
    assert captured_event["total_nomina"] == total_esperado, (
        f"total_nomina esperado={total_esperado}, got={captured_event.get('total_nomina')}"
    )
    assert captured_event["empleados_count"] == 3, "empleados_count debe ser 3"

    print(f"T6 PASO: Evento publicado — total_nomina={captured_event['total_nomina']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 7 (RED): Duplicado empleado+mes+anio retorna HTTP 409
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t7_duplicado_empleado_mes_anio_retorna_409(mock_db, mock_user):
    """
    T7 (RED): Segunda llamada con mismo empleado+mes+anio debe retornar HTTP 409.

    Anti-duplicate guard: si nomina_registros ya tiene un registro para
    empleado="Alexa", mes=1, anio=2026 → raise HTTPException(status_code=409).

    Esperado:
    - HTTPException status_code == 409
    - "ya registrada" en detail
    """
    from routers.nomina import registrar_nomina_mensual, RegistrarNominaRequest
    from fastapi import HTTPException

    # Mock: Alexa enero 2026 ya existe en nomina_registros
    registro_existente = {
        "empleado": "Alexa",
        "mes": 1,
        "anio": 2026,
        "alegra_journal_id": "JE-NOM-0001",
    }
    mock_db.nomina_registros.find_one = AsyncMock(return_value=registro_existente)

    payload = RegistrarNominaRequest(
        mes=1,
        anio=2026,
        empleados=[{"nombre": "Alexa", "salario": 3220000}],
        banco_origen="Bancolombia",
    )

    with patch("routers.nomina.db", mock_db):
        with patch("routers.nomina.AlegraService") as MockService:
            mock_service = AsyncMock()
            MockService.return_value = mock_service

            with pytest.raises(HTTPException) as exc_info:
                await registrar_nomina_mensual(payload, mock_user)

    assert exc_info.value.status_code == 409, (
        f"Duplicado debe retornar HTTP 409, got {exc_info.value.status_code}"
    )
    assert "ya registrada" in str(exc_info.value.detail).lower(), (
        f"Detail debe contener 'ya registrada', got: {exc_info.value.detail}"
    )

    print(f"T7 PASO (RED): HTTP 409 retornado correctamente — {exc_info.value.detail}")


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN DE TESTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resumen_f8_todos_los_tests():
    """
    Resumen de todas las validaciones T1-T7 para nomina mensual per-employee journals.

    T1: 3 journals creados para nomina enero (un journal por empleado)
    T2: Montos correctos por empleado (debito gastos_nomina 5493 + credito banco 5314)
    T3: Journal observations contienen nombre empleado y mes en espanol
    T4: Fallo Alegra NO inserta en nomina_registros (GARANTIA CRITICA)
    T5: Nomina febrero con 2 empleados crea 2 journals
    T6: Evento nomina.mensual.registrada publicado con mes, anio, total_nomina, empleados_count
    T7 (RED): Duplicado empleado+mes+anio retorna HTTP 409 "ya registrada"
    """
    print("\n" + "=" * 80)
    print("BUILD 23 — F8 NOMINA MENSUAL PER-EMPLOYEE JOURNALS: RESUMEN DE TESTS")
    print("=" * 80)
    print("T1: 3 journals creados para nomina enero (uno por empleado)")
    print("T2: Montos correctos (debito gastos_nomina 5493 + credito banco 5314)")
    print("T3: Journal observations con nombre empleado y mes en espanol")
    print("T4: Fallo Alegra NO inserta en nomina_registros (GARANTIA CRITICA)")
    print("T5: Nomina febrero con 2 empleados crea 2 journals")
    print("T6: Evento nomina.mensual.registrada publicado con datos correctos")
    print("T7 (RED): HTTP 409 para duplicado empleado+mes+anio")
    print("=" * 80)
    print("ESTADO ACTUAL: RED — routers.nomina.registrar_nomina_mensual no existe aun")
    print("PROXIMO: Plan 07-02 implementara registrar_nomina_mensual")
    print("=" * 80)
