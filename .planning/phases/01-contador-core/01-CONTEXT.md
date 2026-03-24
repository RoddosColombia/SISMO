# Phase 1: Contador Core - Context

**Gathered:** 2026-03-24
**Updated:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminar deuda tecnica critica que corrompe silenciosamente la contabilidad: fix proveedor bug, descomponer ai_chat.py, implementar idempotency keys, dead-letter queue, cache invalidation event-driven. Ademas, mapear los 32 flujos contables de Flujos_contables_Roddos.svg y asegurar que cada uno tiene un path automatizado hacia Alegra via el Agente Contador (CONT-00).

Alegra es el libro legal; SISMO es el cerebro operativo. Esta fase establece la base correcta sobre la cual todas las demas fases dependen.

</domain>

<decisions>
## Implementation Decisions

### Prioridad de Ejecucion (LOCKED — usuario definio orden)
- **P-01:** PRIMERO: CONT-01 (fix proveedor extraction) — desbloquea la conciliacion bancaria que es el flujo de mayor volumen
- **P-02:** SEGUNDO: CONT-06 (smoke test 20/20) — establecer baseline de calidad ANTES de descomponer. Nota: CONT-06 esta en Phase 2 del roadmap pero el usuario lo requiere en Phase 1 como gate de calidad pre-decomposicion
- **P-03:** TERCERO: CONT-02 (decomposicion ai_chat.py) — refactoring seguro porque el smoke test ya valida el comportamiento
- **P-04:** CONT-03, CONT-04, CONT-05: en paralelo con CONT-02

### Reglas de Negocio Inviolables (LOCKED — zero tolerance)
- **R-01:** NUNCA reportar exito sin verificar HTTP 200 en respuesta de Alegra. Todo call a Alegra debe verificar status code antes de continuar.
- **R-02:** Endpoint correcto para journals: `/journals` — NUNCA usar `/journal-entries` (retorna 403). Todo codigo que llame a Alegra para asientos debe usar exclusivamente `/journals`.
- **R-03:** IDs de cuentas contables SIEMPRE desde MongoDB coleccion `plan_cuentas_roddos` — nunca hardcoded, nunca desde otra fuente.
- **R-04:** Auteco NIT 860024781 = autoretenedor. NUNCA aplicar ReteFuente a Auteco. Esta regla debe estar en accounting_engine.py como constraint explicito.

### CONT-00: Mandato Estrategico — Cobertura de Flujos Contables
- **D-00:** Auditar los 32 flujos del SVG Flujos_contables_Roddos.svg contra el codigo actual. Cada flujo se clasifica como: Funcional, Parcial, o No implementado. El entregable es una matriz de cobertura que guia el trabajo de esta fase y las siguientes.
- **D-00b:** Los flujos que ya funcionan se verifican con test. Los parciales o faltantes se priorizan segun impacto financiero (ingresos > egresos > analisis).
- **D-00c:** Los 32 flujos se organizan en 4 categorias:
  - **Ingresos:** ventas motos, recaudo cuotas, prestamos, rendimientos
  - **Egresos:** gastos, nomina, activos, anticipos, intereses
  - **Bancario:** conciliacion 4 bancos, 4x1000, comisiones
  - **Analisis:** CXC, CXP, P&L, flujo de caja
- **D-00d:** CONT-00 se considera completado cuando los 32 flujos tienen un endpoint o accion en el Agente Contador que los procesa y envia el journal correcto a Alegra.

### CONT-01: Fix Proveedor Extraction
- **D-01:** El fix va en `backend/services/bank_reconciliation.py` — la funcion `extract_proveedor` de `accounting_engine.py` ya existe y se llama, pero el valor no se propaga correctamente al objeto de transaccion. Fix quirurgico: asegurar que el campo `proveedor` se pasa en todas las rutas de parsing (lineas 119-260 tienen 4 bloques duplicados que extraen proveedor).
- **D-01b:** Consolidar los 4 bloques duplicados de extraccion de proveedor en una sola funcion helper para evitar drift futuro.

