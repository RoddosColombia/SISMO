# RODDOS Contable IA — Product Requirements Document
**Versión**: 4.0.0 | **Actualizado**: Febrero 2026

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
- **Smart Retentions PN/PJ (✅ Febrero 2026)**: Detección automática de tipo de proveedor (`_detectar_tipo_proveedor`) y número de identificación (`_detectar_identificacion`). Flujo de 3 casos: (1) Tipo+ID → acción directa, (2) Tipo sin ID → pregunta SOLO cédula/NIT, (3) Tipo desconocido → pregunta tipo. Validado con TEST 4 oficial 49/49 + 3/3 retentions PASS.
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

### P0 — BUILD 5: WhatsApp Mercately
- Integración WhatsApp (infraestructura en settings lista, Mercately config en DB)
- Scheduler Viernes 17:00 → envío automático resumen CEO
- Motor de alertas: mora día 1, DPD 8, DPD 15, DPD 22 → WhatsApp automático al cliente

### P1 — BUILD 6: CRM + RADAR UI
- CRM clientes: ClientDetail, notas APPEND-ONLY, historial gestiones
- RADAR UI completo: BucketBadge, RadarCard priorizada, scores A+..E visuales

### P2 — BUILD 7: Scheduler WhatsApp + alertas automáticas
- Motor de alertas completo (disparadores por DPD, estado, vencimiento DIAN)

### P3 — BUILD 8: Frontend completo + Dashboard KPIs
- Dashboard KPIs tiempo real con panel RADAR en vivo (buckets visuales)
- Estado de Resultados automático Alegra
- Renombrar módulo cartera → RADAR (frontend completo)

### Backlog Técnico
- Migrar Cartera.js, contextos AuthContext/AlegraContext a TypeScript
- Integración DIAN para semáforo impuestos (actualmente hardcoded VERDE)
- Nómina y Prestaciones NIIF Colombia

---

## COLECCIONES MONGODB (nombres exactos — no crear variantes)
loanbook · cartera_pagos · crm_clientes · inventario_motos · catalogo_motos
roddos_events · agent_memory · cfo_informes · cfo_alertas
mercately_sessions · mercately_config · presupuesto · alegra_credentials
users · audit_logs

## ENDPOINTS (no inventar variantes)
Ver `/app/memory/ARCHITECTURE.md` sección 3.6 para lista completa.
NUNCA crear /api/cartera/* — la ruta correcta es /api/radar/*
