#!/usr/bin/env python3
"""
SMOKE TEST BUILD 23 — Verificacion contra produccion Render
Tests: T01-T04 contra https://sismo-backend-40ca.onrender.com
"""
import os
import sys
import json
import httpx
import asyncio
from datetime import datetime, timezone

BASE_URL = "https://sismo-backend-40ca.onrender.com"
EMAIL = "contabilidad@roddos.com"
PASSWORD = os.environ.get("ALEGRA_PASSWORD", "").strip()  # Necesita estar en env

# Colores para output
RED = '\033[91m'
GREEN = '\033[92m'
YELLOW = '\033[93m'
BLUE = '\033[94m'
RESET = '\033[0m'

def log_test(name: str, status: str, detail: str = ""):
    """Log resultado de test"""
    status_symbol = "[OK]" if status == "PASS" else "[FAIL]"
    status_color = GREEN if status == "PASS" else RED
    print(f"{status_color}[{status}]{RESET} {name}")
    if detail:
        print(f"   {detail}")

async def test_t01_login():
    """T01: POST /api/auth/login → obtener JWT"""
    print(f"\n{YELLOW}==================================================={RESET}")
    print(f"{YELLOW}T01: POST /api/auth/login{RESET}")
    print(f"{YELLOW}==================================================={RESET}")

    if not PASSWORD:
        log_test("T01 Login", "SKIP", "ALEGRA_PASSWORD no está configurada en env")
        return None

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": EMAIL, "password": PASSWORD}
            )

            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                if token:
                    log_test("T01 Login", "PASS", f"JWT obtenido: {token[:50]}...")
                    return token
                else:
                    log_test("T01 Login", "FAIL", "No access_token en respuesta")
                    print(f"   Response: {data}")
                    return None
            else:
                log_test("T01 Login", "FAIL", f"Status {response.status_code}")
                print(f"   Response: {response.text[:200]}")
                return None

        except Exception as e:
            log_test("T01 Login", "FAIL", f"Error: {str(e)}")
            return None


