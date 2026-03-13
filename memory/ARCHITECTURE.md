# ARQUITECTURA TÉCNICA — RODDOS Contable IA
**Versión**: 2.0.0 | **Fecha**: Febrero 2026 | **Estado**: Producción

---

## ÍNDICE
1. [Visión General del Sistema](#1-visión-general-del-sistema)
2. [Diagrama de Arquitectura](#2-diagrama-de-arquitectura)
3. [Backend — Módulos y Responsabilidades](#3-backend--módulos-y-responsabilidades)
4. [Frontend — Páginas y Componentes](#4-frontend--páginas-y-componentes)
5. [Base de Datos — Colecciones MongoDB](#5-base-de-datos--colecciones-mongodb)
6. [Integraciones Externas](#6-integraciones-externas)
7. [Flujos de Datos Clave](#7-flujos-de-datos-clave)
8. [Matriz de Conexiones entre Módulos](#8-matriz-de-conexiones-entre-módulos)
9. [Análisis de Brechas y Producto Final Ideal](#9-análisis-de-brechas-y-producto-final-ideal)

---

## 1. VISIÓN GENERAL DEL SISTEMA

RODDOS Contable IA es un **ERP contable asistido por inteligencia artificial** diseñado para RODDOS Colombia SAS, empresa dedicada a la venta de motocicletas a crédito. El sistema actúa como:

1. **Asistente contable conversacional**: El usuario chatea con una IA (Claude Sonnet) que ejecuta acciones reales en Alegra ERP.
2. **Gestor de cartera**: Administra planes de pago semanales (Loanbook) para clientes que compran motos a crédito.
3. **Control de inventario**: Rastrea el stock de motos y repuestos, sincronizando con Alegra.
4. **Centro de gestión de cobros**: Cola priorizada de clientes con cuotas vencidas o próximas.
5. **Módulo fiscal**: Control de IVA cuatrimestral, retenciones y presupuesto.

### Stack Tecnológico
| Capa | Tecnología | Versión |
|------|-----------|---------|
| Frontend | React | 18.x |
| Backend | FastAPI (Python) | Latest |
| Base de Datos | MongoDB (Motor async) | Latest |
| IA | Claude Sonnet 4.5 via `emergentintegrations` | claude-sonnet-4-5-20250929 |
| ERP Externo | Alegra API v1 | REST |
| Mensajería | Telegram Bot API | Latest |
| Autenticación | JWT + TOTP (Google Authenticator) | - |
| Contenedorización | Kubernetes (Emergent Platform) | - |

---

## 2. DIAGRAMA DE ARQUITECTURA

```
┌─────────────────────────────────────────────────────────────────────┐
│                        CLIENTE (Browser)                           │
│                                                                     │
│  React App (port 3000)                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────────┐  │
│  │  AuthContext │  │ AlegraContext│  │    React Router (App.js)  │  │
│  │  (JWT, 2FA)  │  │ (accounts,   │  │  /agente-contable (HOME) │  │
│  │              │  │  contacts,   │  │  /dashboard              │  │
│  │  useAuth()   │  │  bankAccts)  │  │  /loanbook  /cartera     │  │
│  └──────────────┘  └──────────────┘  │  /inventario-auteco      │  │
│                                       │  /repuestos              │  │
│                                       │  /impuestos /retenciones │  │
│                                       │  /configuracion  etc...  │  │
│                                       └──────────────────────────┘  │
└────────────────────────────────────────────┬────────────────────────┘
                                             │ HTTP / REST (/api/*)
                                             ▼
┌─────────────────────────────────────────────────────────────────────┐
│                     BACKEND FastAPI (port 8001)                     │
│                                                                     │
│  server.py ← Punto de entrada, CORS, startup hooks, webhook Alegra │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      ROUTERS (/api/*)                        │   │
│  │                                                              │   │
│  │  /auth      /settings   /alegra    /chat    /dashboard      │   │
│  │  /inventario /loanbook  /cartera  /repuestos /presupuesto   │   │
│  │  /impuestos  /telegram  /audit                              │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
│                                 │                                    │
│  ┌──────────────────────────────▼───────────────────────────────┐   │
│  │                    SERVICIOS CORE                             │   │
│  │                                                              │   │
│  │  ai_chat.py          alegra_service.py   post_action_sync.py│   │
│  │  (Claude + Prompts)  (Alegra REST proxy)  (sincroniza BDs)  │   │
│  │                                                              │   │
│  │  event_bus.py        auth.py             security_service.py│   │
│  │  (roddos_events)    (JWT, hash)           (TOTP, encrypt)   │   │
│  │                                                              │   │
│  │  inventory_service.py   dependencies.py    database.py      │   │
│  │  (PDF parsing, Alegra)  (guards, audit)   (MongoDB Motor)   │   │
│  └──────────────────────────────┬───────────────────────────────┘   │
└────────────────────────────────┬┴────────────────────────────────────┘
                                 │
         ┌───────────────────────┼──────────────────────────┐
         ▼                       ▼                          ▼
┌─────────────────┐   ┌──────────────────────┐   ┌──────────────────┐
│   MongoDB        │   │   Alegra API v1       │   │  Claude Sonnet   │
│   (Motor async)  │   │   (ERP Colombia)      │   │  (Anthropic AI)  │
│                  │   │                       │   │  via emergent    │
│  Collections:    │   │  /invoices /bills     │   │  integrations    │
│  - users         │   │  /journals /payments  │   │                  │
│  - loanbook      │   │  /contacts /items     │   │  Entrada: texto  │
│  - cartera_pagos │   │  /bank-accounts       │   │  + imagen/PDF    │
│  - inventario_   │   │  /categories          │   │  Salida: texto   │
│    motos         │   │  /taxes               │   │  + bloque <action│
│  - chat_messages │   │                       │   │  JSON>           │
│  - audit_logs    │   │  Base URL:            │   └──────────────────┘
│  - agent_memory  │   │  api.alegra.com/v1    │
│  - roddos_events │   └──────────────────────┘
│  - repuestos_*   │
│  - presupuesto   │                          ┌──────────────────────┐
│  - iva_config    │                          │  Telegram Bot API    │
│  - telegram_*    │◄─────────────────────────│  (webhook receiver)  │
│  - notifications │                          │  Fotos/PDFs → Claude │
└─────────────────┘                          │  → Alegra            │
                                              └──────────────────────┘
```

---

## 3. BACKEND — MÓDULOS Y RESPONSABILIDADES

### 3.1 `server.py` — Punto de Entrada
**Tarea**: Bootstrap de la aplicación FastAPI. No contiene lógica de negocio.

**Responsabilidades**:
- Configura CORS (permite all origins en dev)
- `@startup`: Crea usuarios por defecto, credenciales Alegra vacías, índices MongoDB
- `@shutdown`: Cierra conexión MongoDB
- Registra todos los routers bajo el prefijo `/api`
- Maneja el webhook público de Alegra (`/api/webhook/alegra`)

**Se conecta con**: Todos los routers (los incluye), `database.py`, `auth.py`

**No se conecta directamente con**: Alegra API, Claude (eso lo hace ai_chat.py)

---

### 3.2 `ai_chat.py` — El Cerebro de la IA
**Tarea**: Toda la lógica de IA — sistema de prompts, recopilación de contexto, llamadas a Claude, parsing de respuestas.

**Responsabilidades**:

| Función | Descripción |
|---------|-------------|
| `AGENT_SYSTEM_PROMPT` | Prompt maestro del agente contable. Define: tarifas Colombia 2025, plan de cuentas RODDOS, flujos de acción (venta moto, entrega, causación, factura compra/venta, nuevo tercero) |
| `gather_context()` | Inyecta al prompt: contactos Alegra, cuentas bancarias, catálogo de items, inventario motos disponibles, loanbooks activos, estado IVA cuatrimestral |
| `gather_accounts_context()` | Carga el plan de cuentas completo (hojas) desde Alegra `/categories` + patrones aprendidos de `agent_memory` |
| `process_chat()` | Flujo texto: construye prompt → llama Claude → parsea `<action>` → guarda en `chat_messages` → retorna |
| `process_document_chat()` | Flujo con archivo: carga cuentas + loanbooks → llama Claude con imagen/PDF → parsea `<document_proposal>` + `<action>` |
| `execute_chat_action()` | Ejecuta la acción confirmada: llama `alegra_service.request()` → llama `post_action_sync()` → guarda en `agent_memory` |

**Flujo de acción encadenada (Nuevo Tercero)**:
1. IA detecta proveedor inexistente → emite `crear_contacto` con `_next_action` embebido
2. Frontend muestra `TerceroCard` → usuario confirma
3. `execute_chat_action("crear_contacto")` → crea en Alegra → reemplaza `__NEW_CONTACT_ID__` en `_next_action`
4. Retorna `next_pending_action` al frontend
5. Frontend auto-ejecuta la acción original con el ID real

**Se conecta con**: `alegra_service.py` (contexto + ejecución), `database.py` (chat_messages, agent_memory, loanbook), `post_action_sync.py` (después de ejecutar), `emergentintegrations` (Claude)

---

### 3.3 `alegra_service.py` — Proxy de Alegra ERP
**Tarea**: Toda comunicación con la API REST de Alegra. Abstrae HTTP, auth, caché y modo demo.

**Responsabilidades**:

| Método | Descripción |
|--------|-------------|
| `get_settings()` | Lee credenciales de MongoDB con caché TTL 60s |
| `request(endpoint, method, body)` | Proxy genérico HTTP. Maneja 401/400/403/404/429/500. En demo mode → `_mock()` |
| `_mock()` | Devuelve datos ficticios de `mock_data.py` para desarrollo/demo |
| `get_accounts_from_categories()` | Obtiene árbol de cuentas via `/categories` con caché TTL 5min |
| `get_leaf_accounts()` | Aplana el árbol a solo cuentas hoja (use=movement) |
| `test_connection()` | Verifica conexión vía `/company` |

**Endpoints Alegra que usa**:
- `GET /contacts`, `GET /items`, `GET /taxes`, `GET /bank-accounts`
- `GET/POST /invoices`, `GET/POST /bills`, `GET/POST /journals`
- `GET/POST /payments`, `POST /contacts`
- `GET /categories` (plan de cuentas)

**Se conecta con**: `database.py` (credenciales), `mock_data.py` (datos demo)

**No se conecta con**: frontend directamente, ai_chat.py la usa internamente

---

### 3.4 `post_action_sync.py` — Sincronizador Post-Acción
**Tarea**: Actualiza todas las colecciones internas de MongoDB después de que la IA ejecuta una acción en Alegra.

**Responsabilidades por tipo de acción**:

| Acción IA | Efecto en MongoDB | Módulos Notificados |
|-----------|-------------------|---------------------|
| `crear_factura_venta` | Moto → `estado: "Vendida"` en `inventario_motos`. Crea documento en `loanbook` con cuotas (sin fechas) | inventario, loanbook, dashboard |
| `registrar_pago` | Busca cuota pendiente en `loanbook` → `estado: "pagada"`. Inserta en `cartera_pagos`. Recalcula stats del loan | cartera, loanbook, dashboard |
| `crear_causacion` | Solo emite evento al bus | dashboard |
| `registrar_factura_compra` | Agrega motos a `inventario_motos` si `_metadata.motos_a_agregar` presente | inventario, dashboard |
| `registrar_entrega` | Delega a `loanbook.register_entrega()` → genera fechas miércoles | loanbook, cartera, dashboard |
| `crear_contacto` | Registra en audit log | audit |

**Se conecta con**: `database.py` (inventario_motos, loanbook, cartera_pagos), `event_bus.py`, `routers/loanbook.py` (para entrega)

---

### 3.5 `event_bus.py` — Bus de Eventos
**Tarea**: Persiste eventos de negocio en `roddos_events` y define qué módulos se ven afectados.

**Responsabilidades**:
- `emit_event(source, event_type, payload)` → inserta en `roddos_events`
- Mapa `MODULES_FOR_EVENT` define qué módulos deben reaccionar a cada evento
- `get_recent_events()` → feed de actividad del dashboard

**Eventos definidos**:
```
factura.venta.creada       → inventario, loanbook, cartera, dashboard
pago.cuota.registrado      → cartera, loanbook, dashboard
inventario.moto.entrada    → dashboard, modulo_motos
asiento.contable.creado    → dashboard
factura.compra.creada      → inventario, dashboard
repuesto.vendido           → inventario, dashboard
```

**Se conecta con**: `database.py`, llamado por `post_action_sync.py`, `routers/loanbook.py`, `routers/repuestos.py`

**Nota**: El bus es PASIVO — persiste eventos pero NO tiene listeners activos en tiempo real (no WebSockets).

---

### 3.6 ROUTERS — Endpoints de la API

#### `/auth` — Autenticación
**Archivo**: `routers/auth.py`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/auth/login` | POST | Login → JWT o token temporal si 2FA activo |
| `/auth/2fa/login` | POST | Valida código TOTP → JWT definitivo |
| `/auth/2fa/setup` | POST | Genera secret y QR para Google Authenticator |
| `/auth/2fa/enable` | POST | Activa 2FA para admin |
| `/auth/2fa/disable` | POST | Desactiva 2FA |
| `/auth/me` | GET | Info del usuario actual |

**Se conecta con**: `auth.py` (JWT), `security_service.py` (TOTP), `database.py` (users)

**Conexiones con otros módulos**: Independiente. Todos los demás routers dependen de `get_current_user` de `dependencies.py`.

---

#### `/chat` — Agente IA
**Archivo**: `routers/chat.py`

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/chat/message` | POST | Envía mensaje (con/sin archivo) → retorna respuesta IA + `pending_action` |
| `/chat/execute-action` | POST | Confirma y ejecuta la acción propuesta por la IA |
| `/chat/history/{session_id}` | GET | Historial de mensajes de la sesión |
| `/chat/history/{session_id}` | DELETE | Borra historial |

**Se conecta con**: `ai_chat.py` (toda la lógica), `database.py`

**Conexiones con otros módulos**: Dispara `post_action_sync.py` que a su vez actualiza `loanbook`, `inventario_motos`, `cartera_pagos`.

---

#### `/alegra` — Proxy Alegra
**Archivo**: `routers/alegra.py`

Expone endpoints REST que hacen proxy directo hacia Alegra API. Útil para las páginas frontend que consultan datos de Alegra directamente (sin pasar por el agente IA).

| Endpoints principales |
|----------------------|
| GET/POST `/alegra/invoices` |
| GET/POST `/alegra/bills` |
| GET/POST `/alegra/payments` |
| GET/POST `/alegra/journal-entries` |
| GET `/alegra/contacts`, `/accounts`, `/items`, `/taxes` |
| GET `/alegra/bank-accounts` |
| POST `/alegra/test-connection` |
| GET/POST `/alegra/bank-accounts/{id}/reconciliations` |

**Se conecta con**: `alegra_service.py` (toda la comunicación), `database.py` (audit log)

**Conexiones con otros módulos**: Usado por `AlegraContext.js` (frontend) para poblar selectores y verificar conexión.

---

#### `/loanbook` — Planes de Pago de Motos
**Archivo**: `routers/loanbook.py`

**Tarea**: CRUD de Loanbooks (contratos de venta a crédito de motos).

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/loanbook` | GET | Lista con filtros (estado, plan, cliente) |
| `/loanbook` | POST | Crea Loanbook manualmente |
| `/loanbook/stats` | GET | KPIs: activos, mora, completados, cartera total |
| `/loanbook/{id}` | GET | Detalle + recálculo de estados vencidos |
| `/loanbook/{id}/entrega` | PUT | **Registra entrega física** → genera fechas de cuotas (miércoles) |
| `/loanbook/{id}/pago` | POST | Registra pago de cuota + crea pago en Alegra |
| `/loanbook/{id}/cuota/{num}` | PUT | Edita cuota (valor, notas) |

**Lógica de Miércoles**: `_first_wednesday(fecha_entrega)` → primera cuota = primer miércoles ≥ (entrega + 7 días). Todas las cuotas siguientes son miércoles consecutivos. Es una regla de negocio inviolable de RODDOS.

**Estados de un Loanbook**: `pendiente_entrega` → `activo` → `mora` → `completado`

**Se conecta con**: `database.py` (loanbook, cartera_pagos), `alegra_service.py` (crea pagos en Alegra), `event_bus.py` (emite eventos)

**Conexiones con otros módulos**: `post_action_sync.py` lo llama para `registrar_entrega`. `cartera.py` lo lee para la cola remota y vista semanal/mensual.

---

#### `/cartera` — Gestión de Cobros
**Archivo**: `routers/cartera.py`

**Tarea**: Vista de cobros y gestión remota de clientes morosos.

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/cartera/semanal` | GET | Cuotas de la semana con resumen (cobrado/pendiente/vencido) |
| `/cartera/mensual` | GET | Resumen mensual del año |
| `/cartera/clientes` | GET | Comportamiento de pago + score por cliente |
| `/cartera/clientes/{id}` | GET | Historial completo del cliente |
| `/cartera/cola-remota` | GET | **Cola priorizada**: URGENTE (>30d), PARA_HOY, PREVENTIVO (próximos 2d) |
| `/cartera/gestiones` | POST | Registra intento de contacto (llamada/WhatsApp) |
| `/cartera/gestiones/{loan_id}` | GET | Timeline de contactos de un loan |

**Se conecta con**: `database.py` (loanbook, cartera_pagos, gestiones_cartera), `routers/loanbook.py` (importa `_update_overdue`)

**Conexiones con otros módulos**: Solo lee datos. No escribe en Alegra. La página `Cartera.js` (frontend) lo consume directamente.

---

#### `/inventario` — Inventario de Motos
**Archivo**: `routers/inventory.py`

**Tarea**: CRUD del inventario de motos Auteco.

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/inventario/upload-pdf` | POST | Sube PDF Auteco → extrae motos con Claude → inserta en BD |
| `/inventario/motos` | GET | Lista con filtros (estado, marca) |
| `/inventario/stats` | GET | Conteos por estado + inversión total |
| `/inventario/motos/{id}` | PUT/DELETE | Editar/eliminar moto |
| `/inventario/motos/{id}/register-alegra` | POST | Registra moto como ítem en catálogo Alegra |
| `/inventario/motos/{id}/vender` | POST | Venta directa (sin IA) → crea factura Alegra |

**Se conecta con**: `database.py` (inventario_motos), `alegra_service.py`, `inventory_service.py` (extrae motos de PDFs)

**Conexiones con otros módulos**: `post_action_sync.py` actualiza este módulo cuando la IA ejecuta `crear_factura_venta`. `ai_chat.py` lee el inventario para el contexto del agente.

---

#### `/repuestos` — Inventario de Repuestos
**Archivo**: `routers/repuestos.py`

**Tarea**: Catálogo de repuestos + kits + facturación.

| Funcionalidad | Descripción |
|--------------|-------------|
| Catálogo CRUD | Crea/edita/elimina repuestos y kits |
| Ajuste de stock | Entrada/salida con movimientos auditados |
| Facturación | Crea factura de repuestos con descuento/IVA → sincroniza con Alegra |
| Anular factura | Restaura stock + anula en Alegra |
| Stats | Total productos, alertas de stock mínimo |

**Se conecta con**: `database.py` (repuestos_catalogo, repuestos_facturas, repuestos_movimientos), `alegra_service.py`, `event_bus.py`

**Conexiones con otros módulos**: Relativamente aislado. Solo dispara eventos al bus.

---

#### `/impuestos` — IVA y Fiscal
**Archivo**: `routers/taxes.py`

**Tarea**: Configuración del período IVA y cálculo del estado actual.

| Endpoint | Descripción |
|----------|-------------|
| GET/POST `/impuestos/config` | Configura tipo de período (cuatrimestral/bimestral/anual) y saldo DIAN |
| GET `/impuestos/iva-status` | Calcula IVA cobrado/descontable/a pagar con proyección para el período |
| GET `/impuestos/periodos-preset` | Retorna presets de períodos |

**Se conecta con**: `database.py` (iva_config), `alegra_service.py` (consulta facturas/bills del período)

**Conexiones con otros módulos**: `ai_chat.py` lee el estado IVA para inyectarlo al contexto del agente cuando el usuario pregunta sobre IVA.

---

#### `/presupuesto` — Presupuesto
**Archivo**: `routers/budget.py`

**Tarea**: CRUD simple de presupuesto mensual/anual por concepto.

**Se conecta con**: `database.py` (presupuesto)

**Conexiones con otros módulos**: **Módulo aislado**. No tiene conexión con Alegra ni con otros módulos. Solo lee/escribe en MongoDB.

---

#### `/dashboard` — Alertas y Feed de Eventos
**Archivo**: `routers/dashboard.py`

**Tarea**: Alertas proactivas, memoria del agente y feed de actividad.

| Endpoint | Descripción |
|----------|-------------|
| GET `/dashboard/alerts` | Facturas vencidas, bills próximos, IVA por vencer |
| GET `/agent/memory` | Patrones aprendidos por el agente (acciones recurrentes) |
| GET `/agent/memory/suggestions` | Sugerencias del mes anterior |
| GET `/notifications` | Notificaciones de webhooks de Alegra |
| GET `/events/recent` | Feed últimos eventos del bus |
| GET `/events/stats` | KPIs del día |

**Se conecta con**: `database.py` (agent_memory, notifications, roddos_events), `alegra_service.py` (alertas), `event_bus.py`

**Conexiones con otros módulos**: Lee datos de todos los módulos via eventos. No escribe en otros módulos.

---

#### `/telegram` — Bot de Telegram
**Archivo**: `routers/telegram.py`

**Tarea**: Integración con Telegram para registrar gastos enviando fotos de recibos.

| Endpoint | Descripción |
|----------|-------------|
| POST `/telegram/webhook` | **Público** (sin JWT). Recibe mensajes del bot de Telegram |
| GET/POST `/telegram/config` | Configura token y registra webhook automáticamente |
| DELETE `/telegram/config` | Elimina configuración |

**Flujo del Bot**:
1. Usuario envía foto/PDF al bot → `_process_file()` → descarga, llama `process_document_chat()` (Claude)
2. Claude retorna `document_proposal` → bot envía resumen al chat de Telegram
3. Usuario responde `/si` → `_handle_confirm()` → llama `process_chat()` + `execute_chat_action()`
4. Usuario responde `/no` → limpia sesión pendiente

**Se conecta con**: `ai_chat.py` (process_document_chat, process_chat, execute_chat_action), `database.py` (telegram_config, telegram_sessions, users)

**Conexiones con otros módulos**: Reutiliza toda la lógica del agente IA. Actúa como un cliente alternativo del chat (en lugar del frontend web).

---

#### `/audit` — Auditoría
**Archivo**: `routers/audit.py`

**Tarea**: Log de acciones de usuarios y exportación.

**Se conecta con**: `database.py` (audit_logs)

**Conexiones con otros módulos**: Todos los routers llaman `log_action()` de `dependencies.py` que inserta en `audit_logs`.

---

#### `/settings` — Configuración
**Archivo**: `routers/settings.py`

**Tarea**: Credenciales Alegra, modo demo, cuentas predeterminadas, webhook, Mercately.

| Endpoint | Descripción |
|----------|-------------|
| GET/POST `/settings/credentials` | Email + token de Alegra (admin only) |
| GET/PUT `/settings/demo-mode` | Activa/desactiva modo demo |
| GET/POST `/settings/default-accounts` | Cuentas contables por defecto por tipo de operación |
| POST `/settings/webhooks/register` | Registra webhook en Alegra para recibir eventos |
| GET/POST `/settings/mercately` | Credenciales WhatsApp (infraestructura lista, sin implementar) |

**Se conecta con**: `database.py` (alegra_credentials, default_accounts, webhook_config), `alegra_service.py`

---

### 3.7 Servicios Auxiliares del Backend

#### `auth.py` — Autenticación JWT
- `create_token(user_id, email, role)` → JWT con expiración 24h
- `verify_token(token)` → decodifica y valida
- `create_temp_token(user_id, email)` → token temporal 5min para flujo 2FA
- `hash_password()` / `verify_password()` → bcrypt

#### `security_service.py` — Seguridad 2FA
- `generate_totp_secret()` → genera secret TOTP (base32)
- `encrypt_secret(secret)` / `decrypt_secret(enc)` → Fernet encryption
- `verify_totp(enc_secret, code)` → verifica código de 6 dígitos
- `generate_qr_base64(secret, email)` → QR en base64 para Google Authenticator

#### `inventory_service.py` — Procesamiento PDF Motos
- `extract_motos_from_pdf(content, filename)` → extrae motos de PDFs Auteco vía Claude
- `register_moto_in_alegra(moto, service)` → crea ítem en catálogo Alegra

#### `dependencies.py` — Guards de FastAPI
- `get_current_user` → dependency que valida JWT y retorna user dict
- `require_admin` → dependency que además verifica rol admin
- `log_action()` → helper para audit log

#### `database.py` — Conexión MongoDB
- Conexión única vía Motor async (`AsyncIOMotorClient`)
- Exporta `db` (cliente de base de datos) y `client`
- Todas las colecciones se acceden como `db.nombre_coleccion`

#### `models.py` — Modelos Pydantic
- `ChatMessageRequest` — request del chat (session_id, message, file_content opcional)
- `LoginRequest`, `SaveCredentialsRequest`, `DemoModeRequest`
- `SaveDefaultAccountsRequest`, `DefaultAccountItem`
- `BaseDocument` — clase base con `to_mongo()` / `from_mongo()`

---

## 4. FRONTEND — PÁGINAS Y COMPONENTES

### 4.1 Estructura de Carpetas
```
frontend/src/
├── App.js              ← Router principal (React Router v6)
├── contexts/
│   ├── AuthContext.js  ← JWT, login, logout, axios instance con auth
│   └── AlegraContext.js← Cuentas, contactos, cuentas bancarias de Alegra
├── pages/              ← 20+ páginas de la aplicación
├── components/
│   ├── Layout.js       ← Navbar/sidebar + <Outlet>
│   ├── AlegraAccountSelector.js  ← Selector de cuentas con búsqueda
│   ├── JournalEntryPreview.js    ← Preview de asiento contable
│   ├── ProactiveAlerts.js        ← Alertas del dashboard
│   └── ui/             ← Componentes Shadcn/UI (button, input, etc.)
├── hooks/
│   └── use-toast.js    ← Hook de notificaciones
└── utils/
    ├── exportUtils.js  ← Exportar a Excel/CSV
    └── formatters.js   ← Formatos de moneda, fecha
```

### 4.2 Contextos Globales

#### `AuthContext.js`
- Provee: `user`, `token`, `login()`, `logout()`, `setAuth()`, `api` (axios con auth), `loading`
- El objeto `api` es un axios instance con `baseURL = REACT_APP_BACKEND_URL/api` y interceptor que añade `Authorization: Bearer {token}`
- Auto-redirige a `/login` en error 401
- **Consumido por**: TODAS las páginas que hacen llamadas al backend

#### `AlegraContext.js`
- Se auto-carga al login via `useEffect` en `AlegraProvider`
- Provee: `accounts` (árbol), `flatAccounts`, `contacts`, `bankAccounts`, `connectionStatus`, `isDemoMode`
- Métodos: `searchAccounts()`, `getDefaultAccount()`, `checkConnection()`, `loadAccounts()`
- **Consumido por**: Páginas de facturación, causación, conciliación bancaria, configuración

### 4.3 Páginas Principales

#### `AgentChatPage.js` — LA PÁGINA PRINCIPAL (más compleja)
**Ruta**: `/agente-contable` (home redirect)
**Descripción**: Interfaz de chat a pantalla completa con el agente IA.

**Estado local principal**:
```javascript
messages[]         // Historial del chat
input              // Texto del input
isLoading          // Spinner de respuesta IA
pendingAction      // Acción propuesta por IA esperando confirmación
executing          // Ejecutando acción en Alegra
sessionId          // ID único de sesión (UUID)
attachedFile       // Archivo adjunto (base64 + preview)
selectedDocType    // Tipo de documento seleccionado (chips)
```

**Sub-componentes internos**:

| Componente | Descripción |
|-----------|-------------|
| `MessageBubble` | Renderiza mensajes usuario/IA con Markdown, soporte tabla |
| `TypingIndicator` | Indicador "escribiendo..." animado |
| `ExecutionCard` | **Tarjeta de confirmación** antes de ejecutar en Alegra. Muestra tabla débito/crédito para causaciones, items para facturas. Botones Confirmar/Cancelar |
| `TerceroCard` | **Tarjeta de nuevo tercero**. Se muestra cuando la IA detecta un proveedor/cliente inexistente. Permite editar nombre/NIT antes de crearlo en Alegra. Maneja `next_pending_action` |
| `DocumentProposalCard` | Muestra los datos extraídos de un documento analizado |
| `DOC_TYPE_OPTIONS` | Chips de tipo de documento (Auto, Factura servicio, Compra motos, Pago/Cuota) |

**Flujo de mensajes**:
1. Usuario escribe → `sendMessage()` → POST `/api/chat/message`
2. Backend retorna `{message, pending_action}`
3. Si `pending_action.type === "crear_contacto"` → renderiza `TerceroCard`
4. Si otro tipo → renderiza `ExecutionCard`
5. Usuario confirma → POST `/api/chat/execute-action`
6. Si respuesta tiene `next_pending_action` → auto-set como nuevo `pendingAction`

---

#### `Dashboard.js`
**Ruta**: `/dashboard`
**Conexión Backend**: `/dashboard/alerts`, `/events/recent`, `/loanbook/stats`, `/inventario/stats`
**Descripción**: KPIs resumen, alertas proactivas, feed de actividad reciente.

#### `Login.js`
**Ruta**: `/login`
**Descripción**: Formulario login + flujo 2FA (muestra input para código TOTP si está habilitado).
**Conexión Backend**: `/auth/login`, `/auth/2fa/login`

#### `Loanbook.js`
**Ruta**: `/loanbook`
**Conexión Backend**: `/loanbook`, `/loanbook/stats`
**Descripción**: Vista de todos los planes de pago con filtros, KPIs, tabla de cuotas. Permite registrar pagos manuales y entrega física.

#### `Cartera.js`
**Ruta**: `/cartera`
**Conexión Backend**: `/cartera/cola-remota`, `/cartera/semanal`, `/cartera/mensual`, `/cartera/clientes`, `/cartera/gestiones`
**Descripción**: Tres vistas: Cola de Gestión Remota (URGENTE/HOY/PREVENTIVO), vista semanal de cuotas, comportamiento de clientes.

#### `InventarioAuteco.js`
**Ruta**: `/inventario-auteco`
**Conexión Backend**: `/inventario/motos`, `/inventario/stats`, `/inventario/upload-pdf`
**Descripción**: Tabla de motos con estados (Disponible/Vendida/Entregada), carga de PDFs Auteco.

#### `Repuestos.js`
**Ruta**: `/repuestos`
**Conexión Backend**: `/repuestos/catalogo`, `/repuestos/facturas`, `/repuestos/stats`
**Descripción**: Catálogo de repuestos, ajuste de stock, facturación.

#### `FacturacionVenta.js` / `FacturacionCompra.js`
**Rutas**: `/facturacion-venta`, `/facturacion-compra`
**Conexión Backend**: `/alegra/invoices`, `/alegra/bills`
**Descripción**: Páginas de consulta de facturas en Alegra. Principalmente lectura.

#### `CausacionEgresos.js` / `CausacionIngresos.js`
**Rutas**: `/causacion-egresos`, `/causacion-ingresos`
**Conexión Backend**: `/alegra/journal-entries`
**Descripción**: Asientos contables filtrados por tipo.

#### `Impuestos.js`
**Ruta**: `/impuestos`
**Conexión Backend**: `/impuestos/iva-status`, `/impuestos/config`
**Descripción**: Estado IVA cuatrimestral con proyección.

#### `Settings.js`
**Ruta**: `/configuracion`
**Conexión Backend**: `/settings/*`, `/telegram/config`, `/alegra/test-connection`
**Descripción**: Credenciales Alegra, modo demo, cuentas predeterminadas, configuración Telegram.

#### Páginas con implementación básica/pendiente
- `Nomina.js` → Nómina (UI básica)
- `Prestaciones.js` → Prestaciones sociales
- `EstadoResultados.js` → P&L desde Alegra
- `EgresosClasificados.js` → Clasificación de egresos
- `Presupuesto.js` → CRUD presupuesto
- `Retenciones.js` → Control retenciones
- `RegistroCuotas.js` → Registro manual de cuotas
- `ConciliacionBancaria.js` → Reconciliación bancaria con Alegra

---

## 5. BASE DE DATOS — COLECCIONES MONGODB

| Colección | Módulo Escritura | Módulo Lectura | Descripción |
|-----------|-----------------|----------------|-------------|
| `users` | server.py (startup), auth router | auth router, dependencies | Usuarios del sistema |
| `alegra_credentials` | settings router | alegra_service | Credenciales API Alegra |
| `chat_messages` | ai_chat.py | chat router (history) | Historial conversacional del agente |
| `agent_memory` | ai_chat.py (execute), loanbook router | dashboard router, ai_chat.py (gather_accounts_context) | Patrones aprendidos para sugerencias |
| `loanbook` | post_action_sync.py, loanbook router | loanbook router, cartera router, ai_chat.py | Planes de pago de motos |
| `cartera_pagos` | post_action_sync.py, loanbook router | cartera router | Registro de pagos de cuotas |
| `inventario_motos` | post_action_sync.py, inventory router | ai_chat.py, inventory router | Inventario físico de motos |
| `repuestos_catalogo` | repuestos router | repuestos router | Catálogo de repuestos |
| `repuestos_facturas` | repuestos router | repuestos router | Facturas de repuestos |
| `repuestos_movimientos` | repuestos router | - | Movimientos de stock |
| `roddos_events` | event_bus.py | dashboard router | Bus de eventos de negocio |
| `audit_logs` | dependencies.py (log_action), post_action_sync.py | audit router | Log de todas las acciones |
| `notifications` | server.py (webhook) | dashboard router | Notificaciones de Alegra |
| `iva_config` | taxes router | taxes router, ai_chat.py | Configuración período IVA |
| `presupuesto` | budget router | budget router | Presupuesto mensual |
| `default_accounts` | settings router | AlegraContext.js | Cuentas contables por defecto |
| `telegram_config` | telegram router | telegram router | Token y webhook del bot |
| `telegram_sessions` | telegram router | telegram router | Propuestas pendientes por chat_id |
| `gestiones_cartera` | cartera router | cartera router | Intentos de contacto remoto |
| `webhook_config` | settings router | settings router | Config webhook de Alegra |
| `mercately_config` | settings router | settings router | Credenciales WhatsApp (pendiente) |

### Índices MongoDB (creados en startup)
```javascript
agent_memory:     [user_id + tipo], [frecuencia_count DESC], [ultima_ejecucion DESC]
audit_logs:       [timestamp DESC], [user_email + timestamp DESC]
chat_messages:    [session_id + timestamp ASC]
inventario_motos: [estado], [chasis UNIQUE SPARSE]
```

---

## 6. INTEGRACIONES EXTERNAS

### 6.1 Alegra ERP (INTEGRACIÓN PRINCIPAL)
- **Base URL**: `https://api.alegra.com/api/v1`
- **Auth**: Basic Auth (email:token → base64)
- **Modo Demo**: Si `is_demo_mode=true`, retorna datos de `mock_data.py`
- **Caché**: Settings 60s, cuentas 5min (in-memory por proceso)

**Endpoints críticos y su uso**:
| Endpoint Alegra | Cuándo se usa |
|----------------|--------------|
| POST `/invoices` | Venta de moto (IA o directo) |
| POST `/bills` | Compra de motos/productos físicos del catálogo |
| POST `/journals` | Causaciones de servicios, gastos, honorarios |
| POST `/payments` | Registro de cuota de Loanbook |
| POST `/contacts` | Crear proveedor/cliente nuevo |
| GET `/categories` | Plan de cuentas (árbol NIIF) |
| GET `/contacts` | Contexto para el agente IA |
| GET `/items` | Catálogo para bills |

**Distinción crítica**:
> `/bills` → SOLO productos físicos del catálogo con `id` numérico
> `/journals` → servicios, arrendamiento, honorarios, gastos que no son productos

### 6.2 Claude Sonnet (IA)
- **Modelo**: `claude-sonnet-4-5-20250929`
- **Librería**: `emergentintegrations` (Emergent LLM Key)
- **Clase**: `LlmChat` con `session_id` para memoria de conversación
- **Entrada**: Texto + opcionalmente `FileContent` (imagen/PDF en base64)
- **Salida**: Texto Markdown + bloque `<action>JSON</action>` o `<document_proposal>JSON</document_proposal>`

**Dos modos de uso**:
1. **Chat conversacional** (`process_chat`): Sesión persistente con `session_id`, contexto Alegra inyectado en system prompt
2. **Análisis de documentos** (`process_document_chat`): Sesión descartable (`session_id-doc-{random}`), prompt especializado para extracción de datos de documentos

### 6.3 Telegram Bot
- **API**: `https://api.telegram.org`
- **Auth**: Token del bot de Telegram
- **Webhook**: Se auto-registra al guardar el token vía `setWebhook`
- **Estado**: Infraestructura completa. **Pendiente prueba E2E**

### 6.4 Google Authenticator (TOTP)
- **Librería**: `pyotp`
- **Algoritmo**: TOTP standard (RFC 6238)
- **Almacenamiento**: Secret encriptado con Fernet en `users.totp_secret_enc`
- **Estado**: Completamente funcional para el usuario admin

---

## 7. FLUJOS DE DATOS CLAVE

### 7.1 Ciclo de Vida de un Mensaje de Chat

```
[Usuario escribe]
      │
      ▼
AgentChatPage.js → POST /api/chat/message
      │
      ▼
chat.py router → ai_chat.process_chat()
      │
      ├─ gather_context() → AlegraService.request(contacts, bank-accounts, ...)
      │                   → db.inventario_motos (si contexto moto)
      │                   → db.loanbook (si contexto cuotas)
      │                   → IVA status (si pregunta sobre IVA)
      │
      ├─ gather_accounts_context() → AlegraService.get_accounts_from_categories()
      │                            → db.agent_memory (patrones aprendidos)
      │
      ├─ Construye system prompt con todo el contexto
      │
      ├─ LlmChat.send_message(user_message) → Claude API
      │
      ├─ Parsea <action> block del response
      │
      ├─ Guarda user + assistant messages en db.chat_messages
      │
      └─ Retorna {message, pending_action}

[Frontend muestra ExecutionCard o TerceroCard]
      │
      ▼ (usuario confirma)
      │
AgentChatPage.js → POST /api/chat/execute-action
      │
      ▼
chat.py router → ai_chat.execute_chat_action()
      │
      ├─ AlegraService.request(endpoint, "POST", payload)
      │
      ├─ post_action_sync() → actualiza inventario/loanbook/cartera
      │                     → emit_event() → roddos_events
      │                     → audit_log
      │
      └─ Retorna {success, id, sync_messages, [next_pending_action]}
```

### 7.2 Flujo de Venta de Moto a Crédito (End-to-End)

```
1. Usuario: "Vende Honda CB190R a Juan Pérez, plan P39S, cuota $190.000, inicial $500.000"

2. Agente IA:
   - Verifica disponibilidad en INVENTARIO_DISPONIBLE del contexto
   - Verifica cliente en CONTACTOS_DISPONIBLES
   - Si cliente no existe → propone crear_contacto primero
   - Construye payload crear_factura_venta con _metadata completo

3. ExecutionCard → Usuario confirma

4. execute_chat_action("crear_factura_venta"):
   → POST /invoices en Alegra
   → post_action_sync():
      → inventario_motos.update(estado:"Vendida")
      → loanbook.insert({estado:"pendiente_entrega", cuotas:[inicial_pagada, ...sin_fecha x39]})
      → emit_event("factura.venta.creada")
      → audit_log

5. Resultado: Factura en Alegra + Loanbook creado en RODDOS

6. Usuario: "Entregué la moto LB-2026-0001, fecha 2026-02-10"

7. Agente IA: propone registrar_entrega

8. execute_chat_action("registrar_entrega"):
   → loanbook.register_entrega():
      → calcula primera cuota = primer miércoles >= 2026-02-17
      → genera 39 fechas miércoles consecutivas
      → estado: "activo"
      → inventario_motos.update(estado:"Entregada")
   → emit_event("loanbook.activado")

9. Cliente ahora aparece en cola-remota de Cartera
```

### 7.3 Flujo de Nuevo Tercero (TerceroCard)

```
1. Usuario: "Causar arrendamiento $3M a Inmobiliaria XYZ NIT 900123456"

2. Agente IA:
   - Verifica "Inmobiliaria XYZ" en CONTACTOS_DISPONIBLES → NO encontrado
   - Emite <action> tipo "crear_contacto" con _next_action = crear_causacion

3. Frontend detecta action.type === "crear_contacto" → renderiza TerceroCard
   (No ExecutionCard)

4. TerceroCard muestra: nombre, NIT, tipo, cuenta sugerida
   Usuario puede editar NIT antes de confirmar

5. Usuario confirma → POST /api/chat/execute-action {action:"crear_contacto", payload}

6. execute_chat_action("crear_contacto"):
   → POST /contacts en Alegra → retorna {id: 12345}
   → Reemplaza __NEW_CONTACT_ID__ con 12345 en next_action.payload
   → Retorna {success, next_pending_action: {type:"crear_causacion", payload:{provider:{id:12345},...}}}

7. Frontend recibe next_pending_action → lo setea como nuevo pendingAction
   → Renderiza ExecutionCard con la causación completa

8. Usuario confirma causación → flujo normal
```

### 7.4 Flujo de Análisis de Documento (Telegram o Web)

```
Usuario sube foto de factura
      │
      ▼
process_document_chat():
  - Carga cuentas hoja del plan Alegra
  - Carga loanbooks activos (para detectar pagos de cuota)
  - Llama Claude con imagen + DOCUMENT_ANALYSIS_SYSTEM_PROMPT
  - Claude analiza y retorna texto + <document_proposal>JSON</document_proposal>
  - Parsea proposal: {tipo_documento, proveedor, nit, fecha, montos, cuenta_sugerida, accion_contable}

      │
      ├── Si VÍA WEB → retorna {message, document_proposal, pending_action}
      │   DocumentProposalCard muestra datos extraídos
      │   ExecutionCard permite ejecutar la acción
      │
      └── Si VÍA TELEGRAM → _format_proposal() → mensaje HTML al bot
          Usuario responde /si → process_chat() + execute_chat_action()
          Usuario responde /no → limpia sesión pendiente
```

---

## 8. MATRIZ DE CONEXIONES ENTRE MÓDULOS

### Leyenda: ✅ Conexión directa | 📖 Solo lectura | 🔔 Via evento bus | ❌ Sin conexión

| Módulo \ Conecta con | ai_chat | alegra_svc | post_sync | event_bus | loanbook | cartera | inventario | repuestos | dashboard | taxes | telegram |
|----------------------|---------|-----------|-----------|-----------|----------|---------|------------|-----------|-----------|-------|----------|
| **ai_chat.py** | — | ✅ Contexto+Exec | ✅ Post-exec | ❌ | 📖 Context | ❌ | 📖 Context | ❌ | ❌ | 📖 IVA | ❌ |
| **alegra_service** | ✅ | — | ❌ | ❌ | ✅ Pagos | ❌ | ✅ Items | ✅ Facturas | ❌ | ✅ Inv/Bills | ❌ |
| **post_action_sync** | ❌ | ❌ | — | ✅ Emite | ✅ Escribe | ✅ Escribe | ✅ Escribe | ❌ | ❌ | ❌ | ❌ |
| **event_bus** | ❌ | ❌ | ❌ | — | ❌ | ❌ | ❌ | ❌ | 📖 Feed | ❌ | ❌ |
| **router/loanbook** | ❌ | ✅ Pagos | ✅ Llamado | ✅ Emite | — | 📖 usa helper | ✅ Estado | ❌ | ❌ | ❌ | ❌ |
| **router/cartera** | ❌ | ❌ | ❌ | ❌ | 📖 Lee datos | — | ❌ | ❌ | ❌ | ❌ | ❌ |
| **router/inventario** | ❌ | ✅ Items | ❌ | ❌ | ❌ | ❌ | — | ❌ | ❌ | ❌ | ❌ |
| **router/repuestos** | ❌ | ✅ Facturas | ❌ | ✅ Emite | ❌ | ❌ | ❌ | — | ❌ | ❌ | ❌ |
| **router/dashboard** | ❌ | ✅ Alertas | ❌ | ✅ Lee feed | ❌ | ❌ | ❌ | ❌ | — | ❌ | ❌ |
| **router/taxes** | 📖 IA lee | ✅ Inv/Bills | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — | ❌ |
| **router/telegram** | ✅ Reutiliza | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | — |
| **router/presupuesto** | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |
| **router/settings** | ❌ | ✅ Invalida caché | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ | ❌ |

### Observación clave:
- **`ai_chat.py` + `alegra_service.py` + `post_action_sync.py`** forman el **núcleo** del sistema y están fuertemente acoplados.
- **`cartera`** es el módulo más **dependiente pero no acoplado** — solo lee de `loanbook` sin escribir en él directamente.
- **`presupuesto`** está completamente **aislado** — no tiene conexión real con el resto del sistema.
- **`repuestos`** está **semi-aislado** — solo se conecta con Alegra y el event_bus.
- **`telegram`** es un **cliente alternativo** del agente IA — no tiene lógica propia, reutiliza completamente `ai_chat.py`.

---

## 9. ANÁLISIS DE BRECHAS Y PRODUCTO FINAL IDEAL

### 9.1 Lo que EXISTE y FUNCIONA ✅
- Agente IA conversacional completo (texto + documentos)
- Flujo de venta de moto + creación automática de Loanbook
- Flujo de entrega + generación de fechas de cuotas (miércoles)
- Flujo de causaciones contables con tabla débito/crédito
- Detección y creación de nuevos terceros (TerceroCard)
- Cartera: cola remota, vista semanal/mensual, comportamiento de clientes
- Inventario de motos con carga de PDFs Auteco
- Control IVA cuatrimestral
- 2FA con Google Authenticator
- Modo demo con datos ficticios
- Bot de Telegram (infraestructura completa)

### 9.2 Lo que EXISTE pero NO está completo ⚠️
| Módulo | Estado | Brecha |
|--------|--------|--------|
| **Telegram** | Infraestructura lista | No probado E2E. Sin gestión de sesiones multi-usuario |
| **Presupuesto** | CRUD funciona | Sin comparativo real vs ejecutado (no conecta con Alegra) |
| **Nómina/Prestaciones** | UI básica | Sin lógica real de cálculo NIIF Colombia |
| **Estado de Resultados** | Existe | Sin integración real con Alegra journal-entries |
| **Retenciones** | Existe | Sin automatización de declaración |
| **Conciliación Bancaria** | Existe | Parcialmente implementado |
| **Repuestos** | Funcional | Sin enlace con Loanbook o ventas de motos |

### 9.3 Lo que FALTA para el Producto Final Ideal 🎯
| Prioridad | Feature | Impacto |
|-----------|---------|---------|
| **P0** | Pruebas E2E Telegram completas | Canal de captura de gastos sin computador |
| **P0** | Resolución DIAN vencida (2026-03-06) en Alegra | Facturas quedan en borrador |
| **P1** | Dashboard de KPIs en tiempo real (WebSockets o polling) | Visibilidad operacional |
| **P1** | Directorio de Terceros (CRUD Alegra contactos desde RODDOS) | Gestión de proveedores/clientes |
| **P1** | Integración WhatsApp (Mercately) | Canal de cobros y comunicación con clientes |
| **P1** | Nómina y Prestaciones reales | Cumplimiento legal |
| **P2** | Estado de Resultados automático desde Alegra | Informes gerenciales |
| **P2** | Motor de alertas activo (detección automática de mora) | Cobranza proactiva |
| **P2** | Multi-empresa / Multi-usuario con roles granulares | Escalabilidad |
| **P3** | Notificaciones push al agente de cobros | Eficiencia cobranza |
| **P3** | Integración DIAN para declaración IVA | Automatización fiscal |
| **P3** | App móvil (PWA o React Native) | Movilidad para vendedores |

### 9.4 Deuda Técnica Identificada
| Item | Descripción | Riesgo |
|------|-------------|--------|
| Resolución DIAN | Vence 2026-03-06. Facturas en borrador | **ALTO** — Facturas no válidas |
| Event Bus pasivo | Los eventos se guardan pero nadie los "escucha" activamente | Medio — Oportunidad para alertas automáticas |
| Sin WebSockets | Actualizaciones en tiempo real no están implementadas | Bajo — Requiere polling manual |
| Presupuesto aislado | No conecta con ejecución real en Alegra | Bajo — Funcionalidad incompleta |
| Tests automatizados | Pocos tests de backend (`/tests/`). Sin tests de frontend | Medio — Riesgo de regresiones |

---

## GLOSARIO
| Término | Significado en RODDOS |
|---------|----------------------|
| **Loanbook** | Contrato de crédito para compra de moto. Código formato `LB-AAAA-NNNN` |
| **Causación** | Asiento contable de gasto/ingreso sin transacción de caja (devenga el gasto) |
| **Plan P39S/P52S/P78S** | Plan de 39/52/78 cuotas semanales (los miércoles) |
| **TerceroCard** | Componente UI que pide crear un proveedor/cliente nuevo en Alegra |
| **ExecutionCard** | Componente UI de confirmación antes de ejecutar en Alegra |
| **Cola Remota** | Queue priorizada de clientes a contactar (URGENTE/HOY/PREVENTIVO) |
| **Modo Demo** | Usa datos ficticios de `mock_data.py` en lugar de la API real de Alegra |
| **Emergent LLM Key** | Clave universal de Emergent para Claude/GPT/Gemini |
| **NIIF Colombia** | Normas Internacionales de Información Financiera adaptadas a Colombia |
| **UVT** | Unidad de Valor Tributario (2025: $49.799) — base para retenciones |
