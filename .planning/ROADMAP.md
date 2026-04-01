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
- [x] **Phase 2: Consolidacion Capa Alegra** - Unica fuente de verdad para Alegra, request_with_verify() robusto, errores en espanol (completed 2026-03-30)
- [x] **Phase 3: ACTION_MAP Completo** - Cinco acciones de lectura nuevas (facturas, pagos, journals, cartera, plan_cuentas) funcionales en el chat (completed 2026-03-31)
- [x] **Phase 4: Chat Transaccional Real** - Gasto en lenguaje natural → clasificacion matricial → ReteFuente/ReteICA → journal en Alegra con ID verificado (completed 2026-03-31)
- [ ] **Phase 5: Facturacion Venta Motos** - POST /invoices con VIN + motor obligatorios, inventario actualizado, loanbook creado
- [x] **Phase 6: Ingresos Cuotas Cartera** - Pago de cuota → POST /payments → journal ingreso en Alegra, anti-duplicados activo (completed 2026-03-31)
- [x] **Phase 7: Nomina Mensual** - Journals discriminados por empleado en Alegra con anti-duplicados por mes (completed 2026-03-31)
- [ ] **Phase 8: Smoke Test Final** - 10 criterios Alegra 100% verificados end-to-end en produccion
- [ ] **Phase 9: Tool Use Agente Contador** - Migrar process_chat() de ACTION_MAP + XML parsing a loop nativo tool_use de Anthropic API
- [x] **Phase 10: ReAct Nivel 1 + Memoria Persistente** - Plan multi-accion aprobado por usuario + ejecucion autonoma secuencial + agent_memory sin TTL inyectada en system prompt (completed 2026-04-01)

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
**Plans:** 4/4 plans complete
Plans:
- [x] 02-01-PLAN.md — TDD: Tests AlegraService (5 endpoints + errores) + fix mock journal-entries
- [x] 02-02-PLAN.md — Migrar 3 bypass simples (auditoria, conciliacion, dian_service)
- [x] 02-03-PLAN.md — Migrar 2 bypass complejos (bank_reconciliation, alegra_webhooks)

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
**Plans:** 2/2 plans complete
Plans:
- [x] 03-01-PLAN.md — TDD: Failing test suite for 5 ACTION_MAP read actions
- [x] 03-02-PLAN.md — Implement 5 read action handlers + MOCK_PAYMENTS

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
**Plans:** 6/6 plans complete
Plans:
- [x] 04-05-PLAN.md — TDD: Failing tests for clasificar_gasto_chat + request_with_verify + special cases
- [x] 04-06-PLAN.md — Implement clasificar_gasto_chat + fix crear_causacion + Auteco/socio guards

### Phase 5: Facturacion Venta Motos
**Goal**: Crear una factura de venta de moto desde el chat o UI actualiza Alegra, inventario, y loanbook en una sola operacion atomica
**Depends on**: Phase 4
**Requirements**: FACTURA-01, FACTURA-02, FACTURA-03, FACTURA-04
**Success Criteria** (what must be TRUE):
  1. POST /invoices con VIN y motor reales crea factura en Alegra con descripcion "[Modelo] [Color] - VIN:[x] / Motor:[x]" — HTTP 200 confirmado
  2. Intento de crear factura sin VIN o sin motor retorna HTTP 400 con mensaje claro — Alegra nunca recibe la llamada
  3. Factura creada exitosamente → moto en inventario_motos aparece con estado Vendida
  4. Factura creada exitosamente → loanbook en estado pendiente_entrega existe + evento factura.venta.creada aparece en roddos_events
**Plans:** 2 plans (05-04, 05-05)
Plans:
- [ ] 05-04-PLAN.md -- TDD: Fix test isolation (qrcode stub) + update T6 for FACTURA-01 format
- [ ] 05-05-PLAN.md -- Fix ventas.py description format per FACTURA-01 (GREEN)
**UI hint**: yes

### Phase 6: Ingresos Cuotas Cartera
**Goal**: Cada pago de cuota recibido queda registrado en Alegra como ingreso verificado, sin posibilidad de duplicados
**Depends on**: Phase 5
**Requirements**: CARTERA-01, CARTERA-02, CARTERA-03
**Success Criteria** (what must be TRUE):
  1. Registrar un pago de cuota → POST /payments type:in → journal ingreso aparece en Alegra con cuenta de plan_ingresos_roddos — HTTP 200 confirmado
  2. Intentar registrar el mismo pago dos veces → sistema detecta el duplicado y retorna error claro, ningun segundo registro creado en Alegra
  3. CFO consultando portfolio_summaries puede ver el recaudo del pago registrado — el ingreso es visible en reportes financieros
**Plans:** 2 plans
Plans:
- [x] 06-01-PLAN.md — TDD: Fix test isolation (qrcode stub) + T1-T6 GREEN + T7 RED (anti-duplicado) (completed 2026-03-31)
- [x] 06-02-PLAN.md — Implement anti-duplicate guard (T7 GREEN) + fix cartera_pagos→portfolio wiring (T8 GREEN) (completed 2026-03-31)

