# Auditoria Alegra — SISMO BUILD 24

**Fecha:** 2026-03-30
**Fase:** 01-auditoria-alegra
**Ejecutor:** Claude (auditoria automatizada — Planes 01-01 y 01-02)
**Metodo:** Analisis estatico del codigo fuente + script HTTP (credenciales ausentes en entorno de ejecucion)

---

## 1. Arquitectura Actual

### Fuente de Verdad

**Archivo unico de comunicacion con Alegra:** `backend/alegra_service.py` (492 lineas)

La clase `AlegraService` reside **exclusivamente** en `backend/alegra_service.py`. Los siguientes archivos hipoteticos **NO EXISTEN** (confirmado con find):
- `backend/utils/alegra.py` — NO EXISTE
- `backend/services/alegra_service.py` — NO EXISTE

Solo 3 archivos tienen nombre `alegra*.py` en el proyecto:

| Archivo | Rol |
|---------|-----|
| `backend/alegra_service.py` | Fuente de verdad: clase AlegraService + ALEGRA_BASE_URL + todos los metodos HTTP |
| `backend/routers/alegra.py` | Router HTTP que expone endpoints REST al frontend |
| `backend/routers/alegra_webhooks.py` | Receptor de webhooks entrantes de Alegra |

### Clase AlegraService — Metodos Principales

| Metodo | Tipo | Descripcion |
|--------|------|-------------|
| `get_settings()` | async | Credenciales desde env vars > MongoDB > demo mode |
| `is_demo_mode()` | async | Retorna True si no hay credenciales reales |
| `get_auth_header()` | async | Encabezado Basic Auth para Alegra |
| `request()` | async | HTTP generico (GET/POST/PUT/DELETE) via ALEGRA_BASE_URL (linea 201) |
| `request_with_verify()` | async | POST + verificacion GET obligatoria (linea 274) |
| `retry_request()` | async | request() con reintentos para 429/503 (linea 316) |
| `check_duplicate_journal()` | async | Anti-duplicados via roddos_events MongoDB (linea 341) |
| `get_accounts_from_categories()` | async | GET /categories con cache 5 min |
| `get_cuenta_roddos()` | async | Busca cuenta en MongoDB roddos_cuentas |
| `test_connection()` | async | Verifica conexion con GET /company |

### Mapa de Imports

**Modulos de produccion que importan AlegraService:**

| Archivo | Linea | Importa | Uso |
|---------|-------|---------|-----|
| `backend/ai_chat.py` | 2588, 2852, 3830, 4513 | `AlegraService` / `AlegraService as _AS` | request(), request_with_verify() en acciones de chat |
| `backend/post_action_sync.py` | 34 | `AlegraService` | Sincronizacion post-accion |
| `backend/routers/alegra.py` | 7 | `AlegraService` | Router principal — todos los endpoints REST |
| `backend/routers/alegra_webhooks.py` | 18 | `ALEGRA_BASE_URL` | Acceso directo a URL (bypass parcial — ver Seccion 4) |
| `backend/routers/auditoria.py` | 14 | `ALEGRA_BASE_URL` | Acceso directo a URL (bypass parcial) |
| `backend/routers/cartera.py` | 16 | `AlegraService` | Operaciones de cartera |
| `backend/routers/cfo_estrategico.py` | 30 | `AlegraService` | CFO agente estrategico |
| `backend/routers/conciliacion.py` | 24, 706 | `ALEGRA_BASE_URL`, `AlegraService` | Conciliacion bancaria — bypass parcial + uso correcto |
| `backend/routers/cxc.py` | 24 | `AlegraService` | Cuentas por cobrar |
| `backend/routers/cxc_socios.py` | 16 | `AlegraService` | CXC socios |
| `backend/routers/dashboard.py` | 9 | `AlegraService` | KPIs dashboard |
| `backend/routers/estado_resultados.py` | 20 | `AlegraService` | Estado de resultados |
| `backend/routers/gastos.py` | 26 | `AlegraService` | Gestion de gastos |
| `backend/routers/ingresos.py` | 16 | `AlegraService` | Registro de ingresos |
| `backend/routers/inventory.py` | 8 | `AlegraService` | Inventario motos |
| `backend/routers/loanbook.py` | 9 | `AlegraService` | Ciclo de credito |
| `backend/routers/nomina.py` | 17 | `AlegraService` | Nomina mensual |
| `backend/routers/repuestos.py` | 9 | `AlegraService` | Repuestos |
| `backend/routers/settings.py` | 10 | `AlegraService` | Configuracion |
| `backend/routers/taxes.py` | 8 | `AlegraService` | Impuestos |
| `backend/routers/ventas.py` | 10 | `AlegraService` | Ventas |
| `backend/server.py` | 368 | `AlegraService` | Health check al startup |
| `backend/services/bank_reconciliation.py` | 26 | `ALEGRA_BASE_URL` | Acceso directo a URL (bypass parcial) |
| `backend/services/cfo_agent.py` | 74 | `AlegraService` | CFO analisis financiero |
| `backend/services/dian_service.py` | 17 | `ALEGRA_BASE_URL` | Acceso directo a URL (bypass parcial) |
| `backend/services/loanbook_scheduler.py` | 881 | `AlegraService` | Scheduler cuotas |

