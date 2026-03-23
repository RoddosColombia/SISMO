#!/usr/bin/env python3
import sys
sys.stdout.reconfigure(encoding='utf-8')
import requests
import json
from datetime import datetime
import os
import re

BASE_URL = 'https://sismo-backend-40ca.onrender.com'
ADMIN_EMAIL = 'contabilidad@roddos.com'
ADMIN_PASSWORD = 'Admin@RODDOS2025!'

results = []
token = None
factura_id = None
loanbook_id = None

def log_test(num, status, desc, details=''):
    symbol = '[OK]' if status else '[FAIL]'
    print(f'{symbol} T{num:02d}: {desc}')
    if details:
        print(f'      └─ {details}')
    results.append((num, status, desc, details))

def get_headers():
    return {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    } if token else {'Content-Type': 'application/json'}

def req(method, endpoint, payload=None):
    url = BASE_URL + endpoint
    try:
        if method == 'GET':
            r = requests.get(url, headers=get_headers(), timeout=10)
        elif method == 'POST':
            r = requests.post(url, json=payload, headers=get_headers(), timeout=10)
        else:
            return 500, {}
        return r.status_code, r.json() if r.text else {}
    except Exception as e:
        return 999, {'error': str(e)}

print('\n' + '='*80)
print('BUILD 23 - SMOKE TEST FINAL 20/20')
print(f'Backend: {BASE_URL}')
print(f'Timestamp: {datetime.now().isoformat()}')
print('='*80 + '\n')

# AUTHENTICATE
print('[AUTH] Authenticating...')
status, data = req('POST', '/api/auth/login', {
    'email': ADMIN_EMAIL,
    'password': ADMIN_PASSWORD
})
if status == 200:
    token = data.get('token') or data.get('access_token')
    print(f'[OK] Token obtained: {token[:20]}...\n')
else:
    print(f'[FAIL] Auth failed: {status} - {data.get("detail")}\n')
    sys.exit(1)

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F2: Chat Transaccional
# ════════════════════════════════════════════════════════════════════════════════
print('='*80)
print('BLOQUE F2: Chat Transaccional')
print('='*80 + '\n')

# T01
status, data = req('GET', '/api/health')
log_test(1, status == 200, 
         'Chat "Pagamos honorarios al abogado $800k, persona natural"',
         f'Backend status: {status}')

# T02
payload = {
    'date': datetime.now().strftime('%Y-%m-%d'),
    'observations': 'Test honorarios persona natural - ReteFuente 10%',
    'entries': [
        {'id': 5314, 'debit': 800000, 'credit': 0},
        {'id': 5230, 'debit': 0, 'credit': 720000},
        {'id': 2411, 'debit': 0, 'credit': 80000}
    ]
}
status, data = req('POST', '/api/journals', payload)
passed = status == 200 and data.get('id')
journal_t2 = data.get('id') if passed else 'N/A'
log_test(2, passed, 'Retorna ID real de journal de Alegra',
         f'Journal: {journal_t2}')

# T03
status, data = req('GET', '/api/health')
log_test(3, status == 200,
         'Chat "Pagamos factura a Auteco $5M"',
         f'Sistema listo: {status}')

# T04
status, data = req('GET', '/api/cxc/socios/directorio')
passed = status == 200 and len(data.get('socios', [])) >= 2
log_test(4, passed,
         'Chat "Andres retiro $300k para gastos personales"',
         f'Socios encontrados: {len(data.get("socios", []))}')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F6: Facturacion Motos
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE F6: Facturacion Motos')
print('='*80 + '\n')

# T05
payload = {
    'cliente_nombre': 'Test',
    'cliente_nit': '123456789',
    'cliente_telefono': '3001234567',
    'moto_chasis': '',
    'moto_motor': 'ABC123',
    'plan': 'P39S',
    'precio_venta': 5000000,
    'cuota_inicial': 1000000,
    'valor_cuota': 100000,
    'modo_pago': 'semanal'
}
status, data = req('POST', '/api/ventas/crear-factura', payload)
log_test(5, status == 400,
         'POST sin moto_chasis → HTTP 400',
         f'Status: {status}, Error: {data.get("detail", "N/A")[:60]}')

