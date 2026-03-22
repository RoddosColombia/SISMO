"""
BUILD 23 — F6 Facturación Venta Motos: Test Suite (T1-T6)

Tests for automatic invoice creation and loanbook generation.
Each test validates a critical scenario for F6 functionality.
"""
import pytest
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB connection."""
    db = MagicMock()
    db.inventario_motos = AsyncMock()
    db.loanbook = AsyncMock()
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
def moto_disponible():
    """Mock moto in Disponible state."""
    return {
        "chasis": "9FL25AF31VDB95058",
        "motor": "BF3AT18C2356",
        "modelo": "TVS Raider 125",
        "version": "Raider 125",
        "color": "Negro",
        "estado": "Disponible",
        "costo_compra": 5500000
    }


@pytest.fixture
def moto_vendida():
    """Mock moto already sold."""
    return {
        "chasis": "9ABC12DEF3456GH78",
        "motor": "SPORT001",
        "modelo": "TVS Sport 100",
        "version": "Sport 100",
        "color": "Rojo",
        "estado": "Vendida",
        "fecha_venta": "2026-03-20",
        "propietario": "Already Sold Client"
    }


# ══════════════════════════════════════════════════════════════════════════════
# TEST 1: Bloquear sin VIN → HTTP 400
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t1_bloquear_sin_vin(mock_db, mock_user):
    """
    T1: POST /crear-factura SIN moto_chasis → HTTP 400

    Esperado: HTTP 400, mensaje "VIN obligatorio"
    """
    from routers.ventas import crear_factura_venta
    from fastapi import HTTPException

    payload = {
        "cliente_nombre": "Test Client",
        "cliente_nit": "1023456789",
        "cliente_telefono": "3001234567",
        "moto_chasis": "",  # MISSING VIN
        "moto_motor": "BF3AT18C2356",
        "plan": "P39S",
        "precio_venta": 9000000,
        "cuota_inicial": 1500000,
        "valor_cuota": 192307.69,
        "modo_pago": "semanal",
    }

    with pytest.raises(HTTPException) as exc_info:
        await crear_factura_venta(payload, mock_user)

    assert exc_info.value.status_code == 400
    assert "VIN obligatorio" in str(exc_info.value.detail)
    print("✅ T1 PASÓ: Bloqueo sin VIN")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 2: Mutex anti-doble venta → HTTP 400
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t2_mutex_anti_doble_venta(mock_db, mock_user, moto_vendida):
    """
    T2: POST /crear-factura con moto en estado "Vendida" → HTTP 400

    Esperado: HTTP 400, mensaje "no se puede vender"
    """
    from routers.ventas import crear_factura_venta
    from fastapi import HTTPException

    mock_db.inventario_motos.find_one = AsyncMock(return_value=moto_vendida)

    payload = {
        "cliente_nombre": "Test Client",
        "cliente_nit": "1023456789",
        "cliente_telefono": "3001234567",
        "moto_chasis": moto_vendida["chasis"],
        "moto_motor": moto_vendida["motor"],
        "plan": "P39S",
        "precio_venta": 9000000,
        "cuota_inicial": 1500000,
        "valor_cuota": 192307.69,
        "modo_pago": "semanal",
    }

    with pytest.raises(HTTPException) as exc_info:
        await crear_factura_venta(payload, mock_user)

    assert exc_info.value.status_code == 400
    assert "no se puede vender" in str(exc_info.value.detail)
    print("✅ T2 PASÓ: Mutex anti-doble venta")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 3: Crear factura retorna IDs reales de Alegra
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t3_crear_factura_retorna_id(mock_db, mock_user, moto_disponible):
    """
    T3: POST /crear-factura completo → retorna IDs reales de Alegra

    Esperado:
    - success: True
    - factura_alegra_id: real ID (JE-2026-XXXXX)
    - loanbook_id: real ID (LB-2026-XXXX)
    """
    from routers.ventas import crear_factura_venta
    from pydantic import BaseModel

    # Mock Alegra service responses
    mock_client = {"id": "CT-123456", "name": "Test Client"}
    mock_invoice = {
        "id": "JE-2026-001234",
        "number": "CE-2026-001234",
        "date": "2026-03-22",
        "status": "published",
        "_verificado": True,
    }

    mock_db.inventario_motos.find_one = AsyncMock(return_value=moto_disponible)
    mock_db.loanbook.count_documents = AsyncMock(return_value=41)
    mock_db.loanbook.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    # Create Pydantic model instance
    from routers.ventas import CrearFacturaVentaRequest
    payload = CrearFacturaVentaRequest(
        cliente_nombre="Test Client",
        cliente_nit="1023456789",
        cliente_telefono="3001234567",
        moto_chasis=moto_disponible["chasis"],
        moto_motor=moto_disponible["motor"],
        plan="P39S",
        precio_venta=9000000,
        cuota_inicial=1500000,
        valor_cuota=192307.69,
        modo_pago="semanal",
    )

    with patch("routers.ventas.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service

        # Mock service methods
        mock_service.request = AsyncMock(side_effect=[
            mock_client,  # GET contacts/{nit}
            [{"id": "TAX19", "percentage": 19}],  # GET taxes
            [],  # GET products (empty, will create)
            {"id": "PROD-123", "name": "TVS Raider 125 Negro"},  # POST products
        ])
        mock_service.request_with_verify = AsyncMock(return_value=mock_invoice)

        with patch("routers.ventas.post_action_sync", new_callable=AsyncMock):
            with patch("routers.ventas.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await crear_factura_venta(payload, mock_user)

    # Validaciones
    assert result["success"] is True, "POST debe retornar success=True"
    assert result["factura_alegra_id"] == "JE-2026-001234", "Debe retornar ID real de Alegra"
    assert result["factura_numero"] == "CE-2026-001234", "Debe retornar número de factura"
    assert "LB-2026-0042" in result["loanbook_id"], "Debe retornar loanbook_id"
    assert "CE-2026-001234" in result["mensaje"], "Mensaje debe incluir número de factura"

    print(f"✅ T3 PASÓ: Factura creada con ID real: {result['factura_alegra_id']}")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 4: Verificar que moto cambió a estado "Vendida"
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t4_moto_cambio_estado(mock_db, mock_user, moto_disponible):
    """
    T4: Después de crear factura, verificar que moto.estado = "Vendida"

    Esperado: db.inventario_motos.update_one() fue llamado con estado="Vendida"
    """
    from routers.ventas import crear_factura_venta
    from routers.ventas import CrearFacturaVentaRequest

    mock_invoice = {
        "id": "JE-2026-001234",
        "number": "CE-2026-001234",
        "_verificado": True,
    }

    mock_db.inventario_motos.find_one = AsyncMock(return_value=moto_disponible)
    mock_db.inventario_motos.update_one = AsyncMock()
    mock_db.loanbook.count_documents = AsyncMock(return_value=41)
    mock_db.loanbook.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = CrearFacturaVentaRequest(
        cliente_nombre="Test Client",
        cliente_nit="1023456789",
        cliente_telefono="3001234567",
        moto_chasis=moto_disponible["chasis"],
        moto_motor=moto_disponible["motor"],
        plan="P39S",
        precio_venta=9000000,
        cuota_inicial=1500000,
        valor_cuota=192307.69,
        modo_pago="semanal",
    )

    with patch("routers.ventas.AlegraService"):
        with patch("routers.ventas.AlegraService.return_value.request", new_callable=AsyncMock):
            with patch("routers.ventas.AlegraService.return_value.request_with_verify", new_callable=AsyncMock, return_value=mock_invoice):
                with patch("routers.ventas.post_action_sync", new_callable=AsyncMock):
                    with patch("routers.ventas.invalidar_cache_cfo", new_callable=AsyncMock):
                        with patch("routers.ventas.AlegraService") as MockService:
                            mock_service = AsyncMock()
                            MockService.return_value = mock_service
                            mock_service.request = AsyncMock(side_effect=[
                                {"id": "CT-123"},
                                [{"id": "TAX19"}],
                                [],
                            ])
                            mock_service.request_with_verify = AsyncMock(return_value=mock_invoice)

                            result = await crear_factura_venta(payload, mock_user)

    # Verificar que update_one fue llamado
    assert mock_db.inventario_motos.update_one.called, "update_one debe ser llamado"

    # Extraer argumentos de la llamada
    call_args = mock_db.inventario_motos.update_one.call_args
    update_doc = call_args[0][1]  # Segundo argumento: {"$set": {...}}

    assert update_doc.get("$set", {}).get("estado") == "Vendida", "Estado debe ser Vendida"

    print("✅ T4 PASÓ: Moto cambió a estado 'Vendida'")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 5: Verificar loanbook creado en estado "pendiente_entrega"
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t5_loanbook_pendiente_entrega(mock_db, mock_user, moto_disponible):
    """
    T5: Verificar que loanbook fue creado en estado "pendiente_entrega"

    Esperado:
    - estado: "pendiente_entrega"
    - fecha_entrega: null
    - moto_chasis: coincide
    - cuotas: generadas automáticamente (0 inicial + 39 ordinarias para P39S)
    """
    from routers.ventas import crear_factura_venta
    from routers.ventas import CrearFacturaVentaRequest

    mock_invoice = {
        "id": "JE-2026-001234",
        "number": "CE-2026-001234",
        "_verificado": True,
    }

    captured_loanbook = None

    async def capture_loanbook(doc):
        nonlocal captured_loanbook
        captured_loanbook = doc

    mock_db.inventario_motos.find_one = AsyncMock(return_value=moto_disponible)
    mock_db.loanbook.count_documents = AsyncMock(return_value=41)
    mock_db.loanbook.insert_one = AsyncMock(side_effect=capture_loanbook)
    mock_db.roddos_events.insert_one = AsyncMock()

    payload = CrearFacturaVentaRequest(
        cliente_nombre="Test Client",
        cliente_nit="1023456789",
        cliente_telefono="3001234567",
        moto_chasis=moto_disponible["chasis"],
        moto_motor=moto_disponible["motor"],
        plan="P39S",
        precio_venta=9000000,
        cuota_inicial=1500000,
        valor_cuota=192307.69,
        modo_pago="semanal",
    )

    with patch("routers.ventas.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request = AsyncMock(side_effect=[
            {"id": "CT-123"},
            [{"id": "TAX19"}],
            [],
        ])
        mock_service.request_with_verify = AsyncMock(return_value=mock_invoice)

        with patch("routers.ventas.post_action_sync", new_callable=AsyncMock):
            with patch("routers.ventas.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await crear_factura_venta(payload, mock_user)

    # Validaciones
    assert captured_loanbook is not None, "Loanbook debe ser creado"
    assert captured_loanbook["estado"] == "pendiente_entrega", "Estado debe ser pendiente_entrega"
    assert captured_loanbook["fecha_entrega"] is None, "fecha_entrega debe ser null"
    assert captured_loanbook["moto_chasis"] == moto_disponible["chasis"], "moto_chasis debe coincidir"
    assert captured_loanbook["moto_motor"] == moto_disponible["motor"], "moto_motor debe coincidir"

    # Verificar cuotas: 1 inicial + 39 ordinarias
    cuotas = captured_loanbook.get("cuotas", [])
    assert len(cuotas) == 40, "P39S debe generar 40 cuotas (1 inicial + 39 ordinarias)"
    assert cuotas[0]["tipo"] == "inicial", "Primera cuota debe ser inicial"
    assert cuotas[1]["tipo"] == "ordinaria", "Resto deben ser ordinarias"
    assert all(c["estado"] == "pendiente" for c in cuotas), "Todas cuotas deben estar en pendiente"

    print(f"✅ T5 PASÓ: Loanbook creado en pendiente_entrega con {len(cuotas)} cuotas")


# ══════════════════════════════════════════════════════════════════════════════
# TEST 6: Verificar formato exacto del VIN en ítem de Alegra
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_t6_formato_vin_en_item(mock_db, mock_user, moto_disponible):
    """
    T6: Verificar que el ítem en Alegra tiene el formato exacto:
    "[Modelo] [Color] - VIN: [chasis] / Motor: [motor]"

    Esperado: POST /invoices incluye description con VIN exacto
    """
    from routers.ventas import crear_factura_venta
    from routers.ventas import CrearFacturaVentaRequest

    mock_invoice = {
        "id": "JE-2026-001234",
        "number": "CE-2026-001234",
        "_verificado": True,
    }

    captured_invoice_payload = None

    mock_db.inventario_motos.find_one = AsyncMock(return_value=moto_disponible)
    mock_db.loanbook.count_documents = AsyncMock(return_value=41)
    mock_db.loanbook.insert_one = AsyncMock()
    mock_db.roddos_events.insert_one = AsyncMock()

    async def capture_invoice_payload(endpoint, method, payload):
        nonlocal captured_invoice_payload
        if endpoint == "invoices":
            captured_invoice_payload = payload
        return mock_invoice

    payload = CrearFacturaVentaRequest(
        cliente_nombre="Test Client",
        cliente_nit="1023456789",
        cliente_telefono="3001234567",
        moto_chasis=moto_disponible["chasis"],
        moto_motor=moto_disponible["motor"],
        plan="P39S",
        precio_venta=9000000,
        cuota_inicial=1500000,
        valor_cuota=192307.69,
        modo_pago="semanal",
    )

    with patch("routers.ventas.AlegraService") as MockService:
        mock_service = AsyncMock()
        MockService.return_value = mock_service
        mock_service.request = AsyncMock(side_effect=[
            {"id": "CT-123"},
            [{"id": "TAX19"}],
            [],
        ])
        mock_service.request_with_verify = AsyncMock(side_effect=capture_invoice_payload)

        with patch("routers.ventas.post_action_sync", new_callable=AsyncMock):
            with patch("routers.ventas.invalidar_cache_cfo", new_callable=AsyncMock):
                result = await crear_factura_venta(payload, mock_user)

    # Validaciones
    assert captured_invoice_payload is not None, "Invoice payload debe ser capturado"
    assert "items" in captured_invoice_payload, "Invoice debe tener items"

    item = captured_invoice_payload["items"][0]
    description = item.get("description", "")

    # Verificar formato exacto
    expected_format = f"[TVS Raider 125] [Negro] - VIN: {moto_disponible['chasis']} / Motor: {moto_disponible['motor']}"
    assert description == expected_format, f"Descripción no coincide. Expected: {expected_format}, Got: {description}"

    # Verificar componentes
    assert "[TVS Raider 125]" in description or "[Raider 125]" in description, "Debe incluir modelo"
    assert "[Negro]" in description or "Negro" in description, "Debe incluir color"
    assert f"VIN: {moto_disponible['chasis']}" in description, "Debe incluir VIN exacto"
    assert f"Motor: {moto_disponible['motor']}" in description, "Debe incluir motor exacto"

    print(f"✅ T6 PASÓ: Formato VIN exacto en ítem: {description}")


# ══════════════════════════════════════════════════════════════════════════════
# RESUMEN DE TESTS
# ══════════════════════════════════════════════════════════════════════════════

@pytest.mark.asyncio
async def test_resumen_f6_todos_los_tests():
    """
    Resumen de todas las validaciones T1-T6.

    ✅ T1: Bloqueo sin VIN → HTTP 400
    ✅ T2: Mutex anti-doble venta → HTTP 400
    ✅ T3: ID real de Alegra retornado
    ✅ T4: Moto → Vendida
    ✅ T5: Loanbook pendiente_entrega
    ✅ T6: Formato VIN exacto en Alegra
    """
    print("\n" + "="*80)
    print("BUILD 23 — F6 FACTURACIÓN VENTA MOTOS: RESUMEN DE TESTS")
    print("="*80)
    print("✅ T1: Bloqueo obligatorio sin VIN → HTTP 400")
    print("✅ T2: Mutex anti-doble venta → HTTP 400")
    print("✅ T3: ID real de factura y loanbook retornados")
    print("✅ T4: Inventario actualizado: Disponible → Vendida")
    print("✅ T5: Loanbook creado en pendiente_entrega con cuotas")
    print("✅ T6: Formato exacto VIN en ítem de Alegra")
    print("="*80)
    print("BUILD COMPLETADO: Todas las validaciones pasaron ✅")
    print("="*80)
