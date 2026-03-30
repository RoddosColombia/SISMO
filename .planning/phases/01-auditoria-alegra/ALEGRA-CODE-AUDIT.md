# ALEGRA-CODE-AUDIT.md — Auditoria Estatica Capa Alegra

**Generado:** 2026-03-30
**Fase:** 01-auditoria-alegra — Plan 01-01
**Proposito:** Documentar arquitectura actual, confirmar URLs, inventariar ACTION_MAP — sin hacer requests HTTP reales.

---

## 1. Arquitectura: Fuente de Verdad

**Archivo principal:** `backend/alegra_service.py` (492 lineas)

La clase `AlegraService` reside en `backend/alegra_service.py`, **NO** en:
- `backend/utils/alegra.py` — NO EXISTE (confirmado con find)
- `backend/services/alegra_service.py` — NO EXISTE (confirmado con find)

### Resultado de busqueda de archivos Alegra

```
$ find backend/ -name "alegra*.py" -type f
backend/alegra_service.py
backend/routers/alegra.py
backend/routers/alegra_webhooks.py
```

Solo 3 archivos con nombre `alegra*.py`:
- `backend/alegra_service.py` — Fuente de verdad: clase AlegraService + ALEGRA_BASE_URL
- `backend/routers/alegra.py` — Router HTTP que expone endpoints REST al frontend
- `backend/routers/alegra_webhooks.py` — Receptor de webhooks de Alegra

### Clase AlegraService — Metodos principales

| Metodo | Tipo | Descripcion |
|--------|------|-------------|
| `get_settings()` | async | Credenciales desde env vars > MongoDB > demo mode |
| `is_demo_mode()` | async | Retorna True si no hay credenciales reales |
| `get_auth_header()` | async | Encabezado Basic Auth para Alegra |
| `request()` | async | HTTP generico (GET/POST/PUT/DELETE) via ALEGRA_BASE_URL |
| `request_with_verify()` | async | POST + verificacion GET obligatoria |
| `retry_request()` | async | request() con reintentos para 429/503 |
| `check_duplicate_journal()` | async | Anti-duplicados via roddos_events |
| `get_accounts_from_categories()` | async | GET /categories con cache 5 min |
| `get_cuenta_roddos()` | async | Busca cuenta en MongoDB roddos_cuentas |
| `test_connection()` | async | Verifica conexion con GET /company |

---

## 2. Mapa de Imports

**Comando ejecutado:** `grep -rn "from alegra_service import\|import alegra_service" backend/`

### Modulos de produccion que importan AlegraService

| Archivo | Importa | Uso detectado |
|---------|---------|---------------|
| `backend/ai_chat.py:2588` | `AlegraService` | request(), request_with_verify() en acciones de chat |
| `backend/ai_chat.py:2852` | `AlegraService` | request() en contexto de ejecutar acciones |
| `backend/ai_chat.py:3830` | `AlegraService` | request() en procesamiento de acciones Alegra |
| `backend/ai_chat.py:4513` | `AlegraService as _AS` | request() en cleanup async de journals |
| `backend/post_action_sync.py:34` | `AlegraService` | Sincronizacion post-accion |
| `backend/routers/alegra.py:7` | `AlegraService` | Router principal — todos los endpoints REST |
| `backend/routers/alegra_webhooks.py:18` | `ALEGRA_BASE_URL` | **Acceso directo a URL** (ver Hallazgos) |
| `backend/routers/auditoria.py:14` | `ALEGRA_BASE_URL` | **Acceso directo a URL** (ver Hallazgos) |
| `backend/routers/cartera.py:16` | `AlegraService` | Operaciones de cartera |
| `backend/routers/cfo_estrategico.py:30` | `AlegraService` | CFO agente estrategico |
| `backend/routers/conciliacion.py:24` | `ALEGRA_BASE_URL` | **Acceso directo a URL** (ver Hallazgos) |
| `backend/routers/conciliacion.py:706` | `AlegraService` | Conciliacion bancaria |
| `backend/routers/cxc.py:24` | `AlegraService` | Cuentas por cobrar |
| `backend/routers/cxc_socios.py:16` | `AlegraService` | CXC socios |
| `backend/routers/dashboard.py:9` | `AlegraService` | KPIs dashboard |
| `backend/routers/estado_resultados.py:20` | `AlegraService` | Estado de resultados |
| `backend/routers/gastos.py:26` | `AlegraService` | Gestion de gastos |
| `backend/routers/ingresos.py:16` | `AlegraService` | Registro de ingresos |
| `backend/routers/inventory.py:8` | `AlegraService` | Inventario motos |
| `backend/routers/loanbook.py:9` | `AlegraService` | Ciclo de credito |
| `backend/routers/nomina.py:17` | `AlegraService` | Nomina mensual |
| `backend/routers/repuestos.py:9` | `AlegraService` | Repuestos |
| `backend/routers/settings.py:10` | `AlegraService` | Configuracion |
| `backend/routers/taxes.py:8` | `AlegraService` | Impuestos |
| `backend/routers/ventas.py:10` | `AlegraService` | Ventas |
| `backend/server.py:368` | `AlegraService` | Health check startup |
| `backend/services/bank_reconciliation.py:26` | `ALEGRA_BASE_URL` | **Acceso directo a URL** (ver Hallazgos) |
| `backend/services/cfo_agent.py:74` | `AlegraService` | CFO analisis financiero |
| `backend/services/dian_service.py:17` | `ALEGRA_BASE_URL` | **Acceso directo a URL** (ver Hallazgos) |
| `backend/services/loanbook_scheduler.py:881` | `AlegraService` | Scheduler cuotas |

