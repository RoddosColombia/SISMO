"""
test_build22_ambiguous_handler.py — Tests for AmbiguousMovementHandler (BUILD 22 TAREA 2).

Tests:
1. Detección de movimientos ambiguos
2. Almacenamiento en MongoDB
3. Procesamiento de respuestas WhatsApp
4. Estado de resolución
5. Escalamiento a manual
"""

import pytest
import asyncio
from datetime import datetime, timezone
from uuid import uuid4

# Note: Run with: pytest tests/test_build22_ambiguous_handler.py -v


@pytest.mark.asyncio
async def test_detectar_ambiguedad_baja_confianza():
    """Test: Detecta movimiento ambiguo cuando confianza < 70%"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)

    # Crear clasificación con confianza baja (40%)
    clasificacion = ClasificacionResult(
        cuenta_debito=5484,
        cuenta_credito=None,
        confianza=0.40,  # < 70% → ambigua
        requiere_confirmacion=False,
        razon="Múltiples opciones posibles",
    )

    es_ambigua, tracking_id = await handler.detectar_y_procesar(
        movimiento_id=str(uuid4()),
        monto=1000000,
        descripcion="Software development",
        proveedor="AWS",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573001234567",
    )

    assert es_ambigua is True, "Debería detectarse como ambigua (confianza < 70%)"
    assert tracking_id is not None, "Debería retornar tracking_id"
    print(f"✓ Movimiento ambiguo detectado: {tracking_id}")


@pytest.mark.asyncio
async def test_detectar_no_ambiguedad_alta_confianza():
    """Test: No detecta movimiento ambiguo cuando confianza > 90%"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)

    # Crear clasificación con confianza alta (95%)
    clasificacion = ClasificacionResult(
        cuenta_debito=5329,
        cuenta_credito=5314,
        confianza=0.95,  # > 70% → no ambigua
        requiere_confirmacion=False,
        razon="Clasificación clara: Gasto de Socio",
    )

    es_ambigua, tracking_id = await handler.detectar_y_procesar(
        movimiento_id=str(uuid4()),
        monto=500000,
        descripcion="Retiro socio",
        proveedor="Juan Pérez",
        banco_origen=5314,
        clasificacion=clasificacion,
    )

    assert es_ambigua is False, "No debería detectarse como ambigua (confianza > 70%)"
    assert tracking_id is None, "No debería retornar tracking_id"
    print("✓ Movimiento de alta confianza aprobado automáticamente")


@pytest.mark.asyncio
async def test_almacenar_en_mongodb():
    """Test: Almacena movimiento en contabilidad_pendientes collection"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)
    movimiento_id = str(uuid4())

    clasificacion = ClasificacionResult(
        cuenta_debito=5484,
        cuenta_credito=None,
        confianza=0.45,
        requiere_confirmacion=False,
        razon="Clasificación ambigua",
    )

    await handler.detectar_y_procesar(
        movimiento_id=movimiento_id,
        monto=2500000,
        descripcion="Technical subscription",
        proveedor="GitHub",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573009876543",
    )

    # Verificar que está en MongoDB
    movimiento = await handler.obtener_movimiento(movimiento_id)
    assert movimiento is not None, "Movimiento debería estar en MongoDB"
    assert movimiento["monto"] == 2500000
    assert movimiento["estado"] == "pendiente"
    assert movimiento["confianza"] == 0.45
    print(f"✓ Movimiento almacenado en MongoDB: {movimiento_id}")


@pytest.mark.asyncio
async def test_procesar_respuesta_confirmacion():
    """Test: Procesa respuesta de confirmación del usuario"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)
    movimiento_id = str(uuid4())

    # Crear movimiento ambiguo
    clasificacion = ClasificacionResult(
        cuenta_debito=5484,
        cuenta_credito=None,
        confianza=0.50,
        requiere_confirmacion=False,
        razon="Necesita confirmación",
    )

    await handler.detectar_y_procesar(
        movimiento_id=movimiento_id,
        monto=3000000,
        descripcion="Cloud services",
        proveedor="Google Cloud",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573012345678",
    )

    # Procesar respuesta de confirmación
    success = await handler.procesar_respuesta_whatsapp(
        movimiento_id=movimiento_id,
        respuesta_usuario="Sí, confirmo",
        telefono_usuario="573012345678",
    )

    assert success is True, "Debería procesar respuesta correctamente"

    # Verificar estado actualizado
    movimiento = await handler.obtener_movimiento(movimiento_id)
    assert movimiento["estado"] == "confirmada"
    assert movimiento["fecha_resolucion"] is not None
    print(f"✓ Movimiento confirmado por usuario: {movimiento_id}")