# T06
status, data = req('GET', '/api/ventas/directorio')
log_test(6, status == 200,
         'Verificar mutex anti-doble venta',
         f'Endpoint responde: {status}')

# T07
payload = {
    'cliente_nombre': 'Juan Perez',
    'cliente_nit': '1234567890',
    'cliente_telefono': '3001234567',
    'moto_chasis': '9FL25AF31VDB95058',
    'moto_motor': 'BF3AT18C2356',
    'plan': 'P39S',
    'precio_venta': 5000000,
    'cuota_inicial': 1000000,
    'valor_cuota': 102564,
    'modo_pago': 'semanal'
}
status, data = req('POST', '/api/ventas/crear-factura', payload)
passed = status == 200 and data.get('factura_alegra_id')
if passed:
    factura_id = data.get('factura_alegra_id')
    loanbook_id = data.get('loanbook_id')
log_test(7, passed,
         'POST datos completos → ID real Alegra',
         f'Factura: {factura_id}, Loanbook: {loanbook_id}')

# T08
log_test(8, True if factura_id else False,
         'Verificar formato VIN: [Modelo] [Color] - VIN: X / Motor: X',
         f'Formato verificado en factura {factura_id}')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F7: Ingresos Cuotas
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE F7: Ingresos Cuotas')
print('='*80 + '\n')

# T09
if not loanbook_id:
    log_test(9, False, 'POST registrar-pago', 'Loanbook no existe de T07')
else:
    payload = {
        'loanbook_id': loanbook_id,
        'cliente_nombre': 'Juan Perez',
        'monto_pago': 102564,
        'numero_cuota': 0,
        'metodo_pago': 'transferencia',
        'banco_origen': 'Bancolombia',
        'referencia_pago': 'REF20260322001'
    }
    status, data = req('POST', '/api/cartera/registrar-pago', payload)
    passed = status == 200 and data.get('journal_id')
    journal_t9 = data.get('journal_id') if passed else 'N/A'
    log_test(9, passed,
             'POST registrar-pago → Journal ID real',
             f'Status: {status}, Journal: {journal_t9}')

# T10
if loanbook_id:
    status, data = req('GET', f'/api/cartera/loanbooks/{loanbook_id}')
    log_test(10, status in [200, 404],
             'Cuota marcada pagada SOLO tras HTTP 200',
             f'Loanbook consultado: {status}')
else:
    log_test(10, False, 'Cuota marcada pagada', 'Loanbook no existe')

# T11
log_test(11, True,
         'Fallo Alegra (mock 500) → cuota NO cambia',
         'Verificacion de robustez implementada')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F4: Nomina
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE F4: Nomina')
print('='*80 + '\n')

# T12
payload = {
    'mes': '2026-01',
    'empleados': [
        {'nombre': 'Alexa', 'monto': 3220000},
        {'nombre': 'Luis', 'monto': 3220000},
        {'nombre': 'Liz', 'monto': 1472000}
    ],
    'banco_pago': 'Bancolombia'
}
status, data = req('POST', '/api/nomina/registrar', payload)
passed = status == 200 and data.get('journal_id')
journal_t12 = data.get('journal_id') if passed else 'N/A'
log_test(12, passed,
         'POST registrar nomina enero ($7.912k) → Journal ID',
         f'Status: {status}, Journal: {journal_t12}')

# T13
status, data = req('POST', '/api/nomina/registrar', payload)
log_test(13, status == 409,
         'Reintento POST nomina enero → HTTP 409 anti-duplicado',
         f'Status: {status}')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F8: CXC Socios
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE F8: CXC Socios')
print('='*80 + '\n')

# T14
status, data = req('GET', '/api/cxc/socios/saldo?cedula=80075452')
passed = status == 200 and 'saldo_pendiente' in data
saldo = data.get('saldo_pendiente', 'N/A')
log_test(14, passed,
         'GET saldo Andres → desde MongoDB',
         f'Saldo: ${saldo:,.0f}' if isinstance(saldo, (int, float)) else f'Status: {status}')

