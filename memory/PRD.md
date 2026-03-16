# RODDOS Contable IA — Product Requirements Document
**Versión**: 10.0.0 | **Actualizado**: Marzo 2026

---

## PROBLEMA ORIGINAL
ERP contable asistido por IA para RODDOS Colombia SAS — concesionario Auteco en Bogotá.
Venta de motos a crédito (pagos semanales los miércoles). Integración con Alegra ERP.

## ARQUITECTURA ACTUAL
Ver `/app/memory/ARCHITECTURE.md` para el documento técnico completo.

## STACK
- **Backend**: FastAPI + Motor async MongoDB + APScheduler (America/Bogota)
- **Frontend**: React 19 + TypeScript (migración completa) + Tailwind + Shadcn/UI
- **IA**: Claude Sonnet 4.5 via `emergentintegrations`
- **ERP**: Alegra API v1
- **Auth**: JWT + TOTP 2FA

## REGLAS DE NEGOCIO CRÍTICAS
- Cobro SIEMPRE miércoles. Primer cobro = primer miércoles >= (entrega + 7 días)
- Planes: P39S (39 sem) / P52S (52 sem) / P78S (78 sem)
- Mora: 15% EA. Día 1 mora = jueves
- Máximo sin pago: 21 días. DPD=22 activa recuperación
- Módulo cobranza = RADAR (ruta /radar). NUNCA llamar 'cartera' o 'cola de cobranza'
- Alegra: SIEMPRE /categories. NUNCA /accounts (devuelve 403)
- **IVA: CUATRIMESTRAL** (Ene-Abr | May-Ago | Sep-Dic). NUNCA bimestral.
- **Autoretenedores**: proveedores en `proveedores_config` con es_autoretenedor=true → NO aplicar ReteFuente. Actualmente: AUTECO KAWASAKI S.A.S. (NIT 860024781) + **AUTOTECNICA COLOMBIANA S.A.S. / Auteco (NIT 890.900.317-0)** — confirmado AUTORRETENEDOR

### INVENTARIO TVS — REALIDAD ACTUAL (Marzo 2026)
- **Compras a Auteco**: 2 facturas — E670155732 (23 motos, vence 26/05/2026) + E670156766 (10 motos, vence 03/06/2026)
- **Total en inventario**: 34 motos (33 de facturas nuevas + 1 de batch anterior para LB-2026-0016)
- **Estado**: 24 Disponibles + 10 Entregadas (todos los loanbooks con VIN asignado)
- **VIN obligatorio en venta**: El agente SIEMPRE pide VIN antes de crear factura
- **Bills registradas en Alegra**: E670155732 → ID=4 | E670156766 → ID=5
- **Deudas productivas CFO**: E670155732=$132.668.200 + E670156766=$67.741.277
- **Personas Naturales**: SIEMPRE ReteFuente. NUNCA pueden ser autoretenedoras.

---

## LO QUE EXISTE Y FUNCIONA ✅

### Core IA
- Agente IA conversacional (texto + documentos con Claude Sonnet)
- Flujo venta moto → Loanbook automático
- Entrega física → generación fechas cuotas (regla miércoles)
- Causaciones con tabla débito/crédito (ExecutionCard)
- TerceroCard: detecta proveedores nuevos, crea en Alegra, reanuda acción original
- Selector de tipo de documento (chips al adjuntar archivo)