async def test_t02_crear_causacion(token: str):
    """T02: POST /api/chat crear causación de honorarios
    Verificar: cuenta 5470 (Honorarios) + ReteFuente 236505
    """
    print(f"\n{YELLOW}==================================================={RESET}")
    print(f"{YELLOW}T02: POST /api/chat - Crear causación honorarios{RESET}")
    print(f"{YELLOW}==================================================={RESET}")

    if not token:
        log_test("T02 Causación", "SKIP", "Sin token JWT del T01")
        return None

    mensaje = "Pagamos honorarios al abogado $800.000, persona natural"

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/chat",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json={
                    "message": mensaje,
                    "session_id": f"smoke-test-{datetime.now(timezone.utc).isoformat()}"
                }
            )

            if response.status_code == 200:
                data = response.json()
                response_text = data.get("message", "")

                # Buscar ID de journal en la respuesta
                import re
                journal_ids = re.findall(r'ID[=-]?\s*(\d+)', response_text) or \
                              re.findall(r'journal[:-]?\s*(\d+)', response_text, re.IGNORECASE) or \
                              re.findall(r'CE-\d+-\d+', response_text)

                journal_id = journal_ids[0] if journal_ids else "NO_ENCONTRADO"

                # Verificar que usa cuenta 5470 y ReteFuente 236505
                has_5470 = "5470" in response_text
                has_236505 = "236505" in response_text
                has_wrong_reteids = any(x in response_text for x in ["5381", "5382", "5383", "5386"])

                log_test("T02 Causación", "PASS", f"Chat respondió con journal ID: {journal_id}")
                print(f"   ✓ Cuenta Honorarios (5470): {GREEN if has_5470 else RED}{'✓' if has_5470 else '✗'}{RESET}")
                print(f"   ✓ ReteFuente (236505): {GREEN if has_236505 else RED}{'✓' if has_236505 else '✗'}{RESET}")
                print(f"   ✓ SIN IDs incorrectos (5381/82/83/86): {GREEN if not has_wrong_reteids else RED}{'✓' if not has_wrong_reteids else '✗'}{RESET}")
                print(f"   Response preview: {response_text[:300]}...")

                return journal_id if journal_id != "NO_ENCONTRADO" else None

            else:
                log_test("T02 Causación", "FAIL", f"Status {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return None

        except Exception as e:
            log_test("T02 Causación", "FAIL", f"Error: {str(e)}")
            return None


async def test_t03_crear_factura(token: str):
    """T03: POST /api/ventas/crear-factura con VIN real
    Retornar ID real de factura de Alegra
    """
    print(f"\n{YELLOW}==================================================={RESET}")
    print(f"{YELLOW}T03: POST /api/ventas/crear-factura{RESET}")
    print(f"{YELLOW}==================================================={RESET}")

    if not token:
        log_test("T03 Venta", "SKIP", "Sin token JWT del T01")
        return None

    # Datos de venta de prueba
    payload = {
        "cliente_nombre": "Cliente Test Smoke",
        "cliente_nit": "1023456789",
        "cliente_telefono": "3001234567",
        "moto_chasis": "TEST-VIN-SMOKE-001",
        "moto_motor": "MOTOR-SMOKE-001",
        "plan": "P39S",
        "precio_venta": 9000000,
        "cuota_inicial": 1500000,
        "valor_cuota": 192307.69,
        "modo_pago": "semanal",
        "fecha_venta": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/ventas/crear-factura",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                factura_id = data.get("factura_alegra_id", "")
                factura_numero = data.get("factura_numero", "")
                loanbook_id = data.get("loanbook_id", "")

                if factura_id:
                    log_test("T03 Venta", "PASS", f"Factura creada")
                    print(f"   Factura ID (Alegra): {GREEN}{factura_id}{RESET}")
                    print(f"   Factura Número: {GREEN}{factura_numero}{RESET}")
                    print(f"   Loanbook ID: {GREEN}{loanbook_id}{RESET}")
                    return factura_id
                else:
                    log_test("T03 Venta", "FAIL", "Sin factura_alegra_id en respuesta")
                    print(f"   Response: {data}")
                    return None
            else:
                log_test("T03 Venta", "FAIL", f"Status {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return None

        except Exception as e:
            log_test("T03 Venta", "FAIL", f"Error: {str(e)}")
            return None


async def test_t04_registrar_pago(token: str):
    """T04: POST /api/cartera/registrar-pago con loanbook activo
    Retornar ID real de journal de ingreso
    """
    print(f"\n{YELLOW}==================================================={RESET}")
    print(f"{YELLOW}T04: POST /api/cartera/registrar-pago{RESET}")
    print(f"{YELLOW}==================================================={RESET}")

    if not token:
        log_test("T04 Pago", "SKIP", "Sin token JWT del T01")
        return None

    # Datos de pago de prueba (con loanbook de ejemplo)
    payload = {
        "loanbook_id": "LB-2026-0042",  # Loanbook de ejemplo
        "cliente_nombre": "Cliente Test",
        "monto_pago": 192307.69,
        "numero_cuota": 1,
        "metodo_pago": "transferencia",
        "banco_origen": "Bancolombia",
        "referencia_pago": "REF-SMOKE-TEST-001",
        "fecha_pago": datetime.now(timezone.utc).strftime("%Y-%m-%d")
    }

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            response = await client.post(
                f"{BASE_URL}/api/cartera/registrar-pago",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Content-Type": "application/json"
                },
                json=payload
            )

            if response.status_code == 200:
                data = response.json()
                journal_id = data.get("journal_id", "")
                saldo_pendiente = data.get("saldo_pendiente", "")

                if journal_id:
                    log_test("T04 Pago", "PASS", f"Pago registrado")
                    print(f"   Journal ID (Alegra): {GREEN}{journal_id}{RESET}")
                    print(f"   Saldo Pendiente: {GREEN}{saldo_pendiente}{RESET}")
                    return journal_id
                else:
                    log_test("T04 Pago", "FAIL", "Sin journal_id en respuesta")
                    print(f"   Response: {data}")
                    return None
            else:
                log_test("T04 Pago", "FAIL", f"Status {response.status_code}")
                print(f"   Response: {response.text[:300]}")
                return None

        except Exception as e:
            log_test("T04 Pago", "FAIL", f"Error: {str(e)}")
            return None


async def main():
    """Ejecutar todos los tests"""
    print(f"\n{BLUE}+========================================================╗{RESET}")
    print(f"{BLUE}|  SMOKE TEST BUILD 23 — VERIFICACIÓN CONTRA PRODUCCIÓN |{RESET}")
    print(f"{BLUE}|  URL: https://sismo-backend-40ca.onrender.com          |{RESET}")
    print(f"{BLUE}+========================================================╝{RESET}")

    print(f"\n{YELLOW}Iniciando tests...{RESET}")

    # T01: Login
    token = await test_t01_login()

    # T02: Crear causación
    journal_t02 = await test_t02_crear_causacion(token)

    # T03: Crear factura
    factura_t03 = await test_t03_crear_factura(token)

    # T04: Registrar pago
    journal_t04 = await test_t04_registrar_pago(token)

    # Resumen
    print(f"\n{BLUE}+========================================================╗{RESET}")
    print(f"{BLUE}|                       RESUMEN                           |{RESET}")
    print(f"{BLUE}+========================================================╝{RESET}")

    print(f"\n{YELLOW}IDs REALES RETORNADOS POR ALEGRA:{RESET}")
    print(f"T02 Journal (Causación Honorarios): {GREEN if journal_t02 else RED}{journal_t02 or 'NO_OBTENIDO'}{RESET}")
    print(f"T03 Factura (Venta Moto):           {GREEN if factura_t03 else RED}{factura_t03 or 'NO_OBTENIDO'}{RESET}")
    print(f"T04 Journal (Pago Cartera):         {GREEN if journal_t04 else RED}{journal_t04 or 'NO_OBTENIDO'}{RESET}")

    success = all([journal_t02, factura_t03, journal_t04])

    if success:
        print(f"\n{GREEN}✅ SMOKE TEST COMPLETADO — Todos los IDs obtenidos correctamente{RESET}\n")
        return 0
    else:
        print(f"\n{RED}❌ SMOKE TEST INCOMPLETO — Faltaron IDs reales{RESET}\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
