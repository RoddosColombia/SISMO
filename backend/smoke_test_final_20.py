#!/usr/bin/env python3
import requests
import sys

BASE_URL = "https://sismo-backend-40ca.onrender.com"
LOGIN_EMAIL = "contabilidad@roddos.com"
LOGIN_PASSWORD = "Admin@RODDOS2025!"

class SmokeTester:
    def __init__(self):
        self.token = None
        self.results = {"passed": 0, "failed": 0, "errors": []}

    def authenticate(self):
        print("\n=== AUTHENTICATION ===")
        try:
            resp = requests.post(
                f"{BASE_URL}/api/auth/login",
                json={"email": LOGIN_EMAIL, "password": LOGIN_PASSWORD},
                timeout=10
            )
            if resp.status_code != 200:
                print(f"X Login failed: {resp.status_code}")
                return False

            data = resp.json()
            self.token = data.get('token') or data.get('access_token')
            if not self.token:
                print(f"X No token in response")
                return False

            print(f"+ Authenticated as {LOGIN_EMAIL}")
            return True
        except Exception as e:
            print(f"X Auth error: {str(e)[:100]}")
            return False

    def make_request(self, method, endpoint, payload=None):
        headers = {"Authorization": f"Bearer {self.token}"}
        url = f"{BASE_URL}/api{endpoint}"

        try:
            if method == "GET":
                resp = requests.get(url, headers=headers, timeout=10)
            elif method == "POST":
                resp = requests.post(url, json=payload, headers=headers, timeout=10)
            else:
                return None, "Unknown method"

            try:
                data = resp.json()
            except:
                data = {}
            return (resp.status_code, data)
        except Exception as e:
            return (None, str(e)[:100])

    def test_endpoint(self, name, method, endpoint, payload=None, expected_status=200):
        status, data = self.make_request(method, endpoint, payload)

        success = status == expected_status
        if success:
            self.results["passed"] += 1
            symbol = "+"
        else:
            self.results["failed"] += 1
            symbol = "X"
            self.results["errors"].append(f"{name}: expected {expected_status}, got {status}")

        journal_id = data.get("journal_id") or data.get("factura_alegra_id")
        info = f" [ID: {journal_id}]" if journal_id else ""

        print(f"{symbol} {name:<55} {status}{info}")
        return success

    def run_all_tests(self):
        if not self.authenticate():
            return False

        print("\n=== SMOKE TESTS (20/20) ===\n")

        self.test_endpoint("T1: GET /chat/historial", "GET", "/chat/historial")
        self.test_endpoint("T2: POST /chat/send-message", "POST", "/chat/send-message",
            {"message": "Test", "conversation_id": "test-smoke"})
        self.test_endpoint("T3: GET /ventas/historial", "GET", "/ventas/historial")
        self.test_endpoint("T4: GET /ventas/planes", "GET", "/ventas/planes")
        self.test_endpoint("T5: GET /ventas/estadisticas", "GET", "/ventas/estadisticas")
        self.test_endpoint("T6: GET /ventas/modelos", "GET", "/ventas/modelos")
        self.test_endpoint("T7: GET /cartera/plan-ingresos", "GET", "/cartera/plan-ingresos")
        self.test_endpoint("T8: GET /cartera/bancos", "GET", "/cartera/bancos")
        self.test_endpoint("T9: GET /cartera/historial", "GET", "/cartera/historial")
        self.test_endpoint("T10: GET /nomina/historial", "GET", "/nomina/historial")
        self.test_endpoint("T11: GET /nomina/plan-cuentas", "GET", "/nomina/plan-cuentas")
        self.test_endpoint("T12: POST /nomina/registrar (validation fail)", "POST", "/nomina/registrar",
            {"mes": "2026-03", "empleados": [], "banco_pago": "Bancolombia"}, expected_status=400)
        self.test_endpoint("T13: GET /cxc-socios/plan-cuentas", "GET", "/cxc-socios/plan-cuentas")
        self.test_endpoint("T14: GET /cxc-socios/bancos", "GET", "/cxc-socios/bancos")
        self.test_endpoint("T15: GET /cxc-socios/historial", "GET", "/cxc-socios/historial")
        self.test_endpoint("T16: GET /ingresos/plan-ingresos", "GET", "/ingresos/plan-ingresos")
        self.test_endpoint("T17: GET /ingresos/bancos", "GET", "/ingresos/bancos")
        self.test_endpoint("T18: GET /ingresos/historial", "GET", "/ingresos/historial")
        self.test_endpoint("T19: POST /ingresos/no-operacional (validation fail)", "POST", "/ingresos/no-operacional",
            {"tipo_ingreso": "Test", "monto": 0, "banco_destino": "Bancolombia"}, expected_status=400)
        self.test_endpoint("T20: GET /ingresos/historial (final)", "GET", "/ingresos/historial")

        print(f"\n=== RESULTS ===")
        print(f"Passed: {self.results['passed']}/20")
        if self.results['failed'] > 0:
            print(f"Failed: {self.results['failed']}/20")
            for error in self.results['errors'][:10]:
                print(f"  * {error}")
        else:
            print(f"+ All 20/20 tests passed!")
        
        return self.results['failed'] == 0

if __name__ == "__main__":
    tester = SmokeTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
