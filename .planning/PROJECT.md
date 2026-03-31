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
- [x] Anti-duplicate guard para pagos de cartera (HTTP 409) + cartera_pagos visible en portfolio CFO — Validated in Phase 06: ingresos-cuotas-cartera

### Active (BUILD 24 — Cimientos Definitivos)

- [ ] Bus de eventos tipado y validado (EventBusService + DLQ + retry, reemplaza event_bus.py falso)
- [ ] Permisos de escritura de agentes validados en codigo Python (no en prompts del LLM)
- [ ] MongoDB completo: 30+ colecciones con indices ESR, schema validation, datos sembrados
- [ ] System prompts diferenciados por agente + router con confidence threshold 0.7
- [ ] Portfolio summaries pre-calculados (Computed Pattern) + financial reports mensuales
- [ ] sismo_knowledge como base RAG para reglas de negocio de los agentes
- [x] GitHub CI/CD expandido: pytest, smoke test, anti-pending check, Dependabot — Validated in Phase 05: github-production-ready
- [x] Facturación venta motos: FACTURA-01 (formato VIN/Motor), FACTURA-02 (validación HTTP 400), FACTURA-03 (estado Vendida), FACTURA-04 (loanbook + evento) — Validated in Phase 05: github-production-ready
- [ ] CFO leyendo portfolio_summaries en vez de Alegra directo (70% menos llamadas API)

### Out of Scope

- App movil nativa — web-first, mobile responsive es suficiente
- Multitenancy — SISMO es exclusivo para RODDOS S.A.S.
- Integracion con bancos directa — se usa reconciliacion via CSV/Excel
- Facturacion electronica DIAN en produccion — DIAN stubbed, se implementara cuando haya certificado

## Current Milestone: v2.0 BUILD 24 — Cimientos Definitivos

**Goal:** Establecer los cimientos estructurales de SISMO para escalar como fintech: MongoDB completo, bus de eventos real, permisos de agentes en codigo, system prompts diferenciados, y CI/CD con pytest.

**Target features:**
- Bus de eventos real (EventBusService + DLQ + retry)
- Permisos de escritura de agentes en codigo (WRITE_PERMISSIONS)
- MongoDB 30+ colecciones con indices, validation, datos sembrados
- System prompts diferenciados + confidence router 0.7
- Portfolio summaries + financial reports pre-calculados
- sismo_knowledge base RAG
- GitHub CI/CD expandido + Dependabot
- CFO lee portfolio_summaries, no Alegra directo

**Score objetivo:** 9.0/10 → 9.3/10

## Context

- **Estado actual:** BUILD 23 en progreso — Phase 6 completa, Phase 7 (Nomina) siguiente
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
*Last updated: 2026-03-31 — Phase 05 complete: GitHub CI/CD + FACTURA-01-04 enforced in tests and production*