### Phase 7: Nomina Mensual
**Goal**: La nomina de cada mes queda registrada en Alegra con un asiento por empleado, y el sistema impide registrar el mismo mes dos veces
**Depends on**: Phase 6
**Requirements**: NOMINA-01, NOMINA-02, NOMINA-03
**Success Criteria** (what must be TRUE):
  1. Registrar nomina enero 2026 → tres journals en Alegra (Alexa $3.220.000, Luis $3.220.000, Liz $1.472.000) — cada uno con HTTP 200 verificado
  2. Registrar nomina febrero 2026 → dos journals en Alegra (Alexa $4.500.000, Liz $2.200.000) — cada uno con HTTP 200 verificado
  3. Intentar registrar nomina de enero 2026 por segunda vez → sistema bloquea con error claro "nomina enero ya registrada para [empleado]"
**Plans:** 2 plans
Plans:
- [ ] 07-01-PLAN.md — TDD: Test suite T1-T7 for nomina mensual (journals per employee, anti-duplicate)
- [ ] 07-02-PLAN.md — Implement nomina.py router + wire into server.py (T1-T7 GREEN)

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

### Phase 9: Tool Use Agente Contador
**Goal**: process_chat() usa el loop nativo tool_use de Anthropic API — sin `<action>` XML parsing, sin ACTION_MAP string dispatch, con definiciones de herramientas tipadas y loop agentico real
**Depends on**: Phase 8
**Requirements**: TOOLUSE-01, TOOLUSE-02, TOOLUSE-03, TOOLUSE-04, TOOLUSE-05
**Success Criteria** (what must be TRUE):
  1. "Pagamos arriendo $3.614.953" → Claude llama tool `crear_causacion` con JSON estructurado → journal en Alegra con HTTP 200 verificado — sin intermediacion XML
  2. Cero usos de `<action>` o `</action>` en el flujo contador — el XML parsing es codigo muerto
  3. Cada tool tiene input_schema JSON con tipos, required fields, y descriptions — el LLM no puede llamar una tool con payload invalido
  4. Rollback: una variable de entorno `TOOL_USE_ENABLED=false` activa el flujo antiguo sin deployar nuevo codigo
  5. Los tests del BUILD activo (permissions, event_bus, mongodb_init, phase4_agents) siguen pasando sin modificacion
**Plans:** 2 plans
Plans:
- [ ] 09-01-PLAN.md -- TDD RED: Tool definitions + failing test suite for tool_use loop
- [ ] 09-02-PLAN.md -- TDD GREEN: Implement tool_use branch in process_chat + tool_executor

### Phase 10: ReAct Nivel 1 + Memoria Persistente
**Goal**: El Agente Contador puede ejecutar planes de multiples acciones de forma autonoma tras una sola aprobacion del usuario, y aprende de cada interaccion persistiendo aprendizajes sin TTL en agent_memory
**Depends on**: Phase 9
**Requirements**: REACT-01, REACT-02, REACT-03, REACT-04, REACT-05, REACT-06, REACT-07, REACT-08, REACT-09
**Success Criteria** (what must be TRUE):
  1. "Registra gasto internet Y pago cartera LB-0001" → agente propone plan de 2 pasos → usuario aprueba una vez → ambas acciones ejecutadas autonomamente con 2 alegra_ids en evidencia
  2. create_plan() crea documento en agent_plans con status pending_approval antes de ejecutar nada
  3. execute_plan() para en el primer paso fallido y retorna error descriptivo al usuario
  4. Una sola accion de lectura se ejecuta directo sin crear agent_plans (comportamiento anterior preservado)
  5. extract_and_save_memory() detecta aprendizajes y los persiste en agent_memory con confidence >= 0.7
  6. System prompt incluye seccion "MEMORIA PERSISTENTE" con los ultimos 20 aprendizajes del usuario
  7. T1-T8 pasan GREEN (T9 acepta xfail — requiere Alegra real para verificar 2 alegra_ids)
**Plans:** 2/2 plans complete
Plans:
- [x] 10-01-PLAN.md -- Phase 10A: agent_plans + create_plan + execute_plan + approve-plan endpoint (T1-T4 GREEN)
- [x] 10-02-PLAN.md -- Phase 10B: extract_and_save_memory + memory injection en system prompt (T5-T8 GREEN)

## Progress

**Execution Order:**
Phases execute in strict dependency order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7 -> 8

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Auditoria Alegra | 2/2 | Complete    | 2026-03-30 |
| 2. Consolidacion Capa Alegra | 4/4 | Complete    | 2026-03-31 |
| 3. ACTION_MAP Completo | 2/2 | Complete   | 2026-03-31 |
| 4. Chat Transaccional Real | 6/6 | Complete   | 2026-03-31 |
| 5. Facturacion Venta Motos | 0/2 | In progress | - |
| 6. Ingresos Cuotas Cartera | 2/2 | Complete | 2026-03-31 |
| 7. Nomina Mensual | 0/2 | Not started | - |
| 8. Smoke Test Final | 0/TBD | Not started | - |
| 9. Tool Use Agente Contador | 2/2 | Complete | 2026-04-01 |
| 10. ReAct Nivel 1 + Memoria Persistente | 2/2 | Complete    | 2026-04-01 |
