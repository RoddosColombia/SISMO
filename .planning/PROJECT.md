# SISMO — Sistema Inteligente de Soporte y Monitoreo Operativo

## What This Is

Plataforma de orquestacion de agentes IA especializados para automatizar las operaciones completas de RODDOS S.A.S., fintech de movilidad sostenible en Bogota, Colombia. Financia motocicletas con cobro 100% remoto (WhatsApp + transferencias). Equipo pequeno (2-5 personas) gestiona 10 loanbooks activos, cartera de $94M COP, 34 motos TVS con VINs reales.

## Core Value

Contabilidad automatizada sin intervencion humana (cada operacion financiera reflejada correctamente en Alegra) + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos.

## Requirements

### Validated

- [x] Dashboard con KPIs de negocio (ventas, caja, cartera) — existing
- [x] Gestion de loanbooks (planes de pago motos TVS) — existing
- [x] Chat con agente IA (Contador) para operaciones contables — existing
- [x] Integracion basica con Alegra (contactos, facturas, pagos) — existing
- [x] Webhook Mercately para WhatsApp (deteccion de intenciones: saldo, pago, dificultad) — existing
- [x] Webhook Telegram para subida de documentos con analisis IA — existing
- [x] CRM con gestion de clientes — existing
- [x] Inventario de motos con VINs reales — existing
- [x] Bus de eventos append-only en MongoDB (roddos_events) — existing
- [x] Autenticacion JWT con roles — existing
- [x] CFO dashboard operativo y estrategico — existing
- [x] Clasificacion contable con accounting_engine (50+ reglas) — existing
- [x] Registro de pagos de cuotas con sync a Alegra — existing
- [x] Scheduler para tareas en background (APScheduler) — existing

### Validated (BUILD 24 — Cimientos Definitivos)

- [x] Bus de eventos tipado y validado (EventBusService + DLQ + retry) — BUILD 24 Phase 2
- [x] Permisos de escritura de agentes validados en codigo Python — BUILD 24 Phase 1
- [x] MongoDB completo: 30+ colecciones con indices ESR, schema validation, datos sembrados — BUILD 24 Phase 3
- [x] System prompts diferenciados por agente + router confidence 0.7 — BUILD 24 Phase 4
- [x] Portfolio summaries pre-calculados (Computed Pattern) + financial reports — BUILD 24 Phase 4
- [x] GitHub CI/CD expandido: pytest, smoke test, anti-pending check, Dependabot — BUILD 24 Phase 5
- [x] CFO leyendo portfolio_summaries en vez de Alegra directo — BUILD 24 Phase 4

### Active (BUILD 23 — Agente Contador 8.5/10 + Alegra 100%)

- [ ] Auditoria completa de la capa Alegra — mapear que funciona, que esta roto, que falta
- [ ] Unica fuente de verdad para comunicacion con Alegra (consolidar utils/alegra.py + alegra_service.py)
- [ ] request_with_verify() robusto: POST → verificar con GET → HTTP 200 obligatorio
- [ ] ACTION_MAP completo con acciones de lectura (consultar_facturas, consultar_pagos, consultar_journals, consultar_cartera, consultar_plan_cuentas)
- [ ] Chat transaccional: gasto en lenguaje natural → clasificacion → ReteFuente/ReteICA → POST /journals → ID verificado
- [ ] Facturacion venta motos: POST /invoices con VIN + motor obligatorios, formato "[Modelo] [Color] - VIN:[x] / Motor:[x]"
- [ ] Ingresos cuotas: cada pago → POST /payments → journal ingreso en Alegra, anti-duplicados
- [ ] Nomina mensual discriminada por empleado con anti-duplicados por mes
- [ ] Smoke test final: 10 criterios Alegra 100% verificados

### Out of Scope

- App movil nativa — web-first, mobile responsive es suficiente
- Multitenancy — SISMO es exclusivo para RODDOS S.A.S.
- Integracion con bancos directa — se usa reconciliacion via CSV/Excel
- Facturacion electronica DIAN en produccion — DIAN stubbed, se implementara cuando haya certificado

## Previous Milestone: v2.0 BUILD 24 — Cimientos Definitivos ✓