### Módulos Operativos
- Loanbook: CRUD, registro de pagos y entrega, KPIs
- Cartera/RADAR: cola remota URGENTE/HOY/PREVENTIVO, vistas semanal/mensual
- **BUILD 11 — Agente CFO Estratégico (✅ Mar 2026):**
  - PASO 0: Limpieza 11 registros TEST de loanbook + 10 inventario + cartera + events
  - `cfo_estrategico.py` router con 9 endpoints nuevos: indicadores, plan-ingresos, plan-deudas (avalancha), deudas/cargar (Excel), deudas/confirmar, cuotas-iniciales, config, reporte-lunes, reclasificar
  - **GET /cfo/deudas/plantilla**: Genera Excel descargable con 2 hojas (Deudas + Instrucciones), encabezado #0F2A5C, fila de ejemplo, dropdown Tipo, instrucciones completas
  - **POST /cfo/deudas/cargar mejorado**: Skip fila ejemplo, parseo inteligente de montos ($3.500.000 → 3500000), mapeo fuzzy de columnas, mensajes de error accionables con sugerencia de plantilla
  - Botón "Descargar plantilla Excel" + "Ver campos requeridos" en UI CFO
  - Modal de preview con tabla de 8 campos + botón de descarga integrado
  - **GET /cfo/financiero/calcular-desde-alegra**: Calcula gastos fijos desde facturas Alegra, filtra compras de inventario (>$15M), agrupa por mes; retorna ok=False con mensaje claro si no hay gastos operativos
  - Botón "Calcular desde Alegra" en UI con panel de resultados y botón "Actualizar configuración"
  - **POST /cfo/presupuesto/generar**: Genera presupuesto mensual (ej: Abril 2026) con 5 miércoles, recaudo proyectado, gastos, pago deuda, resultado neto, motos necesarias para equilibrio
  - **GET /cfo/presupuesto**: Retorna presupuestos guardados en cfo_presupuesto_mensual
  - Sección "Presupuesto mensual" en UI CFO con KPIs + tabla semanal + alerta de motos necesarias
  - **CRON job #13**: `revisar_gastos_mensuales` — días 1-7 de cada mes (hábiles), alerta si gastos Alegra difieren >10% del valor configurado
  - Reglas CFO 1-5 inyectadas en system prompt del agente IA + contexto en tiempo real
  - Reporte del lunes automático (inyectado los lunes en el contexto del agente)
  - Sección "Plan Estratégico CFO" en frontend: indicadores, plan ingresos 8 semanas, cuotas iniciales $5.3M, carga Excel deudas, plan avalancha, alertas
  - openpyxl instalado (Excel parsing)
  - cfo_financiero_config collection + cfo_deudas collection en MongoDB
- **SPRINT VISUAL (✅ Mar 2026):**
  - MEJORA A: Badge `TareaActivaBadge` en chat — polling 3s, estados cyan/amarillo/verde, botones Pausar/Continuar, expansión de pasos
  - MEJORA B: Barra de filtros de estado en inventario motos — 6 filtros (TODAS/Disponible/Vendida/Entregada/Pendiente datos/Anulada), conteos en tiempo real, colores exactos del usuario, default=Disponible, TODAS excluye Anulada
  - Backend PATCH `/api/chat/tarea/avance` extendido con `accion=pausar|continuar` (retrocompatible)
- Repuestos: catálogo, stock, facturación
- Control IVA cuatrimestral

### Configuración
- **Catálogo de Motos** (BUILD 1 ✅): Sport 100, Raider 125 precargados. CRUD completo con edición inline y toggle activo/inactivo
- **Scheduler DPD + Scores** (BUILD 3 ✅): 4 CRON jobs (DPD@06:00, Scores@06:30, RADAR@07:00, Resumen@Vie17:00 Bogotá)
- **TypeScript Migration** (✅): App.tsx, Login.tsx, AgentChatPage.tsx, Settings.tsx migrados
- **Plan de Cuentas RODDOS** (✅): 155 cuentas reales de Alegra en colección `roddos_cuentas`
- **Smart Retentions PN/PJ** (✅): Detección automática tipo proveedor + retenciones
- **BUILD 5 — WhatsApp Mercately** (✅): Canal WhatsApp, webhook público, sesiones TTL
- **BUILD 6 — CRM + RADAR** (✅): Refactoring Cartera→RADAR, perfil 360° clientes, gestiones
- **BUILD 7 — Scheduler WhatsApp + Alertas CEO** (✅): 9 CRON jobs, alertas DPD 8/15/22
- **BUILD 8 — Frontend completo + Dashboard KPIs** (✅): Dashboard KPIs, mobile-first
- **BUILD 9 — Capa de Aprendizaje ML** (✅): learning_engine.py, 4 tipos patrones, 3 CRONs ML
- **GAPs v1.0** (✅ Marzo 2026): Ver sección GAPS completados abajo

