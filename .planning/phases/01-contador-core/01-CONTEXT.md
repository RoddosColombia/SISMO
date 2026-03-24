# Phase 1: Contador Core - Context

**Gathered:** 2026-03-24
**Status:** Ready for planning

<domain>
## Phase Boundary

Eliminar deuda tecnica critica que corrompe silenciosamente la contabilidad: fix proveedor bug, descomponer ai_chat.py, implementar idempotency keys, dead-letter queue, cache invalidation event-driven. Ademas, mapear los 32 flujos contables de Flujos_contables_Roddos.svg y asegurar que cada uno tiene un path automatizado hacia Alegra via el Agente Contador (CONT-00).

Alegra es el libro legal; SISMO es el cerebro operativo. Esta fase establece la base correcta sobre la cual todas las demas fases dependen.

</domain>

<decisions>
## Implementation Decisions

### CONT-00: Mandato Estrategico — Cobertura de Flujos Contables
- **D-00:** Auditar los 32 flujos del SVG Flujos_contables_Roddos.svg contra el codigo actual. Cada flujo se clasifica como: Funcional, Parcial, o No implementado. El entregable es una matriz de cobertura que guia el trabajo de esta fase y las siguientes.
- **D-00b:** Los flujos que ya funcionan se verifican con test. Los parciales o faltantes se priorizan segun impacto financiero (ingresos > egresos > analisis).

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

### Claude's Discretion
- Orden de implementacion de los 5 CONT (el planner decide la secuencia optima basada en dependencias)
- Nombres exactos de funciones internas y helpers
- Estructura de tests unitarios
- Nivel de logging y telemetria interna

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Flujos Contables
- `Flujos_contables_Roddos.svg` — **CRITICO:** Define los 32 flujos contables que RODDOS debe tener automatizados hacia Alegra. Este archivo NO esta en el repo aun — el usuario debe proveerlo antes de ejecutar la auditoria CONT-00. Si no se encuentra, preguntar al usuario.

### Codigo Existente (obligatorio leer)
- `backend/ai_chat.py` — Monolito de 5,217 lineas a descomponer (CONT-02)
- `backend/services/bank_reconciliation.py` — Bug de proveedor (CONT-01), 4 bloques duplicados de extraccion
- `backend/services/accounting_engine.py` — Motor de clasificacion con 50+ reglas, funcion `extract_proveedor`
- `backend/alegra_service.py` — API client de Alegra, punto de insercion para idempotency (CONT-03)
- `backend/event_bus.py` — Bus de eventos actual, base para dead-letter (CONT-04) y cache invalidation (CONT-05)
- `backend/services/shared_state.py` — Cache in-memory actual, objetivo de invalidation event-driven (CONT-05)
- `backend/services/scheduler.py` — APScheduler existente, para procesar dead-letter retries (CONT-04)

### Integraciones
- `backend/routers/alegra_webhooks.py` — Webhooks de Alegra, fuente de eventos que pueden fallar (CONT-04)

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `event_bus.py`: Bus append-only funcional — agregar suscripciones para cache invalidation y dead-letter
- `accounting_engine.py`: 50+ reglas de clasificacion + `extract_proveedor` — ya existe, solo necesita que el valor se propague
- `scheduler.py`: APScheduler configurado — reusar para dead-letter retry jobs
- `alegra_service.py`: Client de Alegra centralizado — punto unico para agregar idempotency wrapper

### Established Patterns
- Event bus: `emit_event(event_type, payload)` -> insert en `roddos_events`
- Cache: `shared_state.py` usa dict in-memory con TTL manual de 30s
- Alegra calls: centralizados en `alegra_service.py` con metodos como `create_contact`, `create_invoice`, `register_payment`
- Routers: cada dominio tiene su router en `backend/routers/`

### Integration Points
- `bank_reconciliation.py` lineas 119-260: 4 bloques que llaman `extract_proveedor` — consolidar
- `alegra_service.py`: wrap metodos de escritura con idempotency check
- `event_bus.py`: agregar `subscribe(event_type, callback)` para cache invalidation
- `ai_chat.py`: extraer funciones a modulos bajo `backend/agents/`

</code_context>

<specifics>
## Specific Ideas

- CONT-00 es bloqueante: sin la matriz de cobertura de los 32 flujos, no se puede medir exito de esta fase ni de las siguientes
- El SVG Flujos_contables_Roddos.svg es el documento maestro — toda decision de "que automatizar" se mide contra el
- Principio: Alegra es el libro legal, SISMO es el cerebro operativo — nunca duplicar datos contables fuera de Alegra

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>

---

*Phase: 01-contador-core*
*Context gathered: 2026-03-24*