**Total:** 20 modulos de produccion + 4 archivos de tests

---

## 2. Verificacion de URLs

### URL Base Correcta

```python
# backend/alegra_service.py:16
ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"
```

Esta es la **unica definicion** de la constante en todo el proyecto. El metodo `request()` en linea 210 construye:
```python
url = f"{ALEGRA_BASE_URL}/{endpoint}"
```

### URLs Incorrectas Encontradas

**Resultado de busqueda `app.alegra.com/api/r1`:**

| Archivo | Linea | Tipo | Estado |
|---------|-------|------|--------|
| `backend/routers/alegra_webhooks.py` | 738 | Texto UI (no llamada HTTP) | INOFENSIVO |
| `backend/BBVA_CONCILIACION_ENERO_2026_REPORT.md` | 115 | Documentacion historica | INOFENSIVO |
| `backend/SINCRONIZACION_BIDIRECCIONAL_REPORT.md` | 303 | Ejemplo curl en doc | INOFENSIVO |

**Veredicto:** No hay ninguna llamada HTTP productiva a `app.alegra.com/api/r1`. El hotfix ERROR-017 (commit `dec35ef`) fue completamente efectivo.

### Endpoints Prohibidos Confirmados

| Endpoint | Estado | Alternativa Correcta | Evidencia |
|----------|--------|---------------------|-----------|
| `/accounts` | 403 BLOQUEADO | Usar `/categories` | Documentado en CLAUDE.md global + ninguna invocacion en produccion |
| `/journal-entries` | ERROR | Usar `/journals` | `MOCK_JOURNAL_ENTRIES` en demo mode acepta ambos (HALLAZGO-04) — produccion solo acepta `/journals` |

---

## 3. Resultados por Endpoint

**Nota de auditoria:** Las variables `ALEGRA_EMAIL` y `ALEGRA_TOKEN` no estaban disponibles en el entorno de ejecucion del agente. Los resultados combinan analisis estatico del codigo con comportamiento documentado en operaciones de produccion previas.

**Script de auditoria:** `.planning/scripts/audit_alegra_endpoints.py` — disponible para re-ejecutar con credenciales reales.

### Tabla Resumen

| Endpoint | Metodo | HTTP Status | Veredicto | Evidencia de Soporte |
|----------|--------|-------------|-----------|---------------------|
| /categories | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | `get_accounts_from_categories()` invocado en produccion — alegra_service.py |
| /invoices | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_factura_venta` usa POST /invoices |
| /payments | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `registrar_pago` usa POST /payments |
| /journals | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_causacion` usa POST /journals |
| /contacts | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | ACTION_MAP `crear_contacto` usa POST /contacts |
| /company | GET | CREDENCIALES_AUSENTES | PENDIENTE-VERIFICAR | `test_connection()` invocado en health check startup |
| /accounts | GET | 403-ESTATICO | BLOQUEADO | CLAUDE.md: "/accounts (da 403) — siempre /categories" |

