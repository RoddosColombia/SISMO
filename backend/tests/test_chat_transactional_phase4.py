"""
Phase 04 Plan 05 — Chat Transaccional Real: Test Suite (C1-C8 + V1)

RED phase TDD tests — ALL tests must FAIL because clasificar_gasto_chat()
does not exist yet in accounting_engine.py, and crear_causacion still uses
request() instead of request_with_verify().

Tests cover:
- C1: Arriendo classification
- C2: Honorarios PJ classification
- C3: Honorarios PN classification
- C4: Auteco NIT 860024781 autoretenedor detection
- C5: Socio Andres CC 80075452 CXC socios
- C6: Socio Ivan CC 80086601 CXC socios
- C7: Servicios classification
- C8: Compras classification with retefuente 2.5%
- V1: crear_causacion must use request_with_verify not request
"""
import asyncio
import os
import sys
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# ── TDD: Try/except so the file is parseable even when function doesn't exist ──
try:
    from services.accounting_engine import clasificar_gasto_chat
except ImportError:
    clasificar_gasto_chat = None


# ══════════════════════════════════════════════════════════════════════════════
# FIXTURES
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def mock_db():
    """Mock MongoDB connection."""
    db = MagicMock()
    db.chat_messages = AsyncMock()
    db.roddos_events = AsyncMock()
    db.cfo_cache = AsyncMock()
    db.alegra_credentials = MagicMock()
    db.alegra_credentials.find_one = AsyncMock(
        return_value={"email": "", "token": "", "is_demo_mode": True}
    )
    return db


@pytest.fixture
def mock_user():
    """Mock user object."""
    return {
        "id": "test_user_phase4",
        "email": "test@roddos.com",
        "nombre": "Test User Phase4"
    }


# ══════════════════════════════════════════════════════════════════════════════
# C1: Arriendo classification
# ══════════════════════════════════════════════════════════════════════════════

def test_c1_arriendo_clasificacion():
    """CHAT-01: 'Pagamos arriendo $3.614.953' -> tipo_gasto=arrendamiento, cuenta_debito=5480"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Pagamos arriendo $3.614.953",
        proveedor="Inmobiliaria XYZ",
        monto=3614953,
    )
    assert result["tipo_gasto"] == "arrendamiento", (
        f"Expected 'arrendamiento' pero got '{result.get('tipo_gasto')}'"
    )
    assert result["cuenta_debito"] == 5480, (
        f"Cuenta debito arrendamiento debe ser 5480, got {result.get('cuenta_debito')}"
    )
    assert result["aplica_reteica"] is True, "ReteICA aplica siempre en Bogota"
    assert result["es_autoretenedor"] is False, "Inmobiliaria XYZ no es autoretenedor"


# ══════════════════════════════════════════════════════════════════════════════
# C2: Honorarios PJ
# ══════════════════════════════════════════════════════════════════════════════

def test_c2_honorarios_pj_clasificacion():
    """CHAT-02: Honorarios a persona juridica -> cuenta_debito=5476"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Honorarios a Inversiones XYZ por $500.000",
        proveedor="Inversiones XYZ SAS",
        monto=500000,
    )
    assert result["tipo_gasto"] == "honorarios", (
        f"Expected 'honorarios' pero got '{result.get('tipo_gasto')}'"
    )
    assert result["cuenta_debito"] == 5476, (
        f"Honorarios PJ debe usar cuenta 5476, got {result.get('cuenta_debito')}"
    )
    assert result["es_socio"] is False, "Proveedor externo no es socio"


# ══════════════════════════════════════════════════════════════════════════════
# C3: Honorarios PN
# ══════════════════════════════════════════════════════════════════════════════

def test_c3_honorarios_pn_clasificacion():
    """CHAT-03: Honorarios a persona natural -> cuenta_debito=5475"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Honorarios al abogado $800.000",
        proveedor="Carlos Gomez",
        monto=800000,
    )
    assert result["tipo_gasto"] == "honorarios", (
        f"Expected 'honorarios' pero got '{result.get('tipo_gasto')}'"
    )
    assert result["cuenta_debito"] == 5475, (
        f"Honorarios PN debe usar cuenta 5475, got {result.get('cuenta_debito')}"
    )
    assert result["es_socio"] is False, "Abogado externo no es socio"


# ══════════════════════════════════════════════════════════════════════════════
# C4: Auteco NIT 860024781 — autoretenedor
# ══════════════════════════════════════════════════════════════════════════════

def test_c4_auteco_autoretenedor():
    """CHAT-04: Compra a Auteco NIT 860024781 -> es_autoretenedor=True, no retefuente"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Compra a Auteco por $2.000.000",
        proveedor="Auteco Kawasaki",
        nit="860024781",
        monto=2000000,
    )
    assert result["es_autoretenedor"] is True, (
        "Auteco NIT 860024781 debe ser detectado como autoretenedor"
    )
    # Autoretenedor: retefuente = 0
    from services.accounting_engine import calcular_retenciones
    retenciones = calcular_retenciones(
        tipo_gasto=result["tipo_gasto"],
        monto_bruto=2000000,
        es_autoretenedor=True,
        aplica_reteica=result["aplica_reteica"],
    )
    assert retenciones["retefuente_valor"] == 0, (
        "Autoretenedor Auteco no debe generar retefuente — es_autoretenedor=True"
    )


