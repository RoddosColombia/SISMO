# Roadmap: SISMO v23.0 BUILD 23 — Agente Contador 8.5/10 + Alegra 100%

## Overview

BUILD 23 hace al Agente Contador completamente operacional con Alegra. Cada operacion financiera de RODDOS (gasto, pago, factura de moto, nomina) se ejecuta via API con verificacion HTTP 200 obligatoria. El milestone avanza en 8 fases secuenciales: primero auditar lo que existe (Phase 1), luego consolidar la capa Alegra (Phase 2), luego expandir el ACTION_MAP de lectura (Phase 3), y finalmente habilitar los cuatro flujos transaccionales — chat (Phase 4), facturas (Phase 5), cartera (Phase 6), nomina (Phase 7) — validados por un smoke test final de 10 criterios (Phase 8).

**Restricciones tecnicas inamovibles:**
- URL base unica: `https://api.alegra.com/api/v1/`
- `request_with_verify()` en toda operacion de escritura
- Fechas: `yyyy-MM-dd` estricto (nunca ISO-8601 con timezone)
- Fallback cuentas: ID 5493 (nunca ID 5495)
- Endpoints prohibidos: /journal-entries (403), /accounts (403)
- Auteco NIT 860024781 = AUTORETENEDOR (nunca ReteFuente)

## Phases

**Phase Numbering:** Starts at 1 for milestone v23.0 (fresh cycle)

- [x] **Phase 1: Auditoria Alegra** - Mapear exactamente que funciona, que esta roto, y que falta en la capa Alegra con URL corregida (completed 2026-03-30)
- [ ] **Phase 2: Consolidacion Capa Alegra** - Unica fuente de verdad para Alegra, request_with_verify() robusto, errores en espanol
- [ ] **Phase 3: ACTION_MAP Completo** - Cinco acciones de lectura nuevas (facturas, pagos, journals, cartera, plan_cuentas) funcionales en el chat
- [ ] **Phase 4: Chat Transaccional Real** - Gasto en lenguaje natural → clasificacion matricial → ReteFuente/ReteICA → journal en Alegra con ID verificado
- [ ] **Phase 5: Facturacion Venta Motos** - POST /invoices con VIN + motor obligatorios, inventario actualizado, loanbook creado
- [ ] **Phase 6: Ingresos Cuotas Cartera** - Pago de cuota → POST /payments → journal ingreso en Alegra, anti-duplicados activo
- [ ] **Phase 7: Nomina Mensual** - Journals discriminados por empleado en Alegra con anti-duplicados por mes
- [ ] **Phase 8: Smoke Test Final** - 10 criterios Alegra 100% verificados end-to-end en produccion

## Phase Details

### Phase 1: Auditoria Alegra
**Goal**: El equipo sabe exactamente que funciona, que esta roto, y que falta en la integracion Alegra — con evidencia real de requests HTTP, no suposiciones
**Depends on**: Nothing (first phase — prerequisite obligatorio)
**Requirements**: AUDIT-01, AUDIT-02, AUDIT-03, AUDIT-04, AUDIT-05
**Success Criteria** (what must be TRUE):
  1. Existe un reporte escrito que clasifica utils/alegra.py vs services/alegra_service.py — se sabe cual es la fuente de verdad y cuales son los conflictos
  2. Cada endpoint probado tiene evidencia de su resultado real: GET /invoices, GET /categories, GET /payments, POST /journals — con HTTP status code y payload de respuesta
  3. request_with_verify() confirmado que usa `https://api.alegra.com/api/v1/` — ninguna variante de URL incorrecta puede pasar
  4. ACTION_MAP documentado: lista de acciones existentes, acciones faltantes (las 5 de lectura), y acciones rotas
**Plans**: TBD