### GAPS v1.0 Completados (Marzo 2026)
- **GAP 1 — Normalización teléfonos**: `normalizar_telefono()` en `crm_service.py`. Aplicado en 5 puntos: upsert_cliente, loanbook create, mercately _detect_sender, mercately _normalize_phone, loanbook_scheduler (todos los CRONs). Migración ejecutada: 1 loanbook + 2 crm_clientes normalizados. Formato: +57XXXXXXXXXX
- **GAP 2 — Inventario + Alegra Sync**: `sync_inventario_desde_compra()` en `post_action_sync.py`. CASO 4 la invoca al registrar factura de compra de motos. Crea ítems en Alegra + documenta en `inventario_motos`. GET /api/inventario/stats funcional. Migración idempotente de backfill loanbook→inventario disponible.
- **Factura Compra → Inventario (Opción A, Marzo 2026)**: System prompt hace obligatorio `motos_a_agregar` en compras de motos. Claude pregunta por chasis/color antes de ejecutar. Sin datos → estado `Pendiente datos`. `es_compra_motos=True` sin datos → evento `inventario.sync.pendiente` + warning. Stats incluye `pendiente_datos`.
- **Acción anular_factura_compra + Extracción de datos motos (Marzo 2026)**: Nueva acción `anular_factura_compra` en `execute_chat_action` → DELETE /bills/{id} Alegra → marca motos como `Anulada` → evento `factura.compra.anulada`. Guard: bloquea si hay motos Vendida/Entregada vinculadas. System prompt: extracción de campos separados (referencia, color, chasis, motor) desde texto en bloque; regla: 1 objeto por unidad cuando hay chasis distinto; tarjeta de confirmación antes de ejecutar. Stats endpoint incluye campo `anuladas`.
- **Memoria y Contexto del Agente IA (Marzo 2026)**: MEJORA 1: Historial de chat persistente entre requests (carga desde db.chat_messages, resumen automático cuando supera 6000 tokens, mantiene últimos 6 intercambios completos). MEJORA 2: Tarea activa en agent_memory (endpoints POST/GET/PATCH /api/chat/tarea, comandos "pausa la tarea"/"continúa la tarea", inyección automática en system prompt). MEJORA 3: Actividad del día desde roddos_events inyectada en contexto. MEJORA 4: Comandos especiales "¿en qué íbamos?", "resumen" → respuesta directa sin llamar LLM. Bug fix: `context_data.get('cuentas_contables', [])` evita KeyError 503.
- **GAP 3 — CFO Asíncrono**: POST /api/cfo/generar → async BackgroundTasks → retorna job_id. GET /api/cfo/status/{job_id} para polling. CFO.tsx: polling cada 2s, máx 90s. Semáforo y P&G ahora cargan independientemente del spinner principal (no bloquean la UI).

### Seguridad / Datos
- Mutex anti-doble venta en loanbook (BUILD 1 ✅)
- Resolución DIAN verificada y funcional (ID 17, vigente hasta 2027-03-06)

---

## MIGRACIÓN TYPESCRIPT (✅ COMPLETADO)
- ✅ App.tsx, Login.tsx, AgentChatPage.tsx, Settings.tsx
- ✅ Loanbook.tsx, AuthContext.tsx, AlegraContext.tsx
- ✅ Declaraciones .d.ts para componentes shadcn/ui

---

## BUILD 12 — COMPLETADO (2026-03-15)

### Correcciones críticas implementadas
- **Déficit semanal real**: $1,659,400 recaudo - $7,500,000 gastos = **-$5,840,600/semana** (corregido de -$20,840,600)
- **REGLA FUNDAMENTAL DE LIQUIDEZ** en system prompt: RODDOS vende 100% a cuotas, liquidez ≠ facturación
- **Separación base caja vs base devengada** explicada al agente CFO