### CONT-02: Decomposicion de ai_chat.py
- **D-02:** Descomposicion incremental (no big-bang): extraer un modulo a la vez, verificar con tests existentes que el comportamiento no cambia, commit por modulo.
- **D-02b:** Estructura objetivo:
  - `backend/agents/contador_agent.py` — logica del agente Contador (tool calls, decision making)
  - `backend/agents/context_builder.py` — construccion de contexto para prompts (datos de Alegra, MongoDB, loanbooks)
  - `backend/agents/file_parser.py` — parsing de extractos bancarios, facturas, documentos subidos
  - `backend/agents/prompt_templates.py` — system prompts y templates de mensajes
  - `backend/ai_chat.py` — queda como thin router/dispatcher que importa de los modulos
- **D-02c:** Las funciones existentes de ai_chat.py se mueven tal cual (no refactorizar logica interna en esta fase). El objetivo es separacion, no mejora.
- **D-02d:** La decomposicion se hace DESPUES de que el smoke test 20/20 pasa (P-02/P-03), para tener un gate de regresion confiable.

### CONT-03: Idempotency Keys para Alegra
- **D-03:** Esquema de key: `{operacion}:{entity_type}:{hash_de_datos_unicos}` — ejemplo: `create:contact:{hash(nit+nombre)}`, `create:invoice:{hash(contact_id+items+date)}`.
- **D-03b:** Storage en MongoDB coleccion `idempotency_keys` con TTL index de 7 dias. Antes de cada escritura a Alegra, check si la key existe; si existe, retornar el resultado previo sin llamar a Alegra.
- **D-03c:** Implementar en `backend/alegra_service.py` como decorator o wrapper sobre los metodos de escritura.

### CONT-04: Dead-Letter Queue
- **D-04:** Coleccion MongoDB `dead_letter_queue` con schema: `{event_id, event_type, payload, error, attempts, next_retry, created_at, resolved_at}`.
- **D-04b:** Retry policy: max 5 reintentos con backoff exponencial (1min, 5min, 15min, 1h, 4h). Despues del 5to fallo, marcar como `failed` y emitir evento `dlq.exhausted` al bus.
- **D-04c:** Procesamiento via el scheduler existente (`APScheduler` en `backend/services/scheduler.py`) — job que corre cada minuto revisando items con `next_retry <= now()`.
- **D-04d:** Alertas: emitir evento al bus que el frontend puede mostrar. No se necesita integracion externa de alertas en esta fase.

### CONT-05: Cache Invalidation Event-Driven
- **D-05:** Suscribir `shared_state.py` al event bus: cuando se emite un evento de escritura (pago registrado, factura creada, contacto actualizado), invalidar las keys de cache relevantes inmediatamente.
- **D-05b:** Mapeo evento->cache keys: cada tipo de evento tiene una lista de prefijos de cache que invalida. Ejemplo: `pago.cuota.registrado` invalida `loanbook:{id}`, `cartera:*`, `dashboard:kpis`.
- **D-05c:** TTL de 30 segundos se mantiene como fallback de seguridad, no como mecanismo primario.

### CONT-06: Smoke Test 20/20 (pulled into Phase 1 by user decision)
- **D-06:** El smoke test se ejecuta en Phase 1 ANTES de la decomposicion (ver prioridad P-02). Establece el baseline de calidad que protege el refactoring.
- **D-06b:** Los 20 pasos del ciclo contable completo se corren contra IDs reales de Alegra. Cada paso verifica HTTP 200 (R-01).

### Claude's Discretion
- Nombres exactos de funciones internas y helpers
- Estructura de tests unitarios
- Nivel de logging y telemetria interna

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Flujos Contables
- `Flujos_contables_Roddos.svg` — **CRITICO:** Define los 32 flujos contables RODDOS hacia Alegra. Organizado en 4 categorias (Ingresos, Egresos, Bancario, Analisis). **NOTA:** El archivo NO esta en el repo aun — debe ser agregado al directorio del proyecto antes de iniciar la auditoria CONT-00.

