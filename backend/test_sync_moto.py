#!/usr/bin/env python3
"""
Test: Sincronizar moto facturada en Alegra
Llamada HTTP al endpoint POST /api/sync/moto/urgente
"""

import requests
import json
from datetime import datetime

# Configuración
BASE_URL = "http://localhost:8000"  # Cambiar si es diferente
ENDPOINT = f"{BASE_URL}/api/sync/moto/urgente"

# Datos de la moto a sincronizar
MOTO_DATA = {
    "chasis": "9FL25AF31VDB95190",
    "factura_id": "FE456",
    "cliente": "KEDWYNG VALLADARES"
}

# Headers con autenticación
HEADERS = {
    "Content-Type": "application/json",
    # Agregar token de autenticación si es necesario
    # "Authorization": "Bearer YOUR_TOKEN"
}

def sincronizar_moto():
    """Ejecutar sincronización de moto."""

    print("\n" + "="*80)
    print("SINCRONIZACIÓN MANUAL — MOTO FACTURADA EN ALEGRA")
    print("="*80)

    print(f"\n📍 Endpoint: POST {ENDPOINT}")
    print(f"\n📊 Datos a sincronizar:")
    print(f"   Chasis: {MOTO_DATA['chasis']}")
    print(f"   Factura Alegra: {MOTO_DATA['factura_id']}")
    print(f"   Cliente: {MOTO_DATA['cliente']}")

    print(f"\n⏳ Enviando solicitud...")

    try:
        response = requests.post(
            ENDPOINT,
            json=MOTO_DATA,
            headers=HEADERS,
            timeout=30
        )

        print(f"✓ Respuesta recibida (HTTP {response.status_code})")

        if response.status_code == 200:
            data = response.json()

            print("\n" + "="*80)
            print("✅ SINCRONIZACIÓN COMPLETADA EXITOSAMENTE")
            print("="*80)

            print(f"\n📊 ESTADO INVENTARIO_MOTOS:")
            print(f"\n  ANTES:")
            for key, value in data.get('estado_antes', {}).items():
                print(f"    {key}: {value}")

            print(f"\n  DESPUÉS:")
            for key, value in data.get('estado_despues', {}).items():
                print(f"    {key}: {value}")

            print(f"\n📦 LOANBOOK:")
            print(f"    ID: {data.get('loanbook_id')}")
            print(f"    Código: {data.get('loanbook_codigo')}")
            print(f"    Estado: pendiente_entrega")

            print(f"\n🎯 INFORMACIÓN SINCRONIZADA:")
            print(f"    Chasis: {MOTO_DATA['chasis']}")
            print(f"    Factura: {MOTO_DATA['factura_id']}")
            print(f"    Cliente: {MOTO_DATA['cliente']}")
            print(f"    Timestamp: {data.get('timestamp')}")

            print("\n" + "="*80 + "\n")

        else:
            print(f"\n❌ Error: {response.status_code}")
            print(f"   Respuesta: {response.text}")

    except requests.exceptions.ConnectionError:
        print("\n❌ Error de conexión")
        print(f"   No se pudo conectar a {BASE_URL}")
        print("\n   Opciones:")
        print("   1. Verificar que el servidor esté corriendo")
        print("   2. Cambiar BASE_URL si es diferente")
        print("   3. Verificar la URL del servidor")

    except requests.exceptions.Timeout:
        print("\n❌ Timeout")
        print(f"   El servidor tardó más de 30 segundos en responder")

    except Exception as e:
        print(f"\n❌ Error: {str(e)}")

if __name__ == "__main__":
    sincronizar_moto()