**Goal:** Establecer los cimientos estructurales de SISMO — MongoDB completo, bus de eventos real, permisos de agentes en codigo, system prompts diferenciados, y CI/CD con pytest.
**Score alcanzado:** 9.3/10 | Tag: `v24.0.0` | Hotfix: `v24-hotfix-alegra` (ERROR-017 URL base Alegra)

## Current Milestone: v23.0 BUILD 23 — Agente Contador 8.5/10 + Alegra 100%

**Goal:** Hacer al Agente Contador completamente operacional con Alegra — toda operacion financiera (gasto, pago, factura, nomina) ejecutada correctamente via API con verificacion HTTP 200.

**Target features:**
- S0: Auditoria Alegra — mapear exactamente que funciona con URL corregida
- S1: Consolidacion capa Alegra (unica fuente de verdad, request_with_verify robusto)
- S2: ACTION_MAP completo — acciones de lectura + escritura funcionales
- S3: Chat transaccional real — gasto en lenguaje natural → journal en Alegra (F2: 3/10 → 7/10)
- S4: Facturacion venta motos con VIN obligatorio (F6: 1/10 → 8/10)
- S5: Ingresos cuotas cartera → journal ingreso en Alegra (F7: 5/10 → 8/10)
- S6: Nomina mensual discriminada con anti-duplicados (F4: 0/10 → 7/10)
- S7: Smoke test final — 10 criterios Alegra 100%

**Score objetivo:** 9.3/10 → 8.5/10 Agente Contador (score independiente del sistema)

**Restricciones tecnicas inamovibles:**
- URL base: `https://api.alegra.com/api/v1/` (hotfix v24-hotfix-alegra aplicado)
- `request_with_verify()` obligatorio en TODA operacion de escritura
- Fechas: `yyyy-MM-dd` estricto — NUNCA ISO-8601 con timezone
- Fallback cuentas: ID 5493 — NUNCA ID 5495
- Auteco NIT 860024781 = AUTORETENEDOR — nunca aplicar ReteFuente

## Context

- **Estado actual:** BUILD 23 completado — Score 9.0/10
- **Produccion:** 10 loanbooks activos, $94M COP cartera, 34 motos TVS
- **Stack:** FastAPI + React 19 + TypeScript + MongoDB Atlas + Alegra API + Mercately + Claude Sonnet
- **Arquitectura:** 6 capas horizontales + 5 nodos de negocio verticales + bus de eventos append-only
- **4 Agentes core:** Contador (Alegra), CFO (analisis financiero), RADAR (cobranza WhatsApp), Loanbook (ciclo de credito)
- **Principio:** Ningun agente llama a otro directamente — todo pasa por el bus de eventos
- **Tech debt critico:** ai_chat.py tiene 5,217 lineas, proveedor no se pasa en reconciliacion bancaria, cache invalidation dispersa
- **Usuarios:** Equipo pequeno (2-5 personas) con fundador como usuario principal
- **Hosting:** Render (render.yaml presente)

## Constraints

- **Tech stack**: FastAPI + React 19 + MongoDB Atlas — ya en produccion, no migrar
- **Integraciones**: Alegra es el sistema contable de record — toda operacion contable pasa por Alegra API
- **LLM**: Claude Sonnet via Anthropic SDK — ya integrado en ai_chat.py y cfo_agent.py
- **WhatsApp**: Mercately como proveedor — webhooks ya configurados
- **Produccion**: Sistema en uso real con datos financieros reales — no romper funcionalidad existente
- **Idioma**: Interfaz y datos en espanol (Colombia)
- **Principio rector**: Soberania Digital — ninguna plataforma de terceros debe ser duena del corazon operativo

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Bus de eventos append-only MongoDB | Trazabilidad completa de operaciones, ningun agente acoplado a otro | -- Pending |
| Alegra como sistema contable de record | Ya adoptado por RODDOS, API funcional, cumple requisitos colombianos | -- Pending |
| Claude Sonnet como LLM | Balance costo/calidad para clasificacion contable y chat | -- Pending |
| Mercately para WhatsApp | API estable, webhooks funcionando, cobranza remota critica | -- Pending |
| Arquitectura 6 capas + 5 nodos | Separacion de concerns, cada agente es independiente via bus | -- Pending |
| Smoke test con IDs reales de Alegra | Validacion end-to-end con datos de produccion, no mocks | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check -- still the right priority?
3. Audit Out of Scope -- reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-30 — Milestone v23.0 BUILD 23 started*
