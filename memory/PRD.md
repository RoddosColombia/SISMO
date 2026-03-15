# RODDOS Contable IA — Product Requirements Document
**Versión**: 7.0.0 | **Actualizado**: Marzo 2026

---

## PROBLEMA ORIGINAL
ERP contable asistido por IA para RODDOS Colombia SAS — concesionario Auteco en Bogotá.
Venta de motos a crédito (pagos semanales los miércoles). Integración con Alegra ERP.

## ARQUITECTURA ACTUAL
Ver `/app/memory/ARCHITECTURE.md` para el documento técnico completo.

## STACK
- **Backend**: FastAPI + Motor async MongoDB + APScheduler (America/Bogota)
- **Frontend**: React 19 + TypeScript (migración completa App/Login/AgentChat/Settings) + Tailwind + Shadcn/UI
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
- **Scheduler DPD + Scores** (BUILD 3 ✅ — TEST BUILD3 10/10+Frontend PASS): migration_v24.py idempotente, 4 CRON jobs (DPD@06:00, Scores@06:30, RADAR@07:00, Resumen@Vie17:00 Bogotá), 4 endpoints /api/radar/*, endpoints gestion/ptp/snapshot, Loanbook.tsx con columnas DPD y Score
- **TypeScript Migration** (✅ COMPLETADO — Febrero 2026): `// @ts-nocheck` eliminado de App.tsx, Login.tsx, AgentChatPage.tsx, Settings.tsx. Interfaces propias: Message, PendingAction, DocumentProposalData, AttachedFile. Declaraciones `.d.ts` para shadcn/ui. Fork-ts-checker: "No issues found."
- **TEST 3** (✅ 29/29 PASS): DPD 3A (9/9), Mora 15%EA 3B (3/3), Scores A+→E 3C (6/6), Protocolo+Performance 3D (4/4), Migración 3E (5/5). Fix: `calcular_scores()` ahora incluye estado "recuperacion".
- **Plan de Cuentas RODDOS — Conocimiento Base (✅ Febrero 2026)**: Colección `roddos_cuentas` en MongoDB con 155 cuentas reales de Alegra. `gather_accounts_context` usa `roddos_cuentas` primero (<5ms). System prompt incluye PLAN DE CUENTAS RODDOS con IDs reales.
- **Smart Retentions PN/PJ (✅ Marzo 2026)**: Detección automática de tipo de proveedor (`_detectar_tipo_proveedor`) y número de identificación (`_detectar_identificacion`). Flujo de 3 casos: (1) Tipo+ID → acción directa, (2) Tipo sin ID → pregunta SOLO cédula/NIT, (3) Tipo desconocido → pregunta tipo. Validado con TEST 4 oficial 49/49 + 3/3 retentions PASS.
- **BUILD 5 — WhatsApp Mercately (✅ Marzo 2026)**: Canal WhatsApp via Mercately. `routers/mercately.py` con POST /api/mercately/webhook público. Flujos: CLIENTE (comprobante → propuesta → confirmación SI → registro Alegra → recibo digital), INTERNO (factura → ExecutionCard → confirmación SI → ejecución Alegra), DESCONOCIDO (bienvenida). Settings tab: api_key, phone_number, whitelist, ceo_number, destinatarios_resumen + botón "Probar Conexión". Sesiones TTL 5min en `mercately_sessions`. `resumen_semanal()` envía WhatsApp a destinatarios_resumen cada viernes 17:00. Backwards-compat: ceo_number auto-prepend. 14/14 TEST 5 PASS.
- **BUILD 6 — CRM + RADAR (✅ Marzo 2026)**: Refactoring completo Cartera→RADAR. `routers/radar.py` (migrado): /queue, /semana, /portfolio-health, /roll-rate, /cola-remota (deprecated alias). `services/crm_service.py`: upsert_cliente, registrar_gestion (dual-write a loanbook+crm_clientes), registrar_ptp, agregar_nota. `routers/crm.py`: GET/PUT/POST CRUD 360° del cliente. Frontend: `Radar.tsx` (KpiBar, RadarCard, GestionModal), `CRMList.tsx` (búsqueda+filtros), `CRMCliente.tsx` (perfil 360°: crédito, contacto editable, timeline gestiones, notas). Archivos eliminados: cartera.py, Cartera.js. Declaración types `dialog.d.ts` para React 19. 22/22 TEST 6 PASS.
- **BUILD 7 — Scheduler WhatsApp + Alertas CEO (✅ Marzo 2026)**: 9 CRON jobs en `loanbook_scheduler.py`. Nuevos: `alertar_buckets_criticos()` (06:05, DPD 8/15/22 → WA diferenciado + CEO), `verificar_alertas_cfo()` (06:10, despacha cfo_alertas[estado=nueva] por WA), `recordatorio_preventivo()` (Mar 09:00), `recordatorio_vencimiento()` (Mié 09:00), `notificar_mora_nueva()` (Jue 09:00, DPD=1). `resumen_semanal()` reemplazado por `resumen_semanal_ceo()` enriquecido (semáforo 🟢/🟡/🔴, roll rate, top mora). PTP follow-up integrado en `calcular_scores()`. `cfo_agent.py` ahora inserta alertas con `estado='nueva'` y deduplicación por periodo. 21/21 TEST 7 PASS.
- Credenciales Alegra, modo demo, cuentas predeterminadas
- 2FA con Google Authenticator (TOTP)
- Bot Telegram (infraestructura completa)

### Seguridad / Datos
- Mutex anti-doble venta en loanbook (BUILD 1 ✅)
- Resolución DIAN verificada y funcional (ID 17, vigente hasta 2027-03-06)

---

## MIGRACIÓN TYPESCRIPT (✅ COMPLETADO)
Política: Migrar a .tsx/.ts al tocar cada archivo. No migrar en bloque.
- ✅ App.tsx, Login.tsx, AgentChatPage.tsx, Settings.tsx — `// @ts-nocheck` eliminado, tipos propios añadidos
- ✅ Loanbook.tsx — ya tipado en BUILD 3
- ✅ Declaraciones .d.ts para componentes shadcn/ui (button, input, label, tabs, textarea)
- ✅ tsconfig: `exclude: ["src/components/ui/*.jsx"]` para que TypeScript use las .d.ts
- Pendiente: Cartera.js, Loanbook.js, contextos AuthContext/AlegraContext

---

## BACKLOG (por prioridad — orden BUILD fijo)

### P0 — BUILD 5: WhatsApp Mercately ✅ COMPLETADO
- Integración WhatsApp (infraestructura en settings lista, Mercately config en DB)
- Scheduler Viernes 17:00 → envío automático resumen CEO
- Motor de alertas: mora día 1, DPD 8, DPD 15, DPD 22 → WhatsApp automático al cliente

### P1 — BUILD 6: CRM + RADAR UI ✅ COMPLETADO
- CRM clientes: ClientDetail, notas APPEND-ONLY, historial gestiones
- RADAR UI completo: BucketBadge, RadarCard priorizada, scores A+..E visuales

### P1 — BUILD 7: Scheduler WhatsApp + alertas automáticas ✅ COMPLETADO

### P1 — BUILD 8: Frontend completo + Dashboard KPIs ✅ COMPLETADO (Marzo 2026)
- Dashboard KPIs tiempo real: semáforo CFO, KPIs semana, Top 5 RADAR, inventario, alertas. Auto-refresh 30s.
- Componentes shared: BucketBadge, ScoreBadge, RadarCard (con ultima_gestion), GestionModal, WhatsAppButton, DiasProtocolo
- Loanbook: columna Mora($), DPD/Score ordenables, historial gestiones en detalle
- Hooks: useSharedState, useRadarQueue (polling)
- Migración TypeScript: AuthContext.tsx, AlegraContext.tsx. Archivos .js obsoletos eliminados.
- Backend: POST /api/scheduler/trigger/{job_id}, GET /api/settings/wa-logs
- Mobile-first: /radar y /crm/{id} responsive en 375px
- TEST 8: 14/14 PASS (backend 8/8, frontend 6/6)

### Backlog Técnico
- Detección automática UVT para retenciones (actualmente hardcoded)
- Integración DIAN para semáforo impuestos (actualmente hardcoded VERDE)
- Nómina y Prestaciones NIIF Colombia

### P1 — BUILD 9: Capa de Aprendizaje ✅ COMPLETADO (Marzo 2026)
- **learning_engine.py** (nuevo): crear_outcome, resolver_outcomes_pendientes, procesar_patrones_semanales, get_recomendacion_contacto, get_alerta_deterioro, get_template_optimo, get_metricas_predictivas
- **Colecciones nuevas**: `learning_outcomes` (1 doc/gestión) y `learning_patterns` (4 tipos: contactabilidad, template, señal_deterioro, patron_contable)
- **GET /api/crm/{id}/learning**: recomendación de contacto + alerta predictiva
- **3 CRONs BUILD 9**: alertas_predictivas (06:45), resolver_outcomes (07:30), procesar_patrones (Lun 08:00) — total 12 jobs
- **CRMCliente.tsx**: Box azul (recomendación si confianza ≥ 0.6) y box naranja (alerta si DPD=0 y prob>0.60)
- **CFO**: analizar_cartera + generar_semaforo + informe con clientes_en_riesgo, tendencia_mora, efectividad_canal
- **AI Chat**: patron_contable por NIT incluido en prompt si confianza ≥ 0.7
- **Settings**: 12 jobs con badges ML en "Alertas Predictivas ML", "Resolver Outcomes WA", "Procesar Patrones ML"
- **Layout.js**: Badge rojo CFO en sidebar, polling cada 60s
- **Recordatorios WA**: get_template_optimo() antes de enviar (fallback a default sin error)
- TEST 9: 14/14 PASS

---

## COLECCIONES MONGODB (nombres exactos — no crear variantes)
loanbook · cartera_pagos · crm_clientes · inventario_motos · catalogo_motos
roddos_events · agent_memory · cfo_informes · cfo_alertas
mercately_sessions · mercately_config · presupuesto · alegra_credentials
users · audit_logs

## ENDPOINTS (no inventar variantes)
Ver `/app/memory/ARCHITECTURE.md` sección 3.6 para lista completa.
NUNCA crear /api/cartera/* — la ruta correcta es /api/radar/*
