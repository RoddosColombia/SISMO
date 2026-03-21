# RODDOS Contable IA

Agente Contador con IA integrado con Alegra ERP para gestión contable, inventario de motos y cartera de créditos.
Desarrollado para concesionario de motos Auteco — Bogotá D.C., Colombia.

## Estado del proyecto

| Campo | Valor |
|-------|-------|
| Versión | BUILD 18 — completado |
| Calificación | **8.63 / 10** |
| Último smoke test | 16-mar-2026 — 10/10 ✅ |
| Loanbooks activos | 10 |
| Inventario motos | 33 (VINs reales) |
| Cartera total | $94,118,900 COP |

## Stack tecnológico

| Capa | Tecnología |
|------|-----------|
| Frontend | React 18 + TypeScript + Tailwind CSS + Shadcn/UI |
| Backend | FastAPI (Python 3.11) + Motor (async MongoDB) |
| Base de datos | MongoDB |
| IA | Claude Sonnet 4.5 vía Emergent LLM Key |
| ERP | Alegra API v1 |
| WhatsApp | Mercately |
| Builder | emergent.sh |

## Módulos implementados

| Módulo | Ruta | Descripción |
|--------|------|-------------|
| Agente Contador | `/agente-contable` | Chat IA con acceso a Alegra, inventario y cartera |
| CFO Estratégico | `/cfo-estrategico` | Chat CFO con análisis de deuda, déficit y proyecciones |
| Dashboard | `/dashboard` | KPIs en tiempo real + ventas del mes con progreso de meta |
| Panel CFO | `/cfo` | Semáforo financiero (Caja, Cartera, Ventas, Roll Rate, Impuestos) |
| Presupuesto | `/presupuesto` | Plan de deudas Auteco + gastos operativos + E&R mensual |
| Impuestos | `/impuestos` | Calendario fiscal IVA cuatrimestral, ReteFuente, ReteICA |
| Motos | `/inventario-auteco` | 33 motos TVS con VINs reales, estado Disponible/Vendida/Entregada |
| Loanbook | `/loanbook` | 10 créditos activos, panel entregas pendientes, registro de pagos |
| RADAR | `/radar` | Cola de cobranza semanal, gestiones y PTPs |
| Configuración | `/configuracion` | Alegra, Mercately, usuarios, webhooks, scheduler |

## Cómo ejecutar el proyecto

### Requisitos previos
- Node.js 18+ y Yarn
- Python 3.11+
- MongoDB 6.0+
- Cuenta Alegra con token API
- Emergent LLM Key (o API key de Anthropic)

### Configuración

```bash
# 1. Clonar el repositorio
git clone https://github.com/tu-usuario/roddos-contable-ia.git
cd roddos-contable-ia

# 2. Configurar variables de entorno
cp .env.example backend/.env
cp .env.example frontend/.env
# Editar backend/.env y frontend/.env con valores reales

# 3. Backend
cd backend
pip install -r requirements.txt
uvicorn server:app --host 0.0.0.0 --port 8001 --reload

# 4. Frontend (en otra terminal)
cd frontend
yarn install
yarn start
```

### Variables de entorno obligatorias

**backend/.env:**
```
MONGO_URL=mongodb://localhost:27017
DB_NAME=roddos_contable
ALEGRA_EMAIL=email@empresa.com
ALEGRA_TOKEN=tu-token-alegra
ALEGRA_WEBHOOK_SECRET=tu-secret
JWT_SECRET=secreto-largo-seguro
EMERGENT_LLM_KEY=sk-ant-...
APP_URL=https://tu-dominio.com
CORS_ORIGINS=http://localhost:3000
```

**frontend/.env:**
```
REACT_APP_BACKEND_URL=http://localhost:8001
```

## Integración Mercately (WhatsApp)

La integración de Mercately permite enviar mensajes WhatsApp automáticamente en dos contextos:

### 1. Configuración del API Key

1. Accede a tu dashboard de Mercately: https://mercately.com
2. Navega a **Configuración → API Keys**
3. Copia tu API Key (ej: `9965b1d2f06aced942a448a1eff3b2eb`)
4. En SISMO, ve a **Configuración → Mercately**
5. Pega el API Key en el campo correspondiente
6. Haz clic en **Probar Conexión** para verificar que funciona

### 2. Configurar números de ejecutivos (CEO y CGO)

Para recibir notificaciones de operaciones críticas:

**CEO (Chief Executive Officer)** — Alertas financieras y críticas:
1. Ve a **Configuración → Mercately** en SISMO
2. Ingresa número WhatsApp en campo "Número CEO": `57XXXXXXXXXX`
3. Recibirá: movimientos ambiguos + resumen semanal + alertas de Alegra caído

**CGO (Chief Growth Officer)** — Alertas operativas:
1. En el mismo campo de Configuración → Mercately
2. Ingresa número WhatsApp en campo "Número CGO": `57XXXXXXXXXX`
3. Recibirá: movimientos ambiguos + resumen semanal + alertas operativas

**Mi teléfono RODDOS** — Soporte operativo interno:
1. Campo "Número WhatsApp RODDOS"
2. Número principal de la empresa para notificaciones internas

Ejemplo:
- RODDOS: `573001234567`
- CEO: `573115551234` (Andrés)
- CGO: `573159876543` (Gerente de Operaciones)

### 3. Casos de uso automáticos

**A. Notificaciones de Movimientos Ambiguos (Clasificación Contable)**

Cuando se carga un extracto bancario y hay movimientos con baja confianza:
- El sistema intenta clasificarlos automáticamente
- Si confianza < 70%, se solicita confirmación vía WhatsApp
- **Destinatarios:** CEO + CGO + números en resumen semanal
- Mensaje incluye:
  - Monto de la transacción
  - Descripción del movimiento
  - Cuenta contable sugerida
  - % de confianza en la clasificación
  - Solicitud de confirmación (SI/NO)

Ejemplo:
```
📊 CONFIRMACIÓN DE CLASIFICACIÓN CONTABLE

Transacción:
• Monto: $450,000
• Descripción: PAGO PSE TIGO
• Proveedor: TIGO

Clasificación Sugerida:
• Cuenta: 5318 - Servicios públicos
• Confianza: 62%

¿Confirmas esta clasificación?
Responde: SI o NO
```

**B. Recordatorios de Cuotas (Loanbook)**

El scheduler envía mensajes WhatsApp a clientes en estos momentos:
- **Lunes 8am**: Recordatorio D-2 a clientes que pagan miércoles
- **Miércoles 8am**: Recordatorio día de vencimiento
- **Jueves 9am**: Alerta de mora D+1 (cuota no pagada)
- **Sábado 9am**: Alerta de mora severa (+30 días)

**C. Alertas de Operación del Sistema (CEO y CGO)**

CEO y CGO reciben notificaciones en estos casos:

| Evento | Destinatario | Horario | Descripción |
|--------|-------------|---------|-------------|
| Movimientos ambiguos sin clasificar | CEO + CGO | Inmediato | Solicitud de confirmación contable |
| Resumen semanal de pendientes | CEO + CGO + otros | Viernes 17:00 | Síntesis de movimientos, cuotas, cartera |
| Alegra caído > 30 min | CEO + CGO | Inmediato | Alerta crítica — servicio de contabilidad fuera |

Ambos ejecutivos reciben simultáneamente para asegurar redundancia en casos críticos.

### 4. Probar la integración

**Endpoint de prueba:**
```bash
POST /api/settings/mercately/test
Authorization: Bearer <tu-jwt-token>
```

**Respuesta exitosa:**
```json
{
  "conectado": true,
  "mensaje_enviado": true,
  "detalles": "Conexión exitosa con Mercately ✓ — Mensaje de prueba enviado",
  "phone_configurado": "1234"
}
```

Si recibes un mensaje de prueba en tu WhatsApp, la integración está funcionando correctamente.

### 5. Seguridad

⚠️ **IMPORTANTE:**
- El API Key nunca se guarda en variables de entorno — se almacena en MongoDB configuracion.mercately_config
- Los logs de la aplicación NO incluyen el API Key (se trunca a últimos 4 dígitos)
- El número de teléfono se registra solo en los últimos 4 dígitos en los logs
- No guardes el API Key en el repositorio ni en archivos `.env`

### 6. Troubleshooting

**"No hay API Key configurada"**
- Ve a Configuración → Mercately
- Pega tu API Key real desde Mercately Dashboard

**"API Key inválida (401)"**
- Verifica que copiaste el API Key completo sin espacios
- Regenera el API Key en Mercately Dashboard y prueba de nuevo

**"Mercately no responde (timeout)"**
- Verifica tu conexión a internet
- Comprueba que Mercately esté en funcionamiento: https://status.mercately.com