### Verificación P&L Marzo 2026 — COMPLETADA (2026-03-15)
- Listado completo de 11 facturas Alegra con fecha/cliente/monto verificados ✅ todas en 01/03-31/03/2026
- Alerta automática de posible duplicado FV-6 vs FV-448 (José Altamiranda, mismo monto/fecha)
- **SECCIÓN A (Base Devengada)**: $78,345,567 facturado (contable)
- **SECCIÓN B (Base Caja)**: $8,024,500 recibido realmente ($6.7M cuotas iniciales + $1.3M cuotas semanales)
- UI con tablas collapsibles por sección, alertas en rojo, cuotas pendientes visibles
- `GET /api/cfo/estado-resultados?periodo=YYYY-MM` — P&L real desde Alegra
- `GET /api/cfo/estado-resultados/pdf` y `/excel` — Exportación
- Widget Sostenibilidad (10/45 créditos activos, countdown Jun 20 2026)
- UI Carga de costos de inventario (modal 2 pasos en InventarioAuteco.js)
- PlExportCard en AgentChatPage.tsx

---

## BUILD 14 — MERCATELY WHATSAPP OPERATIVO (✅ Feb 2026)

### Componentes implementados
- **Webhook completo** `/api/mercately/webhook`: detección de tipo de remitente (CLIENTE/INTERNO/DESCONOCIDO), procesamiento de media (comprobante/facturas), flujo SI/NO de confirmación, sesiones TTL 5 min
- **Detección de intención** mensajes libres: SALDO / PAGO / DIFICULTAD / NO_RECONOCIDA → respuesta contextual automática
- **5 Templates automáticos**:
  - T1: Recordatorio preventivo D-2 (lunes 8am COT)
  - T2: Vencimiento hoy — incluye datos bancarios (miércoles 8am COT)
  - T3: Mora D+1 (jueves 9am COT)
  - T4: Confirmación de pago — disparado desde post_action_sync.py al registrar pago
  - T5: Mora severa +30 días (sábado 9am COT)
- **Scheduler 4 cron jobs**: America/Bogota, respetan toggle global_activo y toggles por template
- **Logging** a colección `cartera_gestiones` de todos los mensajes enviados/recibidos
- **Endpoints**: GET /api/mercately/gestiones, GET /api/mercately/gestiones/cliente/{cedula}
- **Settings UI** (Mercately tab): toggle global, horario operación, 5 toggles de templates, datos bancarios, tabla últimos 50 mensajes
- **CRM Profile**: sección "WhatsApp — Historial" en perfil del cliente (de `cartera_gestiones`)

### TAREA 0 — ReteICA Corregido (✅ Feb 2026)
- Cálculo corregido: 0.414% por operación gravada (no proyección anual)
- Campo `tarifa_pct` en respuesta (no `tarifa_anual_pct`)
- Badge UI actualizado: "0.414% por operación gravada"

### TAREA 1 — Hard Delete Proveedores (✅ Feb 2026)
- DELETE /api/proveedores/config/{nombre}: eliminación real del documento MongoDB
- Modal de confirmación personalizado en UI (data-testid: cancel-delete-btn, confirm-delete-btn)
- Filtro de ELIMINADO eliminado del frontend (ya no necesario)

### P0 — GAPs v1.0 ✅ COMPLETADO (Marzo 2026)

### BUILD 15 — Webhooks Alegra + Console Error Fixes ✅ COMPLETADO (Feb 2026)
- JWT 168h (7 días), AuthContext 401 anti-storm guard, AgentChatPage retry backoff, offline guard en polls
- MongoDB 5-min cache para cfo/semaforo + cfo/pyg (36s → 0.2s, eliminó los 504s)
- POST /api/webhooks/alegra (receptor seguro <1s), 12 handlers de eventos, cron sync pagos 5min
- WebhooksTab en Settings: grid 12 eventos, stats sync, re-register y manual sync buttons

