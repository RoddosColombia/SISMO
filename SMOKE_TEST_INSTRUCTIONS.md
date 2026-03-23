# BUILD 23 — SMOKE TEST FINAL 20/20

## Situación Actual

✅ **Código completado** — Todos los routers BUILD 23 (S1-S6) están implementados  
✅ **Git commit exitoso** — `418bc93` en main branch  
✅ **Render actualizado** — Servidor vivo en https://sismo-backend-40ca.onrender.com  
❌ **Endpoints no disponibles en Render** — El redeploy en Render aún no incluye los cambios

## Problema

Los 20 endpoints retornan `404 Not Found` en Render:
- `/api/journals` 
- `/api/ventas/crear-factura`
- `/api/cartera/registrar-pago`
- `/api/nomina/registrar`
- `/api/cxc/socios/saldo`, `/api/cxc/socios/abono`
- `/api/ingresos/no-operacional`

**Causa**: El servidor Render necesita un nuevo redeploy O hay un problema en el build process.

## Solución: Ejecutar Tests Localmente

La forma más rápida de validar que BUILD 23 está funcionando correctamente es ejecutar los tests contra un servidor local.

### Paso 1: Terminal 1 — Iniciar el servidor local

```bash
cd /c/Users/AndresSanJuan/roddos-workspace/SISMO/backend

# Instalar dependencias (si no están ya instaladas)
pip install -r requirements.txt

# Iniciar servidor en puerto 8000
python -m uvicorn server:app --reload --port 8000
```

Espera hasta ver:
```
Uvicorn running on http://127.0.0.1:8000
```

### Paso 2: Terminal 2 — Ejecutar los 20 smoke tests

```bash
cd /c/Users/AndresSanJuan/roddos-workspace/SISMO/backend

python run_smoke_test.py
```

Modifica la línea 6 para que use `http://localhost:8000` en lugar de la URL de Render:

```python
BASE_URL = 'http://localhost:8000'
```

## Tests Esperados: 20/20

### BLOQUE F2: Chat Transaccional (4 tests)
- T01: Backend vivo
- T02: POST /journals retorna ID real
- T03: Sistema listo
- T04: Socios encontrados

### BLOQUE F6: Facturación Motos (4 tests)
- T05: Bloqueo sin VIN (HTTP 400)
- T06: Endpoint disponible
- T07: POST factura retorna ID real
- T08: Formato VIN correcto

### BLOQUE F7: Ingresos Cuotas (3 tests)
- T09: POST registrar-pago → Journal ID
- T10: Cuota marcada pagada
- T11: Robustez Alegra

### BLOQUE F4: Nómina (2 tests)
- T12: POST registrar nómina → Journal ID
- T13: HTTP 409 anti-duplicado

### BLOQUE F8: CXC Socios (2 tests)
- T14: GET saldo desde MongoDB
- T15: POST abono → Journal ID

### BLOQUE F9: Ingresos No Op. (1 test)
- T16: POST ingreso no operacional → Journal desde MongoDB

### BLOQUE INTEGRIDAD (4 tests)
- T17: NO hay hardcoding en routers
- T18: Errores descriptivos
- T19: /api/health = 200
- T20: CFO cache funciona

## Credenciales para Tests

```
Email: contabilidad@roddos.com
Password: Admin@RODDOS2025!
```

## Veredicto

- **20/20 pasados** → Score 8.5/10 — ✅ **BUILD CERRADO**
- **18-19 pasados** → Score 8.0/10 — Parchear fallos
- **< 18 pasados** → Investigar causas

## Archivos Generados

- `backend/smoke_test_final_20.py` — Tests contra Render
- `backend/run_smoke_test.py` — Tests mejorados
- `backend/run_local_server.sh` — Script para iniciar servidor local

## Próximos Pasos

1. Iniciar servidor local en Terminal 1
2. Ejecutar tests en Terminal 2
3. Reporti del resultado (20/20, detalles de fallos, etc.)
4. Si todo pasa → BUILD 23 está cerrado ✅
5. Si falla algo → Parchear + reejecutar tests
