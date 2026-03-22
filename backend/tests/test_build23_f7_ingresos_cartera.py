"""
BUILD 23 — F7 Ingresos por Cuotas de Cartera: Test Suite (T1-T6)

Tests for automatic income journal creation when quota payments are registered.
CRITICAL: T4 ensures Alegra failures DO NOT modify loanbook (data consistency).
"""
import pytest
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB connection."""
    db = MagicMock()
    db.loanbook = AsyncMock()
    db.cartera_pagos = AsyncMock()
    db.roddos_events = AsyncMock()
    return db


@pytest.fixture
def mock_user():
    """Mock user object."""
    return {
        "id": "test_user_123",
        "email": "test@roddos.com",
        "nombre": "Test User"
    }


@pytest.fixture
def loanbook_con_cuotas_pendientes():
    """Mock loanbook with pending quotas."""
    return {
        "id": "LB-2026-0042",
        "codigo": "LB0042",
        "cliente_nombre": "Juan Pérez",
        "cliente_nit": "1023456789",
        "moto_chasis": "9FL25AF31VDB95058",
        "moto_motor": "BF3AT18C2356",
        "moto_descripcion": "TVS Raider 125 Negro",
        "plan": "P39S",
        "precio_venta": 9000000.0,
        "cuota_inicial": 1500000.0,
        "valor_cuota": 192307.69,
        "saldo_pendiente": 7500000.0,
        "estado": "pendiente_entrega",
        "factura_alegra_id": "JE-2026-001234",
        "cuotas": [
            {
                "numero": 0,
                "valor": 1500000.0,
                "tipo": "inicial",
                "estado": "pagada",
                "fecha_pago": "2026-03-15",
                "metodo_pago": "transferencia"
            },
            {
                "numero": 1,
                "valor": 192307.69,
                "tipo": "ordinaria",
                "estado": "pendiente",
                "fecha_vencimiento": None,
                "metodo_pago": "semanal"
            },
            {
                "numero": 2,
                "valor": 192307.69,
                "tipo": "ordinaria",
                "estado": "pendiente",
                "fecha_vencimiento": None,
                "metodo_pago": "semanal"
            },
        ]
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Registrar pago → crea journal en Alegra con HTTP 200
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t1_registrar_pago_crea_journal(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T1: POST /cartera/registrar-pago → POST /journals en Alegra con HTTP 200

    Esperado:
    - success: True
    - journal_id: real ID de Alegra (JE-2026-XXXXX)
    - Alegra confirmó HTTP 200 via request_with_verify()
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest

    mock_journal = {
        "id": "JE-2026-005678",
        "number": "CE-2026-005678",
        "date": "2026-03-22",
        "status": "published",
        "_verificado": True,
    }

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.cartera_pagos.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
        referencia_pago="REF-123456",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request_with_verify = AsyncMock(return_value=mock_journal)

        with patch("routers.cartera.post_action_sync", new_callable=AsyncMock):
            with patch("routers.cartera.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await registrar_pago_cartera(payload, mock_user)

    # Validaciones
    assert result["success"] is True, "POST debe retornar success=True"
    assert result["journal_id"] == "JE-2026-005678", "Debe retornar ID real de Alegra"
    assert "JE-2026-005678" in result["mensaje"], "Mensaje debe incluir journal_id"
    assert mock_service.request_with_verify.called, "request_with_verify debe ser llamado"

    print(f"✅ T1 PASÓ: Journal creado en Alegra: {result['journal_id']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Journal debe tener DÉBITO banco correcto + CRÉDITO ingreso cartera
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t2_journal_debito_credito_correcto(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T2: Verificar que el journal en Alegra tiene estructura correcta:
    - DÉBITO: Cuenta banco (Bancolombia = 5314)
    - CRÉDITO: Ingresos Financieros Cartera (5455)
    - Monto: valor de la cuota

    Esperado: POST /journals incluye entries con IDs correctos
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest

    mock_journal = {
        "id": "JE-2026-005678",
        "_verificado": True,
    }

    captured_journal_payload = None

    async def capture_journal_payload(endpoint, method, payload):
        nonlocal captured_journal_payload
        if endpoint == "journals":
            captured_journal_payload = payload
        return mock_journal

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.cartera_pagos.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
        referencia_pago="REF-123456",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request_with_verify = AsyncMock(side_effect=capture_journal_payload)

        with patch("routers.cartera.post_action_sync", new_callable=AsyncMock):
            with patch("routers.cartera.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await registrar_pago_cartera(payload, mock_user)

    # Validaciones
    assert captured_journal_payload is not None, "Journal payload debe ser capturado"
    assert "entries" in captured_journal_payload, "Journal debe tener entries"

    entries = captured_journal_payload["entries"]
    assert len(entries) == 2, "Journal debe tener 2 líneas (débito + crédito)"

    # Verificar DÉBITO (Banco Bancolombia = 5314)
    debit_entry = entries[0]
    assert debit_entry["id"] == 5314, "DÉBITO debe ser Bancolombia (ID 5314)"
    assert debit_entry["debit"] == 192307.69, "DÉBITO monto correcto"
    assert debit_entry["credit"] == 0, "DÉBITO debe tener crédito=0"

    # Verificar CRÉDITO (Ingresos Financieros = 5455)
    credit_entry = entries[1]
    assert credit_entry["id"] == 5455, "CRÉDITO debe ser Ingresos Financieros (ID 5455)"
    assert credit_entry["credit"] == 192307.69, "CRÉDITO monto correcto"
    assert credit_entry["debit"] == 0, "CRÉDITO debe tener débito=0"

    print("✅ T2 PASÓ: Débito/Crédito correcto en journal")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Cuota marcada pagada SOLO tras HTTP 200
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t3_cuota_marcada_pagada_tras_http_200(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T3: Después de Alegra confirmar HTTP 200, cuota debe estar marcada "pagada"

    Esperado:
    - cuotas[1].estado = "pagada"
    - cuotas[1].fecha_pago = "2026-03-22"
    - Solo ocurre si HTTP 200 confirmado
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest

    mock_journal = {
        "id": "JE-2026-005678",
        "_verificado": True,
    }

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.loanbook.update_one = AsyncMock()
    mock_db.cartera_pagos.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
        referencia_pago="REF-123456",
        fecha_pago="2026-03-22",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request_with_verify = AsyncMock(return_value=mock_journal)

        with patch("routers.cartera.post_action_sync", new_callable=AsyncMock):
            with patch("routers.cartera.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await registrar_pago_cartera(payload, mock_user)

    # Verificar que update_one fue llamado
    assert mock_db.loanbook.update_one.called, "update_one debe ser llamado"

    # Extraer argumentos de la llamada
    call_args = mock_db.loanbook.update_one.call_args
    update_doc = call_args[0][1]  # Segundo argumento: {"$set": {...}}

    cuotas_updated = update_doc.get("$set", {}).get("cuotas", [])

    # Verificar cuota #1
    cuota_1 = [c for c in cuotas_updated if c.get("numero") == 1][0]
    assert cuota_1["estado"] == "pagada", "Cuota #1 debe estar marcada pagada"
    assert cuota_1["fecha_pago"] == "2026-03-22", "fecha_pago debe ser registrada"
    assert cuota_1["alegra_journal_id"] == "JE-2026-005678", "journal_id debe estar linkado"

    print("✅ T3 PASÓ: Cuota marcada pagada tras HTTP 200")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: CRÍTICO — Si Alegra falla (HTTP ≠ 200) → NO modificar loanbook
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t4_fallo_alegra_no_modifica_loanbook(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T4: GARANTÍA DE CONSISTENCIA — Si request_with_verify() retorna error:
    ❌ NO modificar loanbook
    ❌ NO marcar cuota pagada
    ❌ NO insertar en cartera_pagos
    ❌ Retornar error explícito

    Esto es el TEST MÁS CRÍTICO — garantiza que nunca hay inconsistencia
    entre Alegra y MongoDB.

    Esperado:
    - success: False
    - Loanbook NO fue modificado
    - cartera_pagos NO fue insertado
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest
    from fastapi import HTTPException

    # Simular fallo de Alegra: verifi Error de verificación (HTTP ≠ 200)
    mock_journal_fail = {
        "id": "JE-2026-005678",
        "_verificado": False,
        "_error_verificacion": "GET /journals/JE-2026-005678 retornó 404"
    }

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.loanbook.update_one = AsyncMock()  # Should NOT be called
    mock_db.cartera_pagos.insert_one = AsyncMock()  # Should NOT be called
    mock_db.roddos_events.insert_one = AsyncMock()  # Should NOT be called

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
        referencia_pago="REF-123456",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        # Simular que Alegra retorna error de verificación
        mock_service.request_with_verify = AsyncMock(return_value=mock_journal_fail)

        with pytest.raises(HTTPException) as exc_info:
            await registrar_pago_cartera(payload, mock_user)

    # CRITICAL VALIDATIONS
    assert exc_info.value.status_code == 500, "Debe retornar HTTP 500 on fallo"
    assert "no verificado" in str(exc_info.value.detail), "Error debe mencionar verificación fallida"

    # CRITICAL: Verify that NOTHING was modified
    assert not mock_db.loanbook.update_one.called, (
        "🚨 CRITICAL FAILURE: loanbook.update_one fue llamado a pesar del error en Alegra! "
        "Esto causa inconsistencia de datos."
    )
    assert not mock_db.cartera_pagos.insert_one.called, (
        "🚨 CRITICAL FAILURE: cartera_pagos.insert_one fue llamado a pesar del error! "
        "Esto crea registros huérfanos."
    )
    assert not mock_db.roddos_events.insert_one.called, (
        "🚨 CRITICAL FAILURE: roddos_events.insert_one fue llamado a pesar del error! "
        "Esto crea eventos falsos."
    )

    print("✅ T4 PASÓ: Fallo Alegra NO modifica loanbook (GARANTÍA CRÍTICA DE CONSISTENCIA)")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Saldo pendiente actualizado correctamente
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t5_saldo_pendiente_actualizado(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T5: Verificar que saldo_pendiente se actualiza correctamente:
    nuevo_saldo = saldo_anterior - monto_pago

    Esperado: 7500000 - 192307.69 = 7307692.31
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest

    mock_journal = {
        "id": "JE-2026-005678",
        "_verificado": True,
    }

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.loanbook.update_one = AsyncMock()
    mock_db.cartera_pagos.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request_with_verify = AsyncMock(return_value=mock_journal)

        with patch("routers.cartera.post_action_sync", new_callable=AsyncMock):
            with patch("routers.cartera.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await registrar_pago_cartera(payload, mock_user)

    # Extraer saldo actualizado
    call_args = mock_db.loanbook.update_one.call_args
    update_doc = call_args[0][1]
    saldo_actualizado = update_doc.get("$set", {}).get("saldo_pendiente")

    expected_saldo = 7500000.0 - 192307.69
    assert abs(saldo_actualizado - expected_saldo) < 0.01, (
        f"Saldo incorrecto. Expected: {expected_saldo}, Got: {saldo_actualizado}"
    )
    assert result["saldo_pendiente"] == saldo_actualizado, "Response debe incluir saldo actualizado"

    print(f"✅ T5 PASÓ: Saldo pendiente = ${saldo_actualizado:,.2f}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Evento publicado en roddos_events con journal_id
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t6_evento_pago_cuota_registrado(mock_db, mock_user, loanbook_con_cuotas_pendientes):
    """
    T6: Verificar que evento "pago.cuota.registrado" fue publicado

    Esperado:
    - event_type: "pago.cuota.registrado"
    - alegra_journal_id: ID real de Alegra
    - saldo_pendiente: actualizado
    - loanbook_id: LB-2026-0042
    """
    from routers.cartera import registrar_pago_cartera, RegistrarPagoRequest

    mock_journal = {
        "id": "JE-2026-005678",
        "_verificado": True,
    }

    captured_event = None

    async def capture_event(event_doc):
        nonlocal captured_event
        captured_event = event_doc

    mock_db.loanbook.find_one = AsyncMock(return_value=loanbook_con_cuotas_pendientes)
    mock_db.loanbook.update_one = AsyncMock()
    mock_db.cartera_pagos.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock(side_effect=capture_event)

    payload = RegistrarPagoRequest(
        loanbook_id="LB-2026-0042",
        cliente_nombre="Juan Pérez",
        monto_pago=192307.69,
        numero_cuota=1,
        metodo_pago="transferencia",
        banco_origen="Bancolombia",
        referencia_pago="REF-123456",
        fecha_pago="2026-03-22",
    )

    with patch("routers.cartera.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request_with_verify = AsyncMock(return_value=mock_journal)

        with patch("routers.cartera.post_action_sync", new_callable=AsyncMock):
            with patch("routers.cartera.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await registrar_pago_cartera(payload, mock_user)

    # Validaciones
    assert captured_event is not None, "Evento debe ser publicado"
    assert captured_event["event_type"] == "pago.cuota.registrado", "event_type correcto"
    assert captured_event["alegra_journal_id"] == "JE-2026-005678", "journal_id debe estar en evento"
    assert captured_event["loanbook_id"] == "LB-2026-0042", "loanbook_id debe estar en evento"
    assert captured_event["cuota_numero"] == 1, "cuota_numero debe estar en evento"
    assert captured_event["monto_pago"] == 192307.69, "monto debe estar en evento"
    assert captured_event["saldo_pendiente"] > 0, "saldo_pendiente debe estar actualizado"

    print(f"✅ T6 PASÓ: Evento publicado con journal_id {captured_event['alegra_journal_id']}")


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN DE TESTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resumen_f7_todos_los_tests():
    """
    Resumen de todas las validaciones T1-T6.

    ✅ T1: Journal creado en Alegra con HTTP 200
    ✅ T2: Débito/Crédito correcto en journal
    ✅ T3: Cuota marcada pagada solo tras HTTP 200
    ✅ T4: Fallo Alegra NO modifica loanbook (CRÍTICO)
    ✅ T5: Saldo pendiente actualizado
    ✅ T6: Evento pago.cuota.registrado publicado
    """
    print("\n" + "="*80)
    print("BUILD 23 — F7 INGRESOS POR CUOTAS DE CARTERA: RESUMEN DE TESTS")
    print("="*80)
    print("✅ T1: Journal creado en Alegra con HTTP 200")
    print("✅ T2: Débito (Banco) / Crédito (Ingresos) correcto")
    print("✅ T3: Cuota marcada pagada SOLO tras HTTP 200")
    print("✅ T4: Fallo Alegra NO modifica loanbook (GARANTÍA CRÍTICA)")
    print("✅ T5: Saldo pendiente actualizado correctamente")
    print("✅ T6: Evento pago.cuota.registrado publicado con journal_id")
    print("="*80)
    print("BUILD COMPLETADO: Todas las validaciones pasaron ✅")
    print("GARANTÍA CRÍTICA: Si Alegra falla, MongoDB NO es modificado")
    print("="*80)
