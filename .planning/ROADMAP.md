# Roadmap: SISMO

## Overview

SISMO is a production fintech system managing a $94M COP motorcycle loan portfolio at BUILD 23. This roadmap does not build a new system — it completes, hardens, and autonomizes one that already exists but has correctness gaps and tech debt creating financial integrity risk. The journey: fix the known bugs breaking accounting accuracy first (Phases 1-2), then build portfolio intelligence on clean data (Phases 3-4), then pursue digital sovereignty once the codebase is stable enough to safely containerize (Phases 5-6). Every phase delivers a coherent, verifiable capability that the next phase depends on.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [ ] **Phase 1: Contador Core** - Eliminar deuda tecnica critica: proveedor bug, ai_chat.py decomposition, idempotency, dead-letter queue, cache invalidation
- [ ] **Phase 2: Contador Validation** - Smoke test 20/20, clasificacion >=85%, reconciliacion batch optimizada, system prompts + confidence router
- [ ] **Phase 3: Orquestacion y Bus** - Bus de eventos tipado y validado, dashboard de monitoreo, flujos documentados, trazabilidad end-to-end
- [ ] **Phase 4: Loanbook Intelligence** - FSM con concurrency guards, Regla del Miercoles inviolable, PAR30/60/90, scoring de default, alertas predictivas, collection queue
- [ ] **Phase 5: WhatsApp 360** - Canal central del cliente: intenciones mejoradas, respuestas automaticas con datos reales, confirmacion de pagos, historial CRM
- [ ] **Phase 6: Soberania Digital** - Docker Compose, CI/CD, MongoDB Community, Nginx+SSL, secrets cifrados, JWT rotation

## Phase Details

### Phase 1: Contador Core
**Goal**: Los bugs criticos que corrompen silenciosamente la contabilidad estan eliminados y el Agente Contador opera sobre una base correcta
**Depends on**: Nothing (first phase)
**Requirements**: CONT-00, CONT-01, CONT-02, CONT-03, CONT-04, CONT-05
**Success Criteria** (what must be TRUE):
  1. El extracto bancario procesa proveedores correctamente y activa las 30+ reglas de clasificacion que estaban deshabilitadas
  2. ai_chat.py ha sido descompuesto en modulos (contador_agent.py, context_builder.py, file_parser.py, prompt_templates.py) y el sistema funciona identicamente
  3. Todas las escrituras a Alegra (contactos, facturas, pagos, recibos) tienen idempotency keys y no crean duplicados ante reintentos
  4. Los webhooks fallidos de Alegra se almacenan en dead-letter queue y se reintentan con backoff exponencial sin perder eventos
  5. El cache se invalida inmediatamente cuando se emite un evento relevante, sin esperar TTL de 30 segundos
**Plans**: TBD

### Phase 2: Contador Validation
**Goal**: El Agente Contador alcanza 8.5/10 con smoke test 20/20 pasando contra IDs reales de Alegra, clasificacion >=85% de confianza, y reconciliacion bancaria a 90%+ de match
**Depends on**: Phase 1
**Requirements**: CONT-06, CONT-07, CONT-08, ORQU-05, ORQU-06
**Success Criteria** (what must be TRUE):
  1. El smoke test completa los 20/20 pasos del ciclo contable (crear contacto, crear factura, registrar pago, emitir recibo de caja, conciliar movimiento bancario) usando IDs reales de Alegra
  2. Las transacciones con proveedor identificado obtienen clasificacion contable con confianza >= 85%
  3. La reconciliacion bancaria batch usa asyncio.gather para llamadas Alegra y $in para MongoDB, completando en tiempo aceptable para el volumen actual
  4. Cada agente (Contador, CFO, RADAR, Loanbook) tiene su propio system prompt con identidad, herramientas y restricciones especificas
  5. El router no despacha al agente equivocado: si confianza < 0.7 el sistema pregunta al usuario antes de ejecutar
**Plans**: TBD
**UI hint**: yes

### Phase 3: Orquestacion y Bus
**Goal**: El bus de eventos es confiable, monitoreable y cada operacion de backoffice tiene un flujo documentado con trazabilidad completa hasta Alegra
**Depends on**: Phase 2
**Requirements**: ORQU-01, ORQU-02, ORQU-03, ORQU-04
**Success Criteria** (what must be TRUE):
  1. El bus de eventos rechaza eventos con schema invalido antes de insertarlos en roddos_events (schemas validados por tipo de evento)
  2. El dashboard de monitoreo muestra eventos procesados, fallidos, pendientes y latencia por tipo de evento en tiempo real
  3. Cada operacion de backoffice (registrar pago, causar gasto, conciliar extracto, activar loanbook) tiene un flujo documentado que especifica el agente responsable y los eventos que emite
  4. El usuario puede trazar cualquier accion desde la interfaz hasta su reflejo en Alegra consultando roddos_events, sin saltos ni pasos oscuros