### Reglas de Negocio
- `backend/services/accounting_engine.py` — Motor de clasificacion con 50+ reglas. Debe contener constraint explicito para Auteco NIT 860024781 = autoretenedor (R-04).
- MongoDB coleccion `plan_cuentas_roddos` — Fuente unica de IDs de cuentas contables (R-03). Referenciada en 9 archivos del backend.

### Codigo Existente (obligatorio leer)
- `backend/ai_chat.py` — Monolito de 5,217 lineas a descomponer (CONT-02)
- `backend/services/bank_reconciliation.py` — Bug de proveedor (CONT-01), 4 bloques duplicados de extraccion
- `backend/alegra_service.py` — API client de Alegra, punto de insercion para idempotency (CONT-03). Debe usar `/journals` nunca `/journal-entries` (R-02).
- `backend/event_bus.py` — Bus de eventos actual, base para dead-letter (CONT-04) y cache invalidation (CONT-05)
- `backend/services/shared_state.py` — Cache in-memory actual, objetivo de invalidation event-driven (CONT-05)
- `backend/services/scheduler.py` — APScheduler existente, para procesar dead-letter retries (CONT-04)
- `backend/run_smoke_test.py` — Smoke test existente, base para CONT-06

### Integraciones
- `backend/routers/alegra_webhooks.py` — Webhooks de Alegra, fuente de eventos que pueden fallar (CONT-04)
- `backend/routers/conciliacion.py` — Router de conciliacion bancaria, usa journals endpoint

### Documentacion Existente
- `memory/PRD.md` — PRD original con reglas de negocio
- `memory/ARCHITECTURE.md` — Arquitectura del sistema
- `SMOKE_TEST_INSTRUCTIONS.md` — Instrucciones del smoke test actual

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `event_bus.py`: Bus append-only funcional — agregar suscripciones para cache invalidation y dead-letter
- `accounting_engine.py`: 50+ reglas de clasificacion + `extract_proveedor` — ya existe, solo necesita que el valor se propague. Incluye reglas de autoretencion.
- `scheduler.py`: APScheduler configurado — reusar para dead-letter retry jobs
- `alegra_service.py`: Client de Alegra centralizado — punto unico para agregar idempotency wrapper
- `run_smoke_test.py`: Smoke test existente — base para CONT-06
- `plan_cuentas_roddos` (MongoDB): Catalogo de cuentas contables — fuente unica para IDs

### Established Patterns
- Event bus: `emit_event(event_type, payload)` -> insert en `roddos_events`
- Cache: `shared_state.py` usa dict in-memory con TTL manual de 30s
- Alegra calls: centralizados en `alegra_service.py` con metodos como `create_contact`, `create_invoice`, `register_payment`
- Journals: endpoint `/journals` en Alegra (NO `/journal-entries`)
- Routers: cada dominio tiene su router en `backend/routers/`

### Integration Points
- `bank_reconciliation.py` lineas 119-260: 4 bloques que llaman `extract_proveedor` — consolidar
- `alegra_service.py`: wrap metodos de escritura con idempotency check
- `event_bus.py`: agregar `subscribe(event_type, callback)` para cache invalidation
- `ai_chat.py`: extraer funciones a modulos bajo `backend/agents/`
- Conciliacion bancaria de 4 bancos (ver Flujos_contables_Roddos.svg categoria Bancario)

</code_context>

<specifics>
## Specific Ideas

- CONT-00 es bloqueante: sin la matriz de cobertura de los 32 flujos, no se puede medir exito de esta fase ni de las siguientes
- El SVG Flujos_contables_Roddos.svg es el documento maestro — toda decision de "que automatizar" se mide contra el
- Principio: Alegra es el libro legal, SISMO es el cerebro operativo — nunca duplicar datos contables fuera de Alegra
- CONT-06 se ejecuta en Phase 1 (no Phase 2) como gate de calidad pre-decomposicion — el usuario movio esta prioridad explicitamente
- Las 4 reglas inviolables (R-01 a R-04) deben ser verificadas en CADA plan y CADA test — son constraints de produccion aprendidos por experiencia

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-contador-core*
*Context gathered: 2026-03-24*
*Updated: 2026-03-24 — added execution priority, business rules, CONT-06 pull-in, SVG structure*