# ══════════════════════════════════════════════════════════════════════════════
# C5: Socio Andres CC 80075452 -> CXC socios
# ══════════════════════════════════════════════════════════════════════════════

def test_c5_socio_andres_cxc():
    """CHAT-05: Prestamo a socio Andres CC 80075452 -> es_socio=True, cuenta_debito=5329"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Prestamo a socio Andres $1.000.000",
        proveedor="Andres San Juan",
        nit="80075452",
        monto=1000000,
    )
    assert result["es_socio"] is True, (
        "CC 80075452 (Andres) debe ser detectado como socio"
    )
    assert result["cuenta_debito"] == 5329, (
        f"CXC socios debe usar cuenta 5329, got {result.get('cuenta_debito')}"
    )
    assert result["tipo_gasto"] == "socio", (
        f"Prestamo a socio debe clasificarse como 'socio', got '{result.get('tipo_gasto')}'"
    )


# ══════════════════════════════════════════════════════════════════════════════
# C6: Socio Ivan CC 80086601 -> CXC socios
# ══════════════════════════════════════════════════════════════════════════════

def test_c6_socio_ivan_cxc():
    """CHAT-05: Prestamo a socio Ivan CC 80086601 -> es_socio=True, cuenta_debito=5329"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Prestamo a socio Ivan $500.000",
        proveedor="Ivan Alvarado",
        nit="80086601",
        monto=500000,
    )
    assert result["es_socio"] is True, (
        "CC 80086601 (Ivan) debe ser detectado como socio"
    )
    assert result["cuenta_debito"] == 5329, (
        f"CXC socios debe usar cuenta 5329, got {result.get('cuenta_debito')}"
    )
    assert result["tipo_gasto"] == "socio", (
        f"Prestamo a socio debe clasificarse como 'socio', got '{result.get('tipo_gasto')}'"
    )


# ══════════════════════════════════════════════════════════════════════════════
# C7: Servicios classification
# ══════════════════════════════════════════════════════════════════════════════