**No recibo mensajes en WhatsApp**
- Verifica que tu número esté en formato correcto: `57XXXXXXXXXX`
- Asegúrate de que el número tiene el código de país (57 para Colombia)
- El número debe ser el mismo que está registrado en tu cuenta Mercately

## Conciliación Bancaria Automática

La conciliación automática procesa extractos bancarios y crea journals en Alegra:

### Flujo de Procesamiento

1. **Cargar extracto bancario** → POST `/api/conciliacion/cargar-extracto`
   - Soporta BBVA, Bancolombia, Davivienda, Nequi
   - El sistema clasifica automáticamente cada movimiento
   - Confianza ≥ 70% → Crea journal en Alegra automáticamente
   - Confianza < 70% → Guarda en pendientes para revisión manual

2. **Crear journals en Alegra**
   - El background task procesa cada movimiento clasificado
   - POST `/journals` a Alegra con debit/credit
   - GET verificación para confirmar creación
   - Inserta registro en MongoDB `conciliacion_movimientos_procesados` con:
     - `hash`: MD5(banco + fecha + descripcion + monto)
     - `journal_id`: ID del journal en Alegra
     - `procesado_at`: ISO timestamp

3. **Movimientos ambiguos**
   - Se guardan en `contabilidad_pendientes` para resolución manual
   - Endpoint POST `/api/conciliacion/resolver/{id}` permite reclasificar

### Reconstruir Audit Trail desde Alegra

Si el audit trail en MongoDB se ve comprometido o vacío, usa el endpoint de backfill:

**Endpoint:**
```bash
POST /api/conciliacion/backfill-desde-alegra
Authorization: Bearer <jwt-token>
```

**Body:**
```json
{
  "banco": "bbva",
  "mes": "2026-01"
}
```

**Respuesta:**
```json
{
  "status": "success",
  "banco": "bbva",
  "mes": "2026-01",
  "total_journals_alegra": 111,
  "total_insertados": 105,
  "total_existentes": 6,
  "mensaje": "Backfill completado: 105 nuevos + 6 existentes"
}
```

**Lógica:**
- Consulta todos los journals en Alegra
- Filtra por rango de fecha (mes-01 a mes-31)
- Extrae banco del texto de observations
- Calcula hash: MD5(banco + fecha + observations + monto)
- Upsert en MongoDB si no existe ese hash
- NO modifica journals existentes

**Casos de uso:**
- Recuperar datos después de una limpieza accidental de MongoDB
- Validar completitud del audit trail
- Reconstruir histórico de conciliación para un mes específico
- Reconciliar discrepancias entre Alegra y MongoDB

**Permisos:** Requiere rol de admin

## Colecciones MongoDB

| Colección | Descripción |
|-----------|-------------|
| `loanbook` | Créditos activos/pendientes con plan de cuotas semanal |
| `inventario_motos` | 33 motos TVS con VINs, motores, estado y precio |
| `cartera_pagos` | Registro histórico de pagos de cuotas |
| `cartera_gestiones` | Gestiones de cobranza y PTPs |
| `conciliacion_movimientos_procesados` | Audit trail: movimientos causados con journal_id |
| `conciliacion_reintentos` | Movimientos pendiente reintento (error 503/429) |
| `contabilidad_pendientes` | Movimientos ambiguos (confianza < 70%) esperando resolución manual |
| `cfo_deudas` | Deudas no productivas (Auteco + operativas) |
| `cfo_cache` | Caché de panel CFO (TTL 5 min, invalida en eventos) |
| `cfo_configuracion` | Parámetros CFO: meta ventas, gastos fijos, nómina |
| `cfo_instrucciones` | Reglas de negocio para el agente CFO |
| `cfo_compromisos` | Compromisos de pago registrados por el CFO |
| `proveedores_config` | ReteFuente y ReteICA por proveedor |
| `roddos_events` | Log de eventos: ventas, pagos, entregas, webhooks |
| `agent_errors` | Errores del agente para debugging |
| `contactos` | Clientes con perfil 360° + historial CRM |

## Endpoints principales

### Auth
```
POST /api/auth/login          Login con email/password → JWT
POST /api/auth/register       Crear usuario
GET  /api/auth/me             Perfil del usuario autenticado
```