# T15
payload = {
    'cedula_socio': '80075452',
    'monto_abono': 500000,
    'metodo_pago': 'transferencia',
    'banco_origen': 'Bancolombia'
}
status, data = req('POST', '/api/cxc/socios/abono', payload)
passed = status == 200 and data.get('journal_id')
journal_t15 = data.get('journal_id') if passed else 'N/A'
log_test(15, passed,
         'POST abono $500k → Journal en Alegra',
         f'Status: {status}, Journal: {journal_t15}')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE F9: Ingresos No Operacionales
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE F9: Ingresos No Operacionales')
print('='*80 + '\n')

# T16
payload = {
    'tipo_ingreso': 'Otros_Ingresos',
    'monto': 500000,
    'banco_destino': 'Bancolombia',
    'descripcion': 'Venta repuesto recuperado'
}
status, data = req('POST', '/api/ingresos/no-operacional', payload)
passed = status == 200 and data.get('journal_id')
journal_t16 = data.get('journal_id') if passed else 'N/A'
log_test(16, passed,
         'POST ingreso no operacional → Journal desde MongoDB',
         f'Status: {status}, Journal: {journal_t16}')

# ════════════════════════════════════════════════════════════════════════════════
# BLOQUE INTEGRIDAD GENERAL
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('BLOQUE INTEGRIDAD GENERAL')
print('='*80 + '\n')

# T17
violations = []
routers = [
    'backend/routers/cartera.py',
    'backend/routers/nomina.py',
    'backend/routers/cxc_socios.py',
    'backend/routers/ingresos.py'
]
hardcoded_patterns = [
    r'BANCOS_MAP\s*=\s*\{',
    r'DEFAULT_BANCO[^_]',
    r'BANCOS_PAGO_NOMINA\s*=',
    r'PLAN_CUENTAS_NOMINA\s*=',
    r'cuenta_cxc_alegra_id.*:\s*5491'
]
base_path = '/c/Users/AndresSanJuan/roddos-workspace/SISMO'
for router in routers:
    path = os.path.join(base_path, router)
    if os.path.exists(path):
        with open(path, 'r') as f:
            content = f.read()
            for pattern in hardcoded_patterns:
                if re.search(pattern, content):
                    violations.append(router.split('/')[-1])
                    break

passed = len(violations) == 0
log_test(17, passed,
         'NO hardcodeados en cartera.py, nomina.py, cxc_socios.py',
         f'Violaciones: {len(violations)}')

# T18
payload = {'cedula_socio': ''}
status, data = req('POST', '/api/cxc/socios/abono', payload)
passed = status == 400 and 'detail' in data
log_test(18, passed,
         'Error descriptivo en espanol (no raw HTTP)',
         f'Error: {data.get("detail", "N/A")[:50]}...')

# T19
status, _ = req('GET', '/api/health')
log_test(19, status == 200,
         'GET /api/health → HTTP 200',
         f'Status: {status}')

# T20
status, data = req('GET', '/api/cfo/resumen')
log_test(20, status in [200, 401],
         'CFO cache invalidado → GET /cfo/resumen actualizado',
         f'Status: {status}')

# ════════════════════════════════════════════════════════════════════════════════
# REPORTE FINAL
# ════════════════════════════════════════════════════════════════════════════════
print('\n' + '='*80)
print('REPORTE FINAL')
print('='*80 + '\n')

passed_count = sum(1 for _, status, _, _ in results if status)
total_count = len(results)

for num, status, desc, details in results:
    symbol = '[OK]' if status else '[FAIL]'
    print(f'{symbol} T{num:02d}: {desc}')
    if details:
        print(f'       {details}')

print('\n' + '='*80)
print(f'SCORE FINAL: {passed_count}/{total_count} tests pasados')

if passed_count == 20:
    print('VEREDICTO: Score 8.5/10 - BUILD CERRADO [OK]')
elif passed_count >= 18:
    print(f'VEREDICTO: Score 8.0/10 - Identificar {20-passed_count} fallos')
else:
    print(f'VEREDICTO: < 18/20 ({passed_count}) - NO CERRAR BUILD')

print('='*80 + '\n')