def test_c7_servicio_asistencia_tecnica():
    """CHAT-01: 'Servicio de asistencia tecnica $400.000' -> tipo_gasto=servicios"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Servicio de asistencia tecnica $400.000",
        proveedor="TechSupport SAS",
        monto=400000,
    )
    assert result["tipo_gasto"] == "servicios", (
        f"Expected 'servicios' pero got '{result.get('tipo_gasto')}'"
    )
    # cuenta_debito puede ser 5483 (procesamiento datos) o 5493 (gastos generales fallback)
    assert result["cuenta_debito"] in (5483, 5484, 5493), (
        f"Cuenta debito servicios debe ser 5483/5484 o fallback 5493, got {result.get('cuenta_debito')}"
    )
    assert result["aplica_reteica"] is True, "ReteICA aplica siempre en Bogota"


# ══════════════════════════════════════════════════════════════════════════════
# C8: Compras classification + retefuente 2.5%
# ══════════════════════════════════════════════════════════════════════════════

def test_c8_compras_retefuente():
    """CHAT-02: 'Compra de repuestos $2.000.000' -> tipo_gasto=compras, retefuente=2.5%"""
    assert clasificar_gasto_chat is not None, "clasificar_gasto_chat() not implemented yet"
    result = clasificar_gasto_chat(
        descripcion="Compra de repuestos $2.000.000",
        proveedor="Repuestos Motos Ltda",
        monto=2000000,
    )
    assert result["tipo_gasto"] == "compras", (
        f"Expected 'compras' pero got '{result.get('tipo_gasto')}'"
    )
    # Validate via calcular_retenciones that compras uses 2.5%
    from services.accounting_engine import calcular_retenciones
    retenciones = calcular_retenciones(
        tipo_gasto="compras",
        monto_bruto=2000000,
        es_autoretenedor=False,
        aplica_reteica=result["aplica_reteica"],
    )
    assert retenciones["retefuente_pct"] == 0.025, (
        f"Compras debe tener ReteFuente 2.5%, got {retenciones.get('retefuente_pct')}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# V1: crear_causacion must call request_with_verify not request
# ══════════════════════════════════════════════════════════════════════════════

def test_v1_crear_causacion_uses_request_with_verify():
    """CHAT-04: crear_causacion must use service.request_with_verify(), not service.request()

    This test will FAIL in RED phase because ai_chat.py line ~5345 still calls
    service.request() instead of service.request_with_verify().
    """
    from unittest.mock import AsyncMock, MagicMock, patch, call

    async def _run():
        # Lazy import to avoid anthropic import errors in test env
        from ai_chat import execute_chat_action

        # Build minimal payload for crear_causacion
        payload = {
            "descripcion": "Honorarios al abogado $800.000",
            "proveedor": "Carlos Gomez",
            "monto": 800000,
            "tipo_gasto": "honorarios",
            "tipo_proveedor": "PN",
            "fecha": "2026-03-30",
            "entradas": [
                {"cuenta_id": 5475, "debe": 800000, "haber": 0},
                {"cuenta_id": 5376, "debe": 0, "haber": 800000},
            ],
        }

        db = MagicMock()
        db.chat_messages = AsyncMock()
        db.roddos_events = AsyncMock()
        db.cfo_cache = AsyncMock()
        db.alegra_credentials = MagicMock()
        db.alegra_credentials.find_one = AsyncMock(
            return_value={"email": "", "token": "", "is_demo_mode": True}
        )
        db.agent_memory = MagicMock()
        db.agent_memory.find_one = AsyncMock(return_value=None)

        user = {"id": "test_user_v1", "email": "test@roddos.com", "nombre": "Test V1"}

        request_with_verify_mock = AsyncMock(return_value={
            "id": "journal-999",
            "_verificado": True,
            "_verificacion_id": "journal-999",
        })

        with patch("alegra_service.AlegraService.request_with_verify", request_with_verify_mock):
            with patch("alegra_service.AlegraService.request", new_callable=AsyncMock) as request_mock:
                try:
                    await execute_chat_action("crear_causacion", payload, db, user)
                except Exception:
                    pass  # We only care about which method was called

                # KEY ASSERTION: request_with_verify must be called, request must NOT
                assert request_with_verify_mock.called, (
                    "crear_causacion DEBE llamar service.request_with_verify() — "
                    "no service.request(). Verificacion POST+GET es obligatoria."
                )
                # If request was called instead of request_with_verify, this gives detail
                if request_mock.called:
                    raise AssertionError(
                        f"crear_causacion llamo service.request() en lugar de "
                        f"service.request_with_verify(). Calls: {request_mock.call_args_list}"
                    )

    asyncio.run(_run())


# ══════════════════════════════════════════════════════════════════════════════
# ADDITIONAL: reteica 0.414% always applies (Bogota)
# ══════════════════════════════════════════════════════════════════════════════

def test_reteica_siempre_aplica_bogota():
    """CHAT-05: calcular_retenciones con aplica_reteica=True debe calcular 0.414% correctamente"""
    from services.accounting_engine import calcular_retenciones

    retenciones = calcular_retenciones(
        tipo_proveedor="PJ",
        tipo_gasto="servicios",
        monto_bruto=1000000,
        es_autoretenedor=False,
        aplica_reteica=True,
    )
    assert retenciones["reteica_pct"] == pytest.approx(0.00414, abs=1e-5), (
        f"ReteICA debe ser 0.414% = 0.00414, got {retenciones.get('reteica_pct')}"
    )
    assert abs(retenciones["reteica_valor"] - 4140) < 5, (
        f"ReteICA sobre $1M debe ser ~$4.140, got {retenciones.get('reteica_valor')}"
    )


# ══════════════════════════════════════════════════════════════════════════════
# WIRING TESTS: clasificar_gasto_chat called inside crear_causacion
# ══════════════════════════════════════════════════════════════════════════════

def test_wiring_arriendo_end_to_end():
    """WIRE: crear_causacion with arriendo payload calls clasificar_gasto_chat and returns cuenta 5480 + ReteFuente 3.5%"""
    from unittest.mock import AsyncMock, MagicMock, patch

    async def _run():
        from ai_chat import execute_chat_action

        payload = {
            "descripcion": "Pagamos arriendo $3.614.953",
            "proveedor": "Inmobiliaria XYZ",
            "monto": 3614953,
            "fecha": "2026-03-30",
            "entradas": [
                {"cuenta_id": 5480, "debe": 3614953, "haber": 0},
                {"cuenta_id": 5376, "debe": 0, "haber": 3614953},
            ],
        }

        db = MagicMock()
        db.chat_messages = AsyncMock()
        db.roddos_events = AsyncMock()
        db.cfo_cache = AsyncMock()
        db.alegra_credentials = MagicMock()
        db.alegra_credentials.find_one = AsyncMock(
            return_value={"email": "", "token": "", "is_demo_mode": True}
        )
        db.roddos_cuentas = MagicMock()
        db.roddos_cuentas.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.agent_memory = MagicMock()
        db.agent_memory.find_one = AsyncMock(return_value=None)

        user = {"id": "test_wire", "email": "test@roddos.com", "nombre": "Test Wire"}

        from services.accounting_engine import clasificar_gasto_chat as real_clasif

        call_tracker = {"called": False, "result": None}

        def spy_clasificar(*args, **kwargs):
            call_tracker["called"] = True
            result = real_clasif(*args, **kwargs)
            call_tracker["result"] = result
            return result

        async def mock_request_with_verify(endpoint, method, data):
            return {"id": "journal-wire-1", "_verificado": True}

        # Patch at the module level where the lazy import resolves
        with patch("alegra_service.AlegraService.request_with_verify", side_effect=mock_request_with_verify):
            with patch("services.accounting_engine.clasificar_gasto_chat", side_effect=spy_clasificar):
                try:
                    await execute_chat_action("crear_causacion", payload, db, user)
                except Exception:
                    pass

                assert call_tracker["called"], (
                    "clasificar_gasto_chat() MUST be called inside crear_causacion handler"
                )

                r = call_tracker["result"]
                assert r["tipo_gasto"] == "arrendamiento", (
                    f"Expected arrendamiento, got {r['tipo_gasto']}"
                )
                assert r["cuenta_debito"] == 5480, (
                    f"Expected 5480, got {r['cuenta_debito']}"
                )
                assert r["confianza"] >= 0.7, (
                    f"Arriendo confianza must be >= 0.7, got {r['confianza']}"
                )

    asyncio.run(_run())


def test_wiring_auteco_no_retefuente():
    """WIRE: crear_causacion with NIT 860024781 (Auteco) -> autoretenedor, no ReteFuente"""
    from unittest.mock import AsyncMock, MagicMock, patch

    async def _run():
        from ai_chat import execute_chat_action

        payload = {
            "descripcion": "Compra repuestos Auteco $5.000.000",
            "proveedor": "Auteco Kawasaki",
            "nit": "860024781",
            "monto": 5000000,
            "fecha": "2026-03-30",
            "entradas": [
                {"cuenta_id": 5493, "debe": 5000000, "haber": 0},
                {"cuenta_id": 5376, "debe": 0, "haber": 5000000},
            ],
        }

        db = MagicMock()
        db.chat_messages = AsyncMock()
        db.roddos_events = AsyncMock()
        db.cfo_cache = AsyncMock()
        db.alegra_credentials = MagicMock()
        db.alegra_credentials.find_one = AsyncMock(
            return_value={"email": "", "token": "", "is_demo_mode": True}
        )
        db.roddos_cuentas = MagicMock()
        db.roddos_cuentas.find = MagicMock(return_value=MagicMock(to_list=AsyncMock(return_value=[])))
        db.agent_memory = MagicMock()
        db.agent_memory.find_one = AsyncMock(return_value=None)

        user = {"id": "test_wire_auteco", "email": "test@roddos.com", "nombre": "Test Wire Auteco"}

        from services.accounting_engine import clasificar_gasto_chat as real_clasif

        call_tracker = {"called": False, "result": None}

        def spy_clasificar(*args, **kwargs):
            call_tracker["called"] = True
            result = real_clasif(*args, **kwargs)
            call_tracker["result"] = result
            return result

        async def mock_request_with_verify(endpoint, method, data):
            return {"id": "journal-wire-auteco", "_verificado": True}

        with patch("alegra_service.AlegraService.request_with_verify", side_effect=mock_request_with_verify):
            with patch("services.accounting_engine.clasificar_gasto_chat", side_effect=spy_clasificar):
                try:
                    await execute_chat_action("crear_causacion", payload, db, user)
                except Exception:
                    pass

                assert call_tracker["called"], (
                    "clasificar_gasto_chat() MUST be called for Auteco payload"
                )

                r = call_tracker["result"]
                assert r["es_autoretenedor"] is True, (
                    "Auteco NIT 860024781 must be detected as autoretenedor"
                )

                # Verify retenciones: autoretenedor = 0 retefuente
                from services.accounting_engine import calcular_retenciones
                ret = calcular_retenciones(
                    tipo_gasto=r["tipo_gasto"],
                    monto_bruto=5000000,
                    es_autoretenedor=True,
                    aplica_reteica=r["aplica_reteica"],
                )
                assert ret["retefuente_valor"] == 0, (
                    f"Autoretenedor must have retefuente_valor=0, got {ret['retefuente_valor']}"
                )

    asyncio.run(_run())