### Modulos de tests que importan AlegraService

| Archivo | Importa |
|---------|---------|
| `backend/tests/test_build21_accounting_engine.py:216` | `AlegraService` |
| `backend/tests/test_build21_integration.py:154` | `AlegraService` |
| `backend/tests/test_build23_f2_chat_transactional.py:248` | `AlegraService` |
| `backend/tests/test_iteration30_anulacion.py:267` | `AlegraService` |

### Migraciones

| Archivo | Importa |
|---------|---------|
| `backend/migrations/migrate_inventario_tvs.py:30` | `ALEGRA_BASE_URL` desde backend.alegra_service |

---

## 3. Verificacion de URLs

**Comando ejecutado:** `grep -rn "ALEGRA_BASE_URL\|api\.alegra\.com\|app\.alegra\.com" backend/`

### URL correcta — ALEGRA_BASE_URL

**Linea 16 de `backend/alegra_service.py`:**
```python
ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"
```
**Estado:** CORRECTA. Esta es la unica definicion de la constante en el codigo.

**Usos de ALEGRA_BASE_URL (todos correctos — importan la constante):**

| Archivo | Linea | Uso |
|---------|-------|-----|
| `alegra_service.py` | 210 | `url = f"{ALEGRA_BASE_URL}/{endpoint}"` — en method `request()` |
| `routers/alegra_webhooks.py` | 454, 587, 704 | Construye URLs directas para payments, invoices, webhooks |
| `routers/auditoria.py` | 65, 260 | `base_url = ALEGRA_BASE_URL` |
| `routers/conciliacion.py` | 559, 1196 | `url = f"{ALEGRA_BASE_URL}/journals..."` |
| `services/bank_reconciliation.py` | 502 | `base_url = ALEGRA_BASE_URL` |
| `services/dian_service.py` | 144, 207 | `f"{ALEGRA_BASE_URL}/bills"` |
| `migrations/migrate_inventario_tvs.py` | 154, 169 | `f"{ALEGRA_BASE_URL}/{path}"` |

### Referencias a URL INCORRECTA — app.alegra.com/api/r1

**Resultado del grep:**

| Archivo | Linea | Contexto |
|---------|-------|---------|
| `backend/routers/alegra_webhooks.py:738` | 738 | String en mensaje de usuario (UI text, no llamada HTTP): `"...regístralos manualmente en app.alegra.com → Integraciones → Webhooks"` |
| `backend/BBVA_CONCILIACION_ENERO_2026_REPORT.md:115` | 115 | Documentacion historica — no es codigo ejecutable |
| `backend/SINCRONIZACION_BIDIRECCIONAL_REPORT.md:303` | 303 | Ejemplo curl en doc — no es codigo ejecutable |

**Veredicto URL:** No hay ninguna llamada HTTP productiva a `app.alegra.com/api/r1`. Las 3 referencias son texto de UI o documentacion historica. El hotfix ERROR-017 fue efectivo.

---

## 4. Analisis request_with_verify()

**Ubicacion:** `backend/alegra_service.py` lineas 274-314

### Flujo de ejecucion

