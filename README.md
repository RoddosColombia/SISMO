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

### 2. Actualizar tu número de WhatsApp

Para recibir notificaciones en tu WhatsApp personal:

1. Ve a **Configuración → Mercately** en SISMO
2. En el campo "Mi teléfono", ingresa tu número en formato internacional: `57XXXXXXXXXX`
   - Ejemplo: `573115551234` (Andrés)
   - El número debe incluir código país (57 para Colombia)
3. Guarda los cambios
4. Prueba la conexión — recibirás un mensaje de confirmación

### 3. Casos de uso automáticos

**A. Notificaciones de Movimientos Ambiguos (Clasificación Contable)**

Cuando se carga un extracto bancario y hay movimientos con baja confianza en su clasificación contable:
- El sistema intenta clasificarlos automáticamente
- Si confianza < 70%, se solicita confirmación vía WhatsApp
- Mensaje enviado a tu número configurado con:
  - Monto de la transacción
  - Descripción
  - Cuenta contable sugerida
  - % de confianza en la clasificación

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

El scheduler envía mensajes WhatsApp en estos momentos:
- **Lunes 8am**: Recordatorio D-2 a clientes que pagan miércoles
- **Miércoles 8am**: Recordatorio día de vencimiento
- **Jueves 9am**: Alerta de mora D+1 (cuota no pagada)
- **Sábado 9am**: Alerta de mora severa (+30 días)

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

## Colecciones MongoDB

| Colección | Descripción |
|-----------|-------------|
| `loanbook` | Créditos activos/pendientes con plan de cuotas semanal |
| `inventario_motos` | 33 motos TVS con VINs, motores, estado y precio |
| `cartera_pagos` | Registro histórico de pagos de cuotas |
| `cartera_gestiones` | Gestiones de cobranza y PTPs |
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