### Detalle por Endpoint

#### GET /categories
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** `backend/alegra_service.py` metodo `get_accounts_from_categories()` invoca `self.request("categories", "GET")` con cache de 5 minutos
- **Estructura esperada del payload:**
```json
[{"id": "5001", "name": "Caja General", "code": "1105"}, ...]
```
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /invoices
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** `backend/routers/alegra_webhooks.py:587` hace POST /invoices con httpx directo; ACTION_MAP confirma endpoint existe
- **Estructura esperada del payload:**
```json
[{"id": "INV-001", "date": "2026-03-30", "total": 15000000, "status": "open"}]
```
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /payments
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** `backend/routers/alegra_webhooks.py:454` hace POST /payments; ACTION_MAP confirma endpoint existe
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /journals
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** `backend/routers/conciliacion.py:559,1196` hace GET y POST /journals con httpx directo
- **Nota critica:** El mock acepta `journal-entries` O `journals` (alegra_service.py:418) pero produccion solo acepta `/journals`
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /contacts
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** ACTION_MAP `crear_contacto` hace POST /contacts — confirma endpoint disponible
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /company
- **HTTP Status:** CREDENCIALES_AUSENTES
- **Uso en produccion:** `test_connection()` en `backend/server.py:368` durante startup health check
- **Veredicto:** PENDIENTE-VERIFICAR

#### GET /accounts
- **HTTP Status:** 403 (confirmado por regla de negocio documentada)
- **Evidencia:** CLAUDE.md global: `NUNCA usar: /accounts (da 403) — siempre /categories`
- **Uso en produccion:** Cero referencias a `/accounts` en llamadas HTTP — la regla fue aplicada correctamente
- **Veredicto:** BLOQUEADO (restriccion confirmada)

---

## 4. Inventario ACTION_MAP

### Acciones Registradas (12)

**Ubicacion:** `backend/ai_chat.py` lineas 3870-3883

| Accion | Endpoint | Metodo | Tipo |
|--------|----------|--------|------|
| `crear_factura_venta` | `/invoices` | POST | Alegra-directa |
| `registrar_factura_compra` | `/bills` | POST | Alegra-directa |
| `crear_causacion` | `/journals` | POST | Alegra-directa |
| `registrar_pago` | `/payments` | POST | Alegra-directa |
| `registrar_pago_cartera` | `cartera/registrar-pago` | POST | Endpoint-interno SISMO |
| `registrar_nomina` | `nomina/registrar` | POST | Endpoint-interno SISMO |
| `registrar_abono_socio` | `cxc/socios/abono` | POST | Endpoint-interno SISMO |
| `consultar_saldo_socio` | `cxc/socios/saldo` | GET | Endpoint-interno SISMO (unica accion de lectura) |
| `registrar_ingreso_no_operacional` | `ingresos/no-operacional` | POST | Endpoint-interno SISMO |
| `crear_contacto` | `/contacts` | POST | Alegra-directa |
| `crear_nota_credito` | `/credit-notes` | POST | Alegra-directa |
| `crear_nota_debito` | `/debit-notes` | POST | Alegra-directa |

**Resumen:** 6 acciones Alegra-directas (todas escritura) / 6 acciones internas (5 escritura + 1 lectura interna)

### Acciones Especiales (fuera de ACTION_MAP)

| Accion | Lineas | Descripcion |
|--------|--------|-------------|
| `diagnosticar_contabilidad` | 3886-3934 | Diagnostico via accounting_engine — NO llama Alegra API |
| `guardar_pendiente` | 3937-3949 | Guarda tema pendiente en MongoDB — NO llama Alegra API |
| `completar_pendiente` | 3951-3957 | Marca tema completado en MongoDB — NO llama Alegra API |
| `verificar_estado_alegra` | 3959-3984 | GET directo a cualquier recurso Alegra via request() |
| `crear_causacion` (case especial) | 3986+ | Sobreescribe ACTION_MAP entry con logica adicional F2 Chat Transaccional |