```
request_with_verify(endpoint, method, body)
  │
  ├─► request(endpoint, method, body)   [POST/PUT via ALEGRA_BASE_URL]
  │     └─► Maneja 401, 400, 403, 404, 409, 422, 429, 500+ con HTTPException
  │
  ├─► is_demo_mode()
  │     └─► Si demo: retorna {**result, _verificado: True, _fuente: "demo"}
  │
  ├─► Extrae recurso_id = result.get("id")
  │     └─► Si no hay ID: retorna result sin verificar
  │
  └─► request(f"{endpoint}/{recurso_id}", "GET")   [Verificacion]
        ├─► Si verification.id existe: retorna {**result, _verificado: True, _verificacion_id: id}
        ├─► Si lista vacia (404): lanza HTTPException 500 "VERIFICACION FALLIDA"
        └─► Otros HTTPException: retorna {**result, _verificado: False, _error_verificacion: msg}
```

### Propiedades verificadas

- **POST → GET obligatorio:** Si, siempre verifica salvo demo mode
- **HTTP 200 requerido:** Si — `request()` lanza HTTPException en cualquier status >= 400
- **Anti-silencioso:** `VERIFICACION FALLIDA` en detalle si recurso no existe post-creacion
- **Degradacion graceful:** Errores de GET (ej: 403 en verificacion) → `_verificado: False` sin fallar la operacion
- **Usa `self.request()`:** Si — hereda ALEGRA_BASE_URL del metodo base, no hardcodea URLs

### Observacion critica

Los archivos que importan `ALEGRA_BASE_URL` directamente (`conciliacion.py`, `bank_reconciliation.py`, `dian_service.py`, `alegra_webhooks.py`) construyen URLs con `httpx` directamente **sin pasar por `request_with_verify()`**. Estos bypass el manejo de errores estandarizado y la verificacion post-escritura.

---

## 5. Inventario ACTION_MAP

**Ubicacion:** `backend/ai_chat.py` lineas 3870-3883

```python
ACTION_MAP = {
    "crear_factura_venta":            ("invoices",                 "POST"),
    "registrar_factura_compra":       ("bills",                    "POST"),
    "crear_causacion":                ("journals",                 "POST"),
    "registrar_pago":                 ("payments",                 "POST"),
    "registrar_pago_cartera":         ("cartera/registrar-pago",   "POST"),
    "registrar_nomina":               ("nomina/registrar",         "POST"),
    "registrar_abono_socio":          ("cxc/socios/abono",         "POST"),
    "consultar_saldo_socio":          ("cxc/socios/saldo",         "GET"),
    "registrar_ingreso_no_operacional": ("ingresos/no-operacional","POST"),
    "crear_contacto":                 ("contacts",                 "POST"),
    "crear_nota_credito":             ("credit-notes",             "POST"),
    "crear_nota_debito":              ("debit-notes",              "POST"),
}
```

**Total: 12 acciones registradas**

### Clasificacion: Alegra-directa vs Endpoint-interno

| Accion | Endpoint | Metodo | Tipo |
|--------|----------|--------|------|
| `crear_factura_venta` | `/invoices` | POST | Alegra-directa |
| `registrar_factura_compra` | `/bills` | POST | Alegra-directa |
| `crear_causacion` | `/journals` | POST | Alegra-directa |
| `registrar_pago` | `/payments` | POST | Alegra-directa |
| `registrar_pago_cartera` | `cartera/registrar-pago` | POST | Endpoint-interno SISMO |
| `registrar_nomina` | `nomina/registrar` | POST | Endpoint-interno SISMO |
| `registrar_abono_socio` | `cxc/socios/abono` | POST | Endpoint-interno SISMO |
| `consultar_saldo_socio` | `cxc/socios/saldo` | GET | Endpoint-interno SISMO |
| `registrar_ingreso_no_operacional` | `ingresos/no-operacional` | POST | Endpoint-interno SISMO |
| `crear_contacto` | `/contacts` | POST | Alegra-directa |
| `crear_nota_credito` | `/credit-notes` | POST | Alegra-directa |
| `crear_nota_debito` | `/debit-notes` | POST | Alegra-directa |

**Acciones Alegra-directa:** 6 de 12
**Acciones Endpoint-interno:** 5 de 12
**Accion mixta (consultar_saldo_socio es GET pero interno):** 1 de 12

### Acciones especiales fuera de ACTION_MAP (lineas 3886+)

| Accion | Lineas | Descripcion |
|--------|--------|-------------|
| `diagnosticar_contabilidad` | 3886-3934 | Ejecuta diagnostico/retenciones/clasificacion via accounting_engine — NO llama Alegra API |
| `guardar_pendiente` | 3937-3949 | Guarda tema pendiente en MongoDB (save_pending_topic) — NO llama Alegra API |
| `completar_pendiente` | 3951-3957 | Marca tema como completado (complete_pending_topic) — NO llama Alegra API |
| `verificar_estado_alegra` | 3959-3984 | GET directo a cualquier recurso Alegra — si llama API via request() |
| `crear_causacion` | 3986+ | Case especial F2 Chat Transaccional — sobreescribe ACTION_MAP entry con logica adicional |