### Phase 2: Consolidacion Capa Alegra
**Goal**: Hay una sola forma de llamar a Alegra en todo SISMO — ALEGRA_BASE_URL como constante unica, request_with_verify() con POST+GET+200, y errores en espanol
**Depends on**: Phase 1
**Requirements**: ALEGRA-01, ALEGRA-02, ALEGRA-03, ALEGRA-04, ALEGRA-05, ALEGRA-06
**Success Criteria** (what must be TRUE):
  1. Un grep de `utils/alegra.py` y `services/alegra_service.py` muestra arquitectura clara — no hay dos implementaciones paralelas del mismo cliente HTTP
  2. Todos los modulos que llaman a Alegra importan ALEGRA_BASE_URL desde un unico lugar — ningun modulo tiene la URL hardcoded localmente
  3. Llamar a POST /journals y luego verificar con GET /journals retorna HTTP 200 — request_with_verify() no reporta exito sin confirmacion
  4. Un error de Alegra (timeout, 403, 404) produce un mensaje en espanol legible para el usuario — nunca un stack trace ni un mensaje de API crudo
  5. Los tests del cliente Alegra pasan para los 5 endpoints principales
**Plans:** 2/3 plans executed
Plans:
- [x] 02-01-PLAN.md — TDD: Tests AlegraService (5 endpoints + errores) + fix mock journal-entries
- [x] 02-02-PLAN.md — Migrar 3 bypass simples (auditoria, conciliacion, dian_service)
- [ ] 02-03-PLAN.md — Migrar 2 bypass complejos (bank_reconciliation, alegra_webhooks)

### Phase 3: ACTION_MAP Completo
**Goal**: El Agente Contador puede responder consultas de lectura — facturas, pagos, journals, cartera, plan de cuentas — directamente desde el chat sin configuration adicional
**Depends on**: Phase 2
**Requirements**: ACTION-01, ACTION-02, ACTION-03, ACTION-04, ACTION-05
**Success Criteria** (what must be TRUE):
  1. Chat: "Muestrame las facturas de enero" → ACTION_MAP ejecuta consultar_facturas → retorna lista de facturas reales con fechas en formato yyyy-MM-dd
  2. Chat: "Cuantos pagos entraron en marzo" → ACTION_MAP ejecuta consultar_pagos type:in → retorna pagos reales de Alegra
  3. Chat: "Ver journals de febrero" → ACTION_MAP ejecuta consultar_journals → retorna asientos reales de Alegra
  4. Chat: "Como esta la cartera" → ACTION_MAP ejecuta consultar_cartera → lee MongoDB loanbook (no llama a Alegra)
  5. Chat: "Que cuentas tenemos" → ACTION_MAP ejecuta consultar_plan_cuentas → retorna plan de cuentas con IDs correctos incluyendo 5493
**Plans**: TBD

### Phase 4: Chat Transaccional Real
**Goal**: Un gasto descrito en lenguaje natural se convierte en un journal verificado en Alegra — con retenciones correctas, cuentas reales, y confirmacion del usuario antes de ejecutar
**Depends on**: Phase 3
**Requirements**: CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05
**Success Criteria** (what must be TRUE):
  1. Chat: "Pagamos arriendo $3.614.953" → agente propone asiento con ReteFuente 3.5% y ReteICA 0.414% calculados correctamente y cuentas reales de plan_cuentas_roddos
  2. Tras confirmacion del usuario: POST /journals con request_with_verify() → agente retorna ID real del journal en Alegra (no simulado)
  3. Chat: "Honorarios a Inversiones XYZ por $500.000" → agente aplica ReteFuente 11% (persona juridica) — ningun caso de retencion incorrecto
  4. Chat: "Compra a Auteco por $2.000.000" → agente NO aplica ReteFuente (autoretenedor NIT 860024781)
  5. Chat: "Prestamo a socio Andres $1.000.000" → agente registra en CXC socios, nunca en gasto operativo
**Plans**: TBD