### Inventario
```
GET  /api/inventario/motos    Listar motos con filtros
GET  /api/inventario/stats    Resumen: total, disponibles, vendidas, entregadas
POST /api/inventario/motos    Crear moto
PUT  /api/inventario/motos/{id} Actualizar moto
```

### Loanbook (Créditos)
```
GET  /api/loanbook            Listar créditos (con filtros)
GET  /api/loanbook/stats      KPIs: activos, cartera, pendientes entrega
POST /api/loanbook            Crear crédito
PUT  /api/loanbook/{id}/entrega  Registrar entrega → activa crédito + genera cuotas
POST /api/loanbook/{id}/pago  Registrar pago de cuota
GET  /api/loanbook/{id}       Detalle + plan de cuotas
```

### Dashboard / Ventas
```
GET  /api/dashboard/overview  KPIs generales
GET  /api/ventas/dashboard    Ventas del mes: meta, referencias, detalle
```

### CFO
```
GET  /api/cfo/semaforo        Semáforo: caja/cartera/ventas/roll_rate/impuestos
GET  /api/cfo/pyg             PyG mensual
GET  /api/cfo/plan-accion     Plan de deudas + proyección
GET  /api/cfo/alertas         Alertas activas
POST /api/cfo/generar         Generar informe CFO (async)
POST /api/cfo/chat/message    Chat CFO Estratégico
```

### Agente Contador
```
POST /api/chat/message        Mensaje al agente (crea factura, cobra, audita)
GET  /api/chat/sessions       Historial de sesiones
```

### Impuestos
```
GET  /api/impuestos/iva-status    Estado IVA cuatrimestral desde Alegra
GET  /api/impuestos/config        Configuración períodos fiscales
POST /api/impuestos/config        Actualizar configuración
```

### Alegra / Webhooks
```
GET  /api/alegra/invoices     Facturas de venta
GET  /api/alegra/bills        Facturas de compra
GET  /api/webhooks/status     Estado webhooks (activos/inactivos)
POST /api/webhooks/setup      Intentar registro automático webhooks
POST /webhooks/alegra         Receptor de webhooks Alegra (ruta pública)
```

### Conciliación Bancaria
```
POST /api/conciliacion/cargar-extracto        Cargar extracto bancario
GET  /api/conciliacion/pendientes             Listar movimientos pendientes
POST /api/conciliacion/resolver/{id}          Resolver movimiento ambiguo
GET  /api/conciliacion/estado/{fecha}         Estado de conciliación
GET  /api/conciliacion/journals-banco         Audit: journals por banco/mes
POST /api/conciliacion/backfill-desde-alegra  Reconstruir audit trail desde Alegra
```

### Sistema
```
GET  /api/health/smoke        Smoke test completo
GET  /api/scheduler/jobs      Estado jobs del scheduler
GET  /api/audit/log           Log de acciones
```

## Builds completados

| Build | Fecha | Descripción |
|-------|-------|-------------|
| BUILD 10 | Ene 2026 | Inventario TVS base + Loanbook créditos semanales |
| BUILD 11 | Ene 2026 | Agente Contador v1 + integración Alegra facturas |
| BUILD 12 | Feb 2026 | CFO Estratégico + plan de deudas + semáforo financiero |
| BUILD 13 | Feb 2026 | Módulo Impuestos + calendario fiscal Colombia |
| BUILD 14 | Feb 2026 | RADAR cobranza + gestiones + PTPs + CRM clientes |
| BUILD 15 | Feb 2026 | WhatsApp Mercately: 5 templates + 4 cron jobs |
| BUILD 16 | Mar 2026 | Gastos masivos CSV + Estado de Resultados + presupuesto |
| BUILD 17 | Mar 2026 | Hotfix: VINs reales, motor en loanbooks, safe_str, polling |
| BUILD 18 | Mar 2026 | Dashboard ventas, filtros globales, gestión entregas, calificación 8.63/10 |

## Flujo automático Alegra → Inventario

Cada 5 minutos el scheduler hace polling de nuevas facturas en Alegra.
Al detectar una factura de venta de moto:
1. Extrae VIN (regex `9FL...`) y motor (`BF3...` / `RF5...`) del campo `anotation`
2. Actualiza `inventario_motos.estado` → `Vendida`
3. Crea registro `loanbook` con `estado: pendiente_entrega`
4. Emite evento en `roddos_events`
5. Invalida caché CFO

## Licencia

Uso interno — RODDOS S.A.S. — Bogotá D.C., Colombia.