---

## 6. Acciones Faltantes

Las siguientes acciones de **LECTURA** no existen en ACTION_MAP. El agente Contador no puede consultar datos historicos de Alegra sin estas acciones.

| Accion Faltante | Endpoint Alegra | Metodo | Impacto |
|----------------|-----------------|--------|---------|
| `consultar_facturas` | `GET /invoices` | GET | No puede listar facturas de venta por fecha/estado |
| `consultar_categorias` | `GET /categories` | GET | No puede obtener plan de cuentas en chat (usa get_accounts_from_categories() fuera de ACTION_MAP) |
| `consultar_pagos` | `GET /payments` | GET | No puede verificar pagos registrados |
| `consultar_journals` | `GET /journals` | GET | No puede listar asientos contables por rango de fechas |
| `consultar_contactos` | `GET /contacts` | GET | No puede buscar cliente en chat sin crear uno nuevo |

**Estado actual:** Solo `consultar_saldo_socio` (endpoint interno) existe como accion de lectura.
**Consecuencia practica:** El agente Contador es 100% write-only via ACTION_MAP — no puede responder preguntas como "que facturas hay de marzo" o "cuanto le debo a X proveedor" sin implementar estas acciones.

---

## 7. Hallazgos Criticos

### HALLAZGO-01: 5 modulos bypass AlegraService.request() — usan ALEGRA_BASE_URL directamente con httpx

**Gravedad:** MEDIA — URL es correcta, pero se pierde manejo de errores estandarizado y posibilidad de verificacion

**Archivos afectados:**

| Archivo | Lineas | Tipo de bypass |
|---------|--------|----------------|
| `backend/routers/alegra_webhooks.py` | 454, 587, 704 | POST /payments, POST /invoices, GET /webhooks con httpx directo |
| `backend/routers/auditoria.py` | 65, 260 | base_url construida directamente |
| `backend/routers/conciliacion.py` | 559, 1196 | GET y POST /journals con httpx directo |
| `backend/services/bank_reconciliation.py` | 502 | Construccion directa de URL Alegra |
| `backend/services/dian_service.py` | 144, 207 | POST /bills con httpx directo |

**Consecuencia:** Estos modulos no pasan por `request_with_verify()`, no tienen traduccion de errores al espanol, y no tienen retry automatico para 429/503.

### HALLAZGO-02: ACTION_MAP tiene 0 acciones de lectura directas a Alegra

**Gravedad:** ALTA — El agente Contador no puede responder consultas historicas de Alegra

**Estado:** `consultar_saldo_socio` es la unica accion GET, pero apunta a endpoint interno de SISMO, no a Alegra directamente.

### HALLAZGO-03: `crear_causacion` aparece dos veces — en ACTION_MAP Y como caso especial

**Gravedad:** BAJA — El case especial (lineas 3986+) sobreescribe el ACTION_MAP entry antes de que se procese. El flujo correcto es que se ejecuta solo el case especial para F2 Chat Transaccional.

### HALLAZGO-04: Demo mode usa `journal-entries` en mock (no `journals`)

**Gravedad:** BAJA — En `_mock()` linea 418: `if "journal-entries" in endpoint or "journals" in endpoint`. El endpoint correcto en produccion es `/journals`, pero el mock acepta ambos. Riesgo: confusion en desarrollo.

### HALLAZGO-05: URL correcta confirmada en toda ruta de produccion

**Gravedad:** N/A (hallazgo positivo)

**Evidencia:** `ALEGRA_BASE_URL = "https://api.alegra.com/api/v1"` en linea 16. Ningun codigo de produccion usa `app.alegra.com/api/r1`. Hotfix ERROR-017 completamente efectivo.

---

## Resumen Ejecutivo

| Metrica | Valor |
|---------|-------|
| Archivos `alegra*.py` en backend | 3 (service, router, webhooks) |
| Modulos que importan AlegraService | 20 modulos de produccion |
| Modulos que importan ALEGRA_BASE_URL directo | 5 (bypass parcial) |
| Acciones en ACTION_MAP | 12 |
| Acciones Alegra-directas | 6 (5 escritura + 0 lectura) |
| Acciones internas SISMO | 6 (5 escritura + 1 lectura interna) |
| Acciones de lectura Alegra FALTANTES | 5 |
| Referencias a URL incorrecta en codigo ejecutable | 0 |
| Archivos con URL correcta verificada | Todo el codigo de produccion |