### Phase 5: Facturacion Venta Motos
**Goal**: Crear una factura de venta de moto desde el chat o UI actualiza Alegra, inventario, y loanbook en una sola operacion atomica
**Depends on**: Phase 4
**Requirements**: FACTURA-01, FACTURA-02, FACTURA-03, FACTURA-04
**Success Criteria** (what must be TRUE):
  1. POST /invoices con VIN y motor reales crea factura en Alegra con descripcion "[Modelo] [Color] - VIN:[x] / Motor:[x]" — HTTP 200 confirmado
  2. Intento de crear factura sin VIN o sin motor retorna HTTP 400 con mensaje claro — Alegra nunca recibe la llamada
  3. Factura creada exitosamente → moto en inventario_motos aparece con estado Vendida
  4. Factura creada exitosamente → loanbook en estado pendiente_entrega existe + evento factura.venta.creada aparece en roddos_events
**Plans**: TBD
**UI hint**: yes

### Phase 6: Ingresos Cuotas Cartera
**Goal**: Cada pago de cuota recibido queda registrado en Alegra como ingreso verificado, sin posibilidad de duplicados
**Depends on**: Phase 5
**Requirements**: CARTERA-01, CARTERA-02, CARTERA-03
**Success Criteria** (what must be TRUE):
  1. Registrar un pago de cuota → POST /payments type:in → journal ingreso aparece en Alegra con cuenta de plan_ingresos_roddos — HTTP 200 confirmado
  2. Intentar registrar el mismo pago dos veces → sistema detecta el duplicado y retorna error claro, ningun segundo registro creado en Alegra
  3. CFO consultando portfolio_summaries puede ver el recaudo del pago registrado — el ingreso es visible en reportes financieros
**Plans**: TBD

### Phase 7: Nomina Mensual
**Goal**: La nomina de cada mes queda registrada en Alegra con un asiento por empleado, y el sistema impide registrar el mismo mes dos veces
**Depends on**: Phase 6
**Requirements**: NOMINA-01, NOMINA-02, NOMINA-03
**Success Criteria** (what must be TRUE):
  1. Registrar nomina enero 2026 → tres journals en Alegra (Alexa $3.220.000, Luis $3.220.000, Liz $1.472.000) — cada uno con HTTP 200 verificado
  2. Registrar nomina febrero 2026 → dos journals en Alegra (Alexa $4.500.000, Liz $2.200.000) — cada uno con HTTP 200 verificado
  3. Intentar registrar nomina de enero 2026 por segunda vez → sistema bloquea con error claro "nomina enero ya registrada para [empleado]"
**Plans**: TBD

### Phase 8: Smoke Test Final
**Goal**: Los 10 criterios de Alegra 100% estan verificados end-to-end en produccion — BUILD 23 puede darse por completado al 8.5/10
**Depends on**: Phase 7
**Requirements**: SMOKE-01, SMOKE-02, SMOKE-03, SMOKE-04, SMOKE-05, SMOKE-06, SMOKE-07, SMOKE-08, SMOKE-09, SMOKE-10
**Success Criteria** (what must be TRUE):
  1. Los 10 criterios SMOKE-01 a SMOKE-10 pasan sin fallo — evidencia de HTTP 200 o comportamiento esperado para cada uno
  2. El COMMIT PROTOCOL da 0 resultados en todos los greps: app.alegra.com/api/r1, /journal-entries, estado.*pending
  3. Un usuario real puede ejecutar desde el chat: consultar facturas, registrar un gasto, crear factura de moto, y registrar pago de cuota — todo con confirmacion en Alegra
  4. Alegra caido → el sistema retorna error en espanol y la UI sigue funcionando sin romper
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in strict dependency order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Auditoria Alegra | 2/2 | Complete    | 2026-03-30 |
| 2. Consolidacion Capa Alegra | 2/3 | In Progress|  |
| 3. ACTION_MAP Completo | 0/TBD | Not started | - |
| 4. Chat Transaccional Real | 0/TBD | Not started | - |
| 5. Facturacion Venta Motos | 0/TBD | Not started | - |
| 6. Ingresos Cuotas Cartera | 0/TBD | Not started | - |
| 7. Nomina Mensual | 0/TBD | Not started | - |
| 8. Smoke Test Final | 0/TBD | Not started | - |