### BUILD 17 — Inventario TVS Completo + Capacidades Agente ✅ COMPLETADO (Mar 2026)
- Migración DB: eliminados 2 fantasmas (Honda, Yamaha) + 10 placeholders PENDIENTE-LB
- 33 motos TVS reales cargadas con upsert por chasis (34 total incl. 1 de batch anterior para LB-2026-0016)
- Cruce Alegra: 10/10 loanbooks ahora tienen moto_chasis + motor (leídos desde anotation de facturas de venta)
- Bills E670155732 ($132.668.200, vence 26/05/2026) y E670156766 ($67.741.277, vence 03/06/2026) registradas en Alegra (ID=4, ID=5) y en cfo_deudas como deudas productivas
- Nuevos endpoints: `GET /inventario/auditoria`, `DELETE /inventario/motos/{id}`, `POST /inventario/asignar-chasis`
- Webhook actualizado: detecta VIN con regex (9FL...) en anotation, actualiza inventario + loanbook en tiempo real
- AI Agent: auditoría automática sin LLM (keyword "audita el inventario"), consulta moto de cliente (keyword "qué moto tiene"), VIN obligatorio en flujo de venta con lista de disponibles
- Frontend: polling 30s en módulo Motos + scheduler reconciliación inventario lunes 7am COT
- Autoco NIT 890.900.317-0 confirmado AUTORRETENEDOR (sin ReteFuente)

## BUILD 18 — COMPLETADO (Marzo 2026)

### Módulos nuevos y mejoras
- **Dashboard de Ventas**: Sección `/dashboard` con 4 cards: resumen mensual (meta, %, progreso), referencias vendidas, comparativo mensual, detalle expandible por cliente
- **Gestión de Entregas**: Panel `PendientesBanner` + `EntregaModal` en `/loanbook`. Flujo completo: selección de fecha → actualiza loanbook (activo) + moto (Entregada) + genera cuotas → invalida caché CFO
- **Filtros Globales `FiltroFecha`**: Componente reutilizable en 6 módulos: Dashboard, Loanbook, Motos, RADAR, Impuestos, CFO Estratégico
- **Sidebar actualizado**: "Cartera" → "RADAR" apuntando a `/radar`
- **Botón Webhooks Manual**: Settings > Webhooks > "Abrir Alegra → Webhooks" con guía paso a paso
- **CFO Cache Invalidation inmediata**: `invalidar_cache_cfo()` integrado en pagos, gastos y entregas
- **Polling facturas automático**: Cada 5 min detecta facturas Alegra y actualiza inventario + loanbooks
- **Corrección datos**: LB-2026-0021 (Sindy) y LB-2026-0022 (Manuel) corregidos a `estado: pendiente_entrega`
- **Formato factura reforzado**: System prompt con `description` en items + `anotation` para detección fiable de VIN/Motor

### Tests verificados (18/18 PASS)
- Smoke test: status=ok, loanbooks=9, inventario=33, alegra=true
- RADAR nav sidebar, FiltroFecha en 6 módulos, 2 pendientes entrega, VentasDashboard, modal entrega Sindy


**Diagnóstico confirmado:**
- Inventario: ya estaba en 33 motos (22 Disponible + 11 Vendida/Entregada). No se necesitó corrección adicional.
- LB-2026-0016: corregido typo en moto_chasis (`9FLT81003VDB62143` → `9FLT81003VDB62413`)
- Webhook Alegra: API de Alegra rechaza URLs con `https://` (bug confirmado). Sin posibilidad de registro vía API.

**Solución implementada — Polling Permanente:**
- `sincronizar_facturas_recientes()` en `alegra_webhooks.py`: fetch de facturas Alegra (`api.alegra.com/api/v1/invoices`), deduplicación por `alegra_invoice_id` + `ultima_factura_id_sync`, ignora motos ya en Vendida/Entregada.
- Nuevo job `sync_facturas_alegra` cada 5 min en `scheduler.py` (APScheduler).
- Nuevo endpoint `POST /api/webhooks/sync-facturas-ahora` con parámetro `fecha_desde` para sync retroactivo.
- `webhook_status` endpoint actualizado con estadísticas del polling.
- UI Settings.tsx: panel "Polling de Facturas Alegra", banner de alerta webhook bug, botón manual trigger.

**Prueba end-to-end confirmada:**
- Factura FE455 (ID=24) creada en Alegra con VIN `9FL25AF32VDB95022`. El polling la detectó y procesó en ~12 segundos via trigger manual. Factura eliminada y moto restaurada al estado de prueba.