**Plans**: TBD
**UI hint**: yes

### Phase 4: Loanbook Intelligence
**Goal**: La cartera es visible en tiempo real con metricas PAR correctas, scoring de riesgo por cliente, alertas predictivas de mora, y collection queue priorizada — todo respetando la Regla del Miercoles sin excepcion
**Depends on**: Phase 3
**Requirements**: LOAN-01, LOAN-06, LOAN-02, LOAN-03, LOAN-04, LOAN-05
**Success Criteria** (what must be TRUE):
  1. Las transiciones de estado del loanbook (pendiente_entrega -> activo -> cancelado) son seguras bajo concurrencia: dos procesos simultaneos no pueden poner un loanbook en estado invalido
  2. Toda logica de cuotas, fechas de corte y generacion de planes de pago produce fechas que caen en miercoles segun la Regla del Miercoles, sin excepcion verificable
  3. El CFO dashboard muestra metricas PAR30/PAR60/PAR90 calculadas diariamente con datos reales de cuotas
  4. Cada cliente tiene un score de probabilidad de default basado en su historial de pagos y DPD, visible en su perfil
  5. El sistema genera alertas antes de que un cliente caiga en mora, basandose en patrones de comportamiento detectados
  6. La cola de cobranza muestra los clientes ordenados por riesgo, monto adeudado y dias de mora para priorizar gestiones
**Plans**: TBD
**UI hint**: yes

### Phase 5: WhatsApp 360
**Goal**: WhatsApp es el canal operativo completo del cliente: el sistema detecta intenciones, responde con datos reales del loanbook, confirma pagos y mantiene historial en el CRM
**Depends on**: Phase 4
**Requirements**: WA360-01, WA360-02, WA360-03, WA360-04, WA360-05
**Success Criteria** (what must be TRUE):
  1. El sistema detecta correctamente las intenciones del cliente por WhatsApp: saldo, pago realizado, dificultad de pago, consulta de repuestos, estado de moto
  2. Cuando un cliente pregunta su saldo por WhatsApp, recibe el saldo actualizado y la proxima cuota con fecha y monto reales de su loanbook
  3. Cuando un cliente reporta haber pagado por WhatsApp, el sistema verifica en el extracto bancario y confirma o escala a operador segun corresponda
  4. El historial completo de conversaciones WhatsApp de un cliente aparece en su perfil CRM como parte del timeline 360 del cliente
**Plans**: TBD

### Phase 6: Soberania Digital
**Goal**: SISMO corre en infraestructura propia con Docker Compose, CI/CD automatizado, MongoDB Community como opcion sin Render, secrets cifrados y JWT rotation — sin depender de plataformas de terceros para su corazon operativo
**Depends on**: Phase 5
**Requirements**: INFRA-01, INFRA-02, INFRA-03, INFRA-04, INFRA-05, INFRA-06
**Success Criteria** (what must be TRUE):
  1. El sistema completo (frontend, backend, MongoDB) arranca con un solo comando Docker Compose en cualquier servidor Linux
  2. Un push a main desencadena automaticamente build, tests y deploy sin intervencion manual
  3. La migracion de MongoDB Atlas a Community 7.0 esta documentada y probada: backup, restore y validacion de integridad de datos completa
  4. El sistema sirve trafico HTTPS con certificado valido a traves de Nginx como reverse proxy
  5. Ningun secreto existe en texto plano: todas las credenciales estan cifradas en el sistema de secrets management
  6. Los tokens JWT de acceso son de vida corta y el sistema implementa refresh tokens para sesiones persistentes
**Plans**: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 → 2 → 3 → 4 → 5 → 6

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Contador Core | 0/TBD | Not started | - |
| 2. Contador Validation | 0/TBD | Not started | - |
| 3. Orquestacion y Bus | 0/TBD | Not started | - |
| 4. Loanbook Intelligence | 0/TBD | Not started | - |
| 5. WhatsApp 360 | 0/TBD | Not started | - |
| 6. Soberania Digital | 0/TBD | Not started | - |