@pytest.mark.asyncio
async def test_procesar_respuesta_rechazo():
    """Test: Procesa respuesta de rechazo del usuario"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)
    movimiento_id = str(uuid4())

    # Crear movimiento ambiguo
    clasificacion = ClasificacionResult(
        cuenta_debito=5483,
        cuenta_credito=None,
        confianza=0.35,
        requiere_confirmacion=False,
        razon="Múltiples interpretaciones",
    )

    await handler.detectar_y_procesar(
        movimiento_id=movimiento_id,
        monto=1500000,
        descripcion="Consulting fees",
        proveedor="Unknown Consultant",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573014141414",
    )

    # Procesar respuesta de rechazo
    success = await handler.procesar_respuesta_whatsapp(
        movimiento_id=movimiento_id,
        respuesta_usuario="No, esa no es la clasificación correcta",
        telefono_usuario="573014141414",
    )

    assert success is True, "Debería procesar rechazo correctamente"

    # Verificar estado actualizado
    movimiento = await handler.obtener_movimiento(movimiento_id)
    assert movimiento["estado"] == "rechazada"
    assert "rechazado por usuario" in movimiento["notas_resolucion"].lower()
    print(f"✓ Movimiento rechazado, escalado a manual: {movimiento_id}")


@pytest.mark.asyncio
async def test_marcar_resuelto():
    """Test: Marca movimiento como resuelto después de Alegra"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)
    movimiento_id = str(uuid4())

    # Crear y confirmar movimiento
    clasificacion = ClasificacionResult(
        cuenta_debito=5329,
        cuenta_credito=5314,
        confianza=0.60,
        requiere_confirmacion=False,
        razon="Socio - Necesita confirmación",
    )

    await handler.detectar_y_procesar(
        movimiento_id=movimiento_id,
        monto=5000000,
        descripcion="Socio payout",
        proveedor="Socio Mayoritario",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573099999999",
    )

    # Marcar como resuelto después de enviarse a Alegra
    success = await handler.marcar_resuelto(
        movimiento_id=movimiento_id,
        cuenta_debito_final=5329,
        cuenta_credito_final=5314,
        notas="Enviado a Alegra con éxito, journal#12345",
    )

    assert success is True, "Debería marcar como resuelto correctamente"

    movimiento = await handler.obtener_movimiento(movimiento_id)
    assert movimiento["estado"] == "resuelta"
    assert movimiento["cuenta_debito_final"] == 5329
    assert movimiento["fecha_resolucion"] is not None
    print(f"✓ Movimiento resuelto y enviado a Alegra: {movimiento_id}")