- **GET /api/gastos/plantilla**: Genera plantilla Excel oficial con 12 columnas, dropdowns, hoja de instrucciones, fila ejemplo Auteco Kawasaki
- **POST /api/gastos/cargar**: Parsea Excel uploaded, detecta headers (exact + substring matching), calcula retenciones automáticas (ReteFuente + IVA), detecta autoretenedores desde DB y columna, retorna preview + resumen
- **POST /api/gastos/procesar**: Inicia job asíncrono (background task), retorna job_id inmediatamente. Lógica mixta: Contado → journal-entry en Alegra, Credito_N → bill con vencimiento calculado
- **GET /api/gastos/jobs/{job_id}**: Polling de estado (iniciando|procesando|completado)
- **GET /api/gastos/reporte-errores/{job_id}**: Descarga Excel con filas fallidas
- **AI keyword detection**: "carga masiva", "cargar gastos", "excel gastos" → retorna gastos_masivos_card
- **Frontend GastosMasivosCard**: 4 estados (initial/preview/processing/done), KPIs en preview (base, IVA, ReteFuente, neto), tabla expandible, progreso en tiempo real vía polling, chip acceso rápido
- Mapeo automático tipo_gasto → cuenta Alegra: arriendo=3.5%, honorarios_pn=10%, honorarios_pj=11%, servicios=4%, compras=2.5%
- Auteco Kawasaki NIT 860024781 siempre sin ReteFuente (autoretenedor)

- GAP 1: Normalización teléfonos ✅
- GAP 2: Inventario + Alegra Sync ✅
- GAP 3: CFO Asíncrono ✅

### Backlog Técnico
- Detección automática UVT para retenciones (actualmente hardcoded)
- Integración DIAN para semáforo impuestos (actualmente hardcoded VERDE)
- Nómina y Prestaciones NIIF Colombia

### P1 — BUILD 10: Estado de Resultados automático desde Alegra
- Generación automática del P&L mensual completo

### P2 — Panel de Aprendizaje ML
- Dashboard visual de patrones ML (contactabilidad, templates, señales deterioro)
- Widget dashboard: clientes con señal de deterioro

### P3 — Detección automática UVT
- Reemplazar hardcoded UVT por detección dinámica para retenciones

---

## COLECCIONES MONGODB (nombres exactos — no crear variantes)
loanbook · cartera_pagos · crm_clientes · inventario_motos · catalogo_motos
roddos_events · agent_memory · cfo_informes · cfo_alertas · cfo_jobs
mercately_sessions · mercately_config · presupuesto · alegra_credentials
users · audit_logs · gestiones_cartera · learning_outcomes · learning_patterns
**proveedores_config** · iva_config · cfo_instrucciones · cfo_compromisos · cfo_chat_historia

## ENDPOINTS (no inventar variantes)
Ver `/app/memory/ARCHITECTURE.md` sección 3.6 para lista completa.
NUNCA crear /api/cartera/* — la ruta correcta es /api/radar/*

## NUEVOS ENDPOINTS (GAPs Marzo 2026 + BUILD 16 + BUILD 17)
- GET /api/inventario/stats — estadísticas inventario motos (+ ultima_actualizacion)
- GET /api/inventario/auditoria — auditoría completa con inconsistencias
- DELETE /api/inventario/motos/{id} — elimina con verificación loanbook + log evento
- POST /api/inventario/asignar-chasis — asigna VIN+motor a loanbook
- POST /api/cfo/generar — ahora retorna {job_id, estado} (async)
- GET /api/cfo/status/{job_id} — polling estado job CFO
- GET /api/gastos/plantilla — plantilla Excel 12 columnas con instrucciones y dropdowns
- POST /api/gastos/cargar — parse+validación+retenciones desde Excel (multipart/form-data)
- POST /api/gastos/procesar — procesar rows en Alegra (journal-entries o bills), retorna job_id
- GET /api/gastos/jobs/{job_id} — polling estado job carga masiva
- GET /api/gastos/reporte-errores/{job_id} — Excel con filas fallidas