### Acciones de Lectura FALTANTES (5)

El agente Contador es actualmente **100% write-only** via ACTION_MAP — no puede responder consultas historicas de Alegra.

| Accion Sugerida | Endpoint Alegra | Prioridad | Razon |
|-----------------|-----------------|-----------|-------|
| `consultar_facturas` | GET /invoices | ALTA | CFO necesita listar facturas de venta por fecha/estado — actualmente imposible via chat |
| `consultar_categorias` | GET /categories | ALTA | Clasificacion contable — actualmente solo disponible via metodo interno, no como accion de chat |
| `consultar_pagos` | GET /payments | ALTA | Reconciliacion bancaria — agente no puede verificar pagos registrados |
| `consultar_journals` | GET /journals | MEDIA | Auditoria de asientos — agente no puede listar journals por rango de fechas |
| `consultar_contactos` | GET /contacts | MEDIA | CRM sync — agente no puede buscar cliente existente sin crear uno nuevo |

---

## 5. Analisis request_with_verify()

**Ubicacion:** `backend/alegra_service.py` lineas 274-314

### Flujo de Ejecucion

```
request_with_verify(endpoint, method, body)
  │
  ├─► request(endpoint, method, body)   [POST/PUT via ALEGRA_BASE_URL — linea 280]
  │     └─► Maneja 401→400, 400, 403, 404→[], 409, 422, 429, 500+ con HTTPException
  │
  ├─► is_demo_mode()
  │     └─► Si demo: retorna {**result, _verificado: True, _fuente: "demo"} — linea 284
  │
  ├─► Extrae recurso_id = result.get("id") — linea 290
  │     └─► Si no hay ID: retorna result sin verificar — linea 292
  │
  └─► request(f"{endpoint}/{recurso_id}", "GET")   [Verificacion — linea 296]
        ├─► Si verification.id existe: retorna {**result, _verificado: True, _verificacion_id: id} — linea 298
        ├─► Si lista vacia (404→[]): lanza HTTPException 500 "VERIFICACION FALLIDA" — lineas 299-307
        └─► Otros HTTPException: retorna {**result, _verificado: False, _error_verificacion: msg} — linea 312
```

### Propiedades Verificadas

| Propiedad | Estado | Linea | Detalle |
|-----------|--------|-------|---------|
| POST → GET obligatorio | Si | 296 | Siempre verifica salvo demo mode |
| HTTP 200 requerido | Si | 232-263 | `request()` lanza HTTPException en cualquier status >= 400 |
| Anti-silencioso | Si | 301-307 | HTTPException 500 "VERIFICACION FALLIDA" si recurso no existe post-creacion |
| Degradacion graceful | Si | 308-312 | Errores de GET (ej: 403 en verificacion) → `_verificado: False` sin fallar operacion |
| Usa ALEGRA_BASE_URL | Si | 210 | Hereda URL de `self.request()`, no hardcodea |

### Observacion Critica: Bypass de request_with_verify()

Los 5 archivos que importan `ALEGRA_BASE_URL` directamente construyen URLs con httpx sin pasar por `request_with_verify()`:

| Archivo | Lineas Bypass | Operaciones Afectadas |
|---------|---------------|----------------------|
| `backend/routers/alegra_webhooks.py` | 454, 587, 704 | POST /payments, POST /invoices, GET /webhooks |
| `backend/routers/auditoria.py` | 65, 260 | Consultas de auditoria |
| `backend/routers/conciliacion.py` | 559, 1196 | GET /journals, POST /journals |
| `backend/services/bank_reconciliation.py` | 502 | Construccion URL directa |
| `backend/services/dian_service.py` | 144, 207 | POST /bills |

**Consecuencia:** Estos modulos no tienen traduccion de errores al espanol, no tienen retry para 429/503, y las operaciones de escritura no tienen verificacion POST→GET.

---