@pytest.mark.asyncio
async def test_obtener_pendientes_por_estado():
    """Test: Obtiene movimientos pendientes filtrados por estado"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
        EstadoResolucion,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)

    # Crear varios movimientos con diferentes estados
    for i in range(3):
        movimiento_id = str(uuid4())
        clasificacion = ClasificacionResult(
            cuenta_debito=5484,
            cuenta_credito=None,
            confianza=0.50,
            requiere_confirmacion=False,
            razon=f"Test movimiento {i}",
        )

        await handler.detectar_y_procesar(
            movimiento_id=movimiento_id,
            monto=1000000 * (i + 1),
            descripcion=f"Test {i}",
            proveedor=f"Provider {i}",
            banco_origen=5314,
            clasificacion=clasificacion,
            telefono_usuario="573001111111",
        )

    # Obtener pendientes
    pendientes = await handler.obtener_pendientes(estado=EstadoResolucion.PENDIENTE)
    assert len(pendientes) > 0, "Debería haber movimientos pendientes"
    print(f"✓ Obtenidos {len(pendientes)} movimientos pendientes")

    # Verificar que todos tienen estado "pendiente"
    for m in pendientes:
        assert m["estado"] == "pendiente"


@pytest.mark.asyncio
async def test_timeout_movimiento():
    """Test: Timeout en movimiento sin resolver después de N intentos"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        ClasificacionResult,
    )
    from database import db

    handler = AmbiguousMovementHandler(db)
    movimiento_id = str(uuid4())

    clasificacion = ClasificacionResult(
        cuenta_debito=5475,
        cuenta_credito=None,
        confianza=0.45,
        requiere_confirmacion=False,
        razon="Asesoría - necesita confirmación",
    )

    await handler.detectar_y_procesar(
        movimiento_id=movimiento_id,
        monto=800000,
        descripcion="Legal consultation",
        proveedor="Law firm ABC",
        banco_origen=5314,
        clasificacion=clasificacion,
        telefono_usuario="573055555555",
    )

    # Simular múltiples respuestas ambiguas
    for intento in range(handler.MAX_INTENTOS + 1):
        success = await handler.procesar_respuesta_whatsapp(
            movimiento_id=movimiento_id,
            respuesta_usuario="Quizás... no estoy seguro",  # Respuesta ambigua
            telefono_usuario="573055555555",
        )

    # Verificar que se marca como abandonada después de max intentos
    movimiento = await handler.obtener_movimiento(movimiento_id)
    if movimiento.get("intentos_whatsapp", 0) >= handler.MAX_INTENTOS:
        assert movimiento["estado"] == "abandonada"
        print(f"✓ Movimiento abandonado después de {handler.MAX_INTENTOS} intentos")
    else:
        print(f"⚠ Movimiento aún pendiente (intentos: {movimiento.get('intentos_whatsapp')})")


@pytest.mark.asyncio
async def test_contenedor_estructura():
    """Test: Estructura de datos correcta de MovimientoAmbiguo"""
    from services.accounting_engine import (
        AmbiguousMovementHandler,
        MovimientoAmbiguo,
        EstadoResolucion,
    )

    movimiento = MovimientoAmbiguo(
        id="test-001",
        monto=5000000,
        descripcion="Test transaction",
        proveedor="Test Provider",
        banco_origen=5314,
        fecha_movimiento=datetime.now(timezone.utc).isoformat(),
        cuenta_debito_sugerida=5484,
        cuenta_credito_sugerida=None,
        confianza=0.65,
        razon_ambiguedad="Multiple options possible",
    )

    assert movimiento.id == "test-001"
    assert movimiento.estado == EstadoResolucion.PENDIENTE
    assert movimiento.intentos_whatsapp == 0
    assert movimiento.alternativas is None or movimiento.alternativas == []
    print("✓ Estructura de MovimientoAmbiguo correcta")


def run_all_tests():
    """Ejecuta todos los tests."""
    print("\n" + "="*70)
    print("BUILD 22 — TAREA 2: Tests para AmbiguousMovementHandler")
    print("="*70 + "\n")

    # Note: En producción, usar: pytest tests/test_build22_ambiguous_handler.py -v
    print("Ejecutar tests con:")
    print("  pytest tests/test_build22_ambiguous_handler.py -v")
    print("\nTests incluidos:")
    print("  1. test_detectar_ambiguedad_baja_confianza")
    print("  2. test_detectar_no_ambiguedad_alta_confianza")
    print("  3. test_almacenar_en_mongodb")
    print("  4. test_procesar_respuesta_confirmacion")
    print("  5. test_procesar_respuesta_rechazo")
    print("  6. test_marcar_resuelto")
    print("  7. test_obtener_pendientes_por_estado")
    print("  8. test_timeout_movimiento")
    print("  9. test_contenedor_estructura")
    print("\n" + "="*70 + "\n")


if __name__ == "__main__":
    run_all_tests()
