---
phase: quick
plan: 260402-1hh
subsystem: auditoria
tags: [auditoria, alegra, bills, duplicados, paginacion]
dependency_graph:
  requires: [backend/routers/auditoria.py, backend/alegra_service.py, backend/permissions.py]
  provides: [GET /api/auditoria/alegra-completo, POST /api/auditoria/aprobar-limpieza, POST /api/auditoria/anular-bill-duplicada]
  affects: [Alegra bills, MongoDB auditoria_aprobaciones, MongoDB roddos_events]
tech_stack:
  added: []
  patterns: [httpx-raw-direct-bypass, tdd-red-green, pagination-exhaustive, event-sourcing-audit]
key_files:
  created:
    - backend/tests/test_fase1_auditoria.py
  modified:
    - backend/routers/auditoria.py
decisions:
  - httpx raw directo en anular-bill-duplicada para bypasear validate_delete_protection() — igual que eliminar-journal existente
  - _get_alegra_auth_headers() lee ALEGRA_EMAIL/ALEGRA_TOKEN de env vars primero, luego MongoDB fallback
  - evento registrado en roddos_events ANTES del DELETE para garantizar trazabilidad aunque el DELETE falle
  - tests usan importlib.util para cargar auditoria.py directamente y evitar routers/__init__.py que importa qrcode
metrics:
  duration: 558s
  completed: 2026-04-01
  tasks_completed: 3
  files_changed: 2
---

# Quick Task 260402-1hh: Fase 1 Auditoria Completa de Alegra Summary

**One-liner:** Paginacion exhaustiva de Alegra (invoices/bills/journals) con clasificacion, deteccion de bills duplicadas Auteco y endpoints de aprobacion/anulacion trazados en MongoDB.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Tests T1-T7 (RED) | 947796d | backend/tests/test_fase1_auditoria.py |
| 2 | GET alegra-completo + clasificacion + duplicados (T1-T3 GREEN) | b793d75 | backend/routers/auditoria.py |
| 3 | POST aprobar-limpieza + anular-bill-duplicada (T4-T7 GREEN) | f38bd70 | backend/routers/auditoria.py, tests |

## What Was Built

### backend/routers/auditoria.py — 3 nuevos endpoints

**GET /api/auditoria/alegra-completo**
- Pagina TODOS los registros de Alegra con limit=100 hasta agotar (no asume 30 como total)
- Clasifica invoices: `facturas_venta` (tienen "VIN:") vs `facturas_venta_sin_vin`
- Clasifica bills: `compras_auteco` (NIT 860024781) vs `compras_otro_proveedor`
- Clasifica journals: `journals_gasto` (cuenta 5xxx con debit) / `journals_ingreso` (cuenta 4xxx con credit) / `journals_otro`
- Detecta duplicados Auteco: misma (numero_factura, monto) → alerta `bill_duplicada`

**POST /api/auditoria/aprobar-limpieza**
- `confirmado=False`: retorna plan sin ejecutar, NO escribe en MongoDB
- `confirmado=True`: inserta en `auditoria_aprobaciones` con `aprobado_por`, `timestamp`, `excluir_ids`, `status: aprobado_pendiente_ejecucion`

**POST /api/auditoria/anular-bill-duplicada**
- Verifica existencia de ambas bills en Alegra via GET /bills/{id}
- Registra evento `bill_duplicada_anulada` en `roddos_events` ANTES del DELETE
- Ejecuta DELETE via httpx directo (bypasea `validate_delete_protection()`)
- `validate_delete_protection()` NO se modifico — bills siguen protegidas para agentes automaticos

### backend/tests/test_fase1_auditoria.py — 7 tests

- T1: Estructura de respuesta alegra-completo (todas las keys)
- T2: Clasificacion VIN vs sin VIN en invoices
- T3: Deteccion duplicados Auteco por (numero + monto)
- T4: aprobar-limpieza confirmado=False no escribe en MongoDB
- T5: aprobar-limpieza confirmado=True inserta en auditoria_aprobaciones
- T6: anular-bill-duplicada retorna 404 para bill inexistente
- T7: anular-bill-duplicada exitoso inserta evento en roddos_events

## Verification

```
7/7 tests PASS GREEN
grep app.alegra.com/api/r1 auditoria.py → solo en comentarios (0 en codigo real)
grep journal-entries auditoria.py → solo en comentarios (0 en codigo real)
grep 5495 auditoria.py → 0 resultados
```

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Tests usaban importacion via routers/__init__.py que falla por qrcode faltante**
- **Found during:** Task 1
- **Issue:** `from routers.auditoria import ...` triggera `routers/__init__.py` que importa `auth.py` que importa `qrcode` — no instalado en entorno de test
- **Fix:** `importlib.util.spec_from_file_location` para cargar `routers/auditoria.py` directamente, con stubs previos para `database`, `dependencies`, `alegra_service`
- **Files modified:** backend/tests/test_fase1_auditoria.py

**2. [Rule 1 - Bug] URL de endpoints en tests era /api/... en vez de /api/auditoria/...**
- **Found during:** Task 3
- **Issue:** Router tiene prefix="/auditoria", y el app usa prefix="/api", por lo que la ruta completa es /api/auditoria/aprobar-limpieza — los tests usaban /api/aprobar-limpieza
- **Fix:** Corregido URLs en tests T4-T7
- **Files modified:** backend/tests/test_fase1_auditoria.py

**3. [Rule 1 - Bug] T6 fallaba por db.alegra_credentials.find_one siendo MagicMock en vez de AsyncMock**
- **Found during:** Task 3, iteracion de T6
- **Issue:** `_get_alegra_auth_headers()` hace fallback a MongoDB cuando env vars estan vacias. T6 no seteaba ALEGRA_EMAIL/TOKEN ni habia configurado AsyncMock para la DB
- **Fix:** Agregar `patch.dict(os.environ, {"ALEGRA_EMAIL": ..., "ALEGRA_TOKEN": ...})` en T6 (mismo patron que T7)
- **Files modified:** backend/tests/test_fase1_auditoria.py

## Known Stubs

Ninguno — los 3 endpoints estan completamente funcionales con logica real.

## Self-Check: PASSED