## 6. Lista Priorizada de Issues para Fases 2-8

### Criticos (Bloquean operaciones contables correctas)

**ISSUE-C1: ACTION_MAP tiene 0 acciones de lectura directas a Alegra**
- Gravedad: ALTA
- Fase objetivo: 3 (ACTION_MAP completo)
- Impacto: El agente Contador no puede responder consultas historicas — "que facturas hay de marzo", "cuanto le debo a X proveedor" — sin implementar las 5 acciones de lectura faltantes
- Archivos: `backend/ai_chat.py` lineas 3870-3883

**ISSUE-C2: `crear_causacion` aparece en ACTION_MAP Y como case especial — logica duplicada**
- Gravedad: MEDIA-ALTA
- Fase objetivo: 4 (Chat transaccional)
- Impacto: El case especial (lineas 3986+) sobreescribe ACTION_MAP antes de procesarse. Riesgo de comportamiento inesperado si el flujo cambia. La logica de F2 Chat Transaccional esta en el case especial, no en el ACTION_MAP.
- Archivos: `backend/ai_chat.py` lineas 3870, 3986+

**ISSUE-C3: 5 modulos escriben a Alegra sin request_with_verify() — sin verificacion post-creacion**
- Gravedad: MEDIA-ALTA
- Fase objetivo: 2 (Consolidacion capa Alegra)
- Impacto: Operaciones de escritura en alegra_webhooks.py, conciliacion.py, dian_service.py no tienen verificacion POST→GET. Un fallo silencioso no seria detectado.
- Archivos: alegra_webhooks.py:454,587 / conciliacion.py:1196 / dian_service.py:144,207

### Importantes (Afectan calidad y confiabilidad)

**ISSUE-I1: Demo mode acepta `journal-entries` en mock — confunde a desarrolladores**
- Gravedad: BAJA-MEDIA
- Fase objetivo: 2 (Consolidacion)
- Impacto: `alegra_service.py:418` acepta `journal-entries` O `journals` en mock. En produccion solo funciona `/journals`. Confusion en desarrollo.
- Fix: Eliminar `journal-entries` del mock, forzar `/journals` unicamente

**ISSUE-I2: 403 en GET silenciado — retorna `[]` en vez de error explicito**
- Gravedad: MEDIA
- Fase objetivo: 2 (Consolidacion)
- Impacto: `alegra_service.py:241-242` — `if resp.status_code == 403 and method == "GET": return []`. Si alguien llama a un endpoint GET incorrecto, obtiene lista vacia sin saber por que.
- Fix: Log de advertencia + retornar mensaje de error descriptivo

**ISSUE-I3: 5 modulos usan ALEGRA_BASE_URL directamente — bypass parcial**
- Gravedad: MEDIA
- Fase objetivo: 2 (Consolidacion capa Alegra)
- Impacto: No tienen manejo de errores estandarizado (traduccion al espanol), no tienen retry para 429/503
- Fix: Migrar a `AlegraService.request()` o `request_with_verify()`

**ISSUE-I4: Credenciales Alegra ausentes en entorno de agente — evidencia HTTP no disponible**
- Gravedad: BAJA (solo para auditoria)
- Fase objetivo: N/A — operacional
- Impacto: El script de auditoria no pudo obtener HTTP status reales de los endpoints. Los resultados son analisis estatico.
- Fix: Configurar ALEGRA_EMAIL y ALEGRA_TOKEN en entorno de CI para auditorias futuras

### Mejoras (Nice to have)

**ISSUE-M1: `check_duplicate_journal()` busca en MongoDB, no en Alegra**
- Gravedad: BAJA
- Impacto: Anti-duplicados basados en MongoDB pueden fallar si los eventos no estan sembrados o si hay journals creados fuera de SISMO
- Consideracion futura: Verificar contra Alegra GET /journals por fecha+observaciones

**ISSUE-M2: Cache TTL fijo (5 min categories, 1 min settings) — puede causar stale data**
- Gravedad: BAJA
- Impacto: En produccion con credenciales cambiadas, puede haber ventana de 1-5 minutos con datos obsoletos
- Evidencia: `alegra_service.py:22-24` — `_SETTINGS_TTL = 60`, `_ACCOUNTS_TTL = 300`

