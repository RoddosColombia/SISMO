# RODDOS Contable IA — Product Requirements Document
**Versión**: 3.0.0 | **Actualizado**: Febrero 2026

---

## PROBLEMA ORIGINAL
ERP contable asistido por IA para RODDOS Colombia SAS — concesionario Auteco en Bogotá.
Venta de motos a crédito (pagos semanales los miércoles). Integración con Alegra ERP.

## ARQUITECTURA ACTUAL
Ver `/app/memory/ARCHITECTURE.md` para el documento técnico completo.

## STACK
- **Backend**: FastAPI + Motor async MongoDB + APScheduler (America/Bogota)
- **Frontend**: React 19 + TypeScript (migración en curso) + Tailwind + Shadcn/UI
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
- Credenciales Alegra, modo demo, cuentas predeterminadas
- 2FA con Google Authenticator (TOTP)
- Bot Telegram (infraestructura completa)

### Seguridad / Datos
- Mutex anti-doble venta en loanbook (BUILD 1 ✅)
- Resolución DIAN verificada y funcional (ID 17, vigente hasta 2027-03-06)

---

## MIGRACIÓN TYPESCRIPT (en curso)
Política: Migrar a .tsx/.ts al tocar cada archivo. No migrar en bloque.
- ✅ Settings.js → Settings.tsx (BUILD 1)
- Pendiente: App.js, Login.js, AgentChatPage.js, Loanbook.js, Cartera.js, etc.

---

## BACKLOG (por prioridad)

### P0 — Crítico
- Pruebas E2E Telegram completas con token real
- Renombrar módulo cartera → RADAR (radar.py, Radar.tsx, ruta /radar)

### P1 — Alta prioridad
- BUILD 2: Módulo RADAR completo (BucketBadge, RadarCard, cola priorizada, scores A+..E)
- BUILD 3: Loanbook mejorado (LoanDetail.tsx, CuotaTimeline, MoraCalculator)
- BUILD 4: CRM de clientes (ClientDetail, notas APPEND-ONLY, historial gestiones)
- Directorio de Terceros (CRUD contactos Alegra desde RODDOS)
- Integración WhatsApp Mercately (infraestructura en settings lista)
- Nómina y Prestaciones con cálculo real NIIF Colombia

### P2 — Media prioridad
- Dashboard KPIs tiempo real (APScheduler + shared_state.py)
- CFO Agent (semáforo financiero, informe mensual, plan de acción)
- Estado de Resultados automático desde Alegra
- Motor de alertas activo (detección mora automática)

### P3 — Baja prioridad / Futuro
- Multi-empresa / roles granulares
- Integración DIAN para declaración IVA
- App móvil PWA para vendedores

---

## COLECCIONES MONGODB (nombres exactos — no crear variantes)
loanbook · cartera_pagos · crm_clientes · inventario_motos · catalogo_motos
roddos_events · agent_memory · cfo_informes · cfo_alertas
mercately_sessions · mercately_config · presupuesto · alegra_credentials
users · audit_logs

## ENDPOINTS (no inventar variantes)
Ver `/app/memory/ARCHITECTURE.md` sección 3.6 para lista completa.
NUNCA crear /api/cartera/* — la ruta correcta es /api/radar/*
