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
            print(f"+ Authenticated")
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
            self.results["errors"].append(f"{name}: {status}")
        journal_id = data.get("journal_id") or data.get("factura_alegra_id")
        info = f" [ID: {journal_id}]" if journal_id else ""
        print(f"{symbol} {name:<55} {status}{info}")
        return success

    def run_all_tests(self):
        if not self.authenticate():
            return False
        print("\n=== BUILD 23 ENDPOINTS ===\n")
        
        # F6 - Ventas
        self.test_endpoint("F6-1: POST /ventas/crear-factura (validation fail)", "POST", "/ventas/crear-factura",
            {"cliente_nombre": "", "moto_chasis": "", "moto_motor": ""}, expected_status=400)
        
        # F7 - Cartera
        self.test_endpoint("F7-1: POST /cartera/registrar-pago (validation fail)", "POST", "/cartera/registrar-pago",
            {"loanbook_id": "", "monto_pago": 0}, expected_status=400)
        self.test_endpoint("F7-2: GET /cartera/bancos", "GET", "/cartera/bancos")
        self.test_endpoint("F7-3: GET /cartera/plan-ingresos", "GET", "/cartera/plan-ingresos")
        
        # F8 - CXC Socios
        self.test_endpoint("F8-1: GET /cxc/socios/saldo", "GET", "/cxc/socios/saldo")
        self.test_endpoint("F8-2: POST /cxc/socios/abono (validation fail)", "POST", "/cxc/socios/abono",
            {"socio": "", "monto": 0}, expected_status=400)
        self.test_endpoint("F8-3: GET /cxc/socios/bancos", "GET", "/cxc/socios/bancos")
        
        # F4 - Nomina
        self.test_endpoint("F4-1: GET /nomina/historial", "GET", "/nomina/historial")
        self.test_endpoint("F4-2: GET /nomina/plan-cuentas", "GET", "/nomina/plan-cuentas")
        
        # F9 - Ingresos
        self.test_endpoint("F9-1: GET /ingresos/bancos", "GET", "/ingresos/bancos")
        self.test_endpoint("F9-2: GET /ingresos/plan-ingresos", "GET", "/ingresos/plan-ingresos")
        
        print(f"\n=== RESULTS ===")
        print(f"Passed: {self.results['passed']}/{self.results['passed']+self.results['failed']}")
        if self.results['failed'] > 0:
            print(f"Failed: {self.results['failed']}")
            for error in self.results['errors'][:15]:
                print(f"  X {error}")
        return self.results['failed'] == 0

if __name__ == "__main__":
    tester = SmokeTester()
    success = tester.run_all_tests()
    sys.exit(0 if success else 1)