---

## 7. Recomendaciones para BUILD 24

### Prioridad 1: Fase 2 — Consolidacion Capa Alegra (prerequisito de todo lo demas)

1. **Migrar los 5 modulos bypass** a `AlegraService.request()` o `request_with_verify()`
   - Archivos: alegra_webhooks.py, auditoria.py, conciliacion.py, bank_reconciliation.py, dian_service.py
   - Beneficio: Manejo de errores unificado, retry automatico, logs en espanol

2. **Eliminar `journal-entries` del mock** — forzar `/journals` unicamente
   - Archivo: `backend/alegra_service.py:418`

3. **Mejorar manejo de 403 en GET** — log explicito en vez de silenciar con `[]`

### Prioridad 2: Fase 3 — ACTION_MAP Completo (habilita consultas historicas)

4. **Agregar 5 acciones de lectura** a ACTION_MAP:
   - `consultar_facturas` → GET /invoices (ALTA)
   - `consultar_categorias` → GET /categories (ALTA)
   - `consultar_pagos` → GET /payments (ALTA)
   - `consultar_journals` → GET /journals (MEDIA)
   - `consultar_contactos` → GET /contacts (MEDIA)

### Prioridad 3: Fases 4-7 — Flujos Transaccionales

5. **Resolver duplicacion de `crear_causacion`** — unificar ACTION_MAP y case especial
6. **Chat transaccional robusto** — gasto en lenguaje natural → classificacion → ReteFuente/ReteICA → POST /journals → ID verificado
7. **Facturacion venta motos** — POST /invoices con VIN + motor obligatorios
8. **Ingresos cuotas** — POST /payments → journal ingreso con anti-duplicados

### Prioridad 4: Fase 8 — Smoke Test

9. **Configurar ALEGRA_EMAIL y ALEGRA_TOKEN en CI/entorno de pruebas** para que el script de auditoria pueda obtener HTTP status reales
10. **Ejecutar `.planning/scripts/audit_alegra_endpoints.py` con credenciales reales** como parte del smoke test final

---

## Apendice: Evidencia de Analisis

### Comandos Ejecutados

```bash
find backend/ -name "alegra*.py" -type f
# → 3 archivos: alegra_service.py, routers/alegra.py, routers/alegra_webhooks.py

grep -rn "from alegra_service import|import alegra_service" backend/
# → 29 referencias (20 produccion + 4 tests + 1 migracion + algunas lineas adicionales en ai_chat.py)

grep -rn "ALEGRA_BASE_URL|api\.alegra\.com|app\.alegra\.com" backend/
# → ALEGRA_BASE_URL: definida en :16, usada en 8 archivos — todos correctos
# → app.alegra.com: 3 referencias — todas texto/doc, ningun llamada HTTP

grep -n "ACTION_MAP" backend/ai_chat.py
# → definicion en linea 3870, uso en 3883+, case especial crear_causacion en 3986+
```

### Archivos Auditados

| Archivo | Lineas | Estado Alegra |
|---------|--------|---------------|
| `backend/alegra_service.py` | 492 | CORRECTO — URL correcta, metodos documentados |
| `backend/ai_chat.py` | ~5217 | CORRECTO (ACTION_MAP) + ISSUE-C1 (sin acciones lectura) + ISSUE-C2 (duplicacion crear_causacion) |
| `backend/routers/alegra_webhooks.py` | N/A | ISSUE-I3 (bypass) — URL correcta pero sin request_with_verify() |
| `backend/routers/conciliacion.py` | N/A | ISSUE-I3 (bypass) |
| `backend/services/dian_service.py` | N/A | ISSUE-I3 (bypass) |
| `backend/services/bank_reconciliation.py` | N/A | ISSUE-I3 (bypass) |
| `backend/routers/auditoria.py` | N/A | ISSUE-I3 (bypass) |
