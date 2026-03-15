# RODDOS Contable IA — Product Requirements Document
**Versión**: 8.0.0 | **Actualizado**: Marzo 2026

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
- Inventario motos con carga PDFs Auteco
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

## BACKLOG (por prioridad — orden BUILD fijo)

### P0 — GAPs v1.0 ✅ COMPLETADO (Marzo 2026)
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

## ENDPOINTS (no inventar variantes)
Ver `/app/memory/ARCHITECTURE.md` sección 3.6 para lista completa.
NUNCA crear /api/cartera/* — la ruta correcta es /api/radar/*

## NUEVOS ENDPOINTS (GAPs Marzo 2026)
- GET /api/inventario/stats — estadísticas inventario motos
- POST /api/cfo/generar — ahora retorna {job_id, estado} (async)
- GET /api/cfo/status/{job_id} — polling estado job CFO
