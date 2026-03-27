# Requirements: SISMO — Milestone v2.0 BUILD 24

**Defined:** 2026-03-26
**Core Value:** Contabilidad automatizada sin intervencion humana + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos

## v2.0 Requirements — BUILD 24: Cimientos Definitivos

### Models & Contracts (MOD)

- [ ] **MOD-01**: RoddosEvent Pydantic model valida schema de todos los eventos del bus con 13 campos obligatorios
- [ ] **MOD-02**: DLQEvent model para dead-letter queue con retry_count y next_retry
- [ ] **MOD-03**: EVENT_TYPES catalogo Literal con 28 tipos de eventos validos
- [ ] **MOD-04**: WRITE_PERMISSIONS dict define colecciones y endpoints Alegra por agente en codigo Python
- [ ] **MOD-05**: validate_write_permission() bloquea escrituras no autorizadas con PermissionError
- [ ] **MOD-06**: validate_alegra_permission() bloquea llamadas HTTP no autorizadas a Alegra

### Bus de Eventos (BUS)

- [ ] **BUS-01**: EventBusService.emit() publica eventos con estado='processed' (nunca 'pending')
- [ ] **BUS-02**: emit() es idempotente: mismo event_id no genera duplicados (DuplicateKeyError silencioso)
- [ ] **BUS-03**: Fallos del bus van a DLQ, nunca bloquean la operacion principal
- [ ] **BUS-04**: retry_dlq() reintenta eventos fallidos cada 5 minutos con backoff exponencial
- [ ] **BUS-05**: get_bus_health() retorna metricas del bus (dlq_pending, events_last_hour, status)
- [ ] **BUS-06**: event_bus.py eliminado del repositorio, emit_state_change() eliminado de shared_state.py
- [ ] **BUS-07**: Todos los callers migrados a bus.emit() (routers/ventas, cartera, loanbook, nomina, cfo, conciliacion)
- [ ] **BUS-08**: post_action_sync.py migrado a usar bus.emit() + invalidate_cfo_cache()

### MongoDB Completo (MDB)

- [ ] **MDB-01**: init_mongodb_sismo.py reescrito, idempotente, crea 30+ colecciones con indices y schema validation
- [ ] **MDB-02**: roddos_events tiene indice unico en event_id + compuesto (event_type, timestamp_utc) + TTL 90 dias
- [ ] **MDB-03**: loanbook tiene indices ESR (estado+dpd+score, morosos partial, cola_cobranza partial, chasis unique)
- [ ] **MDB-04**: catalogo_planes sembrado con cuotas reales + multiplicadores (Semanal x1.0, Quincenal x2.2, Mensual x4.4)
- [ ] **MDB-05**: plan_cuentas_roddos sembrado con 28 IDs reales, ID 5495 eliminado, fallback 5493
- [ ] **MDB-06**: sismo_knowledge sembrado con 10 reglas criticas de negocio (mora, retenciones, autoretenedor, etc.)
- [ ] **MDB-07**: portfolio_summaries coleccion creada para snapshots diarios de cartera
- [ ] **MDB-08**: financial_reports coleccion creada para P&L mensuales pre-calculados
- [ ] **MDB-09**: roddos_events_dlq coleccion creada con indices para retry

### Agentes & Router (AGT)

- [x] **AGT-01**: SYSTEM_PROMPTS dict con 4 agentes diferenciados (Contador, CFO, RADAR, Loanbook)
- [x] **AGT-02**: Router con INTENT_THRESHOLD 0.7 — confianza < 0.7 pregunta al usuario
- [x] **AGT-03**: Prompt caching activado en system prompts (cache_control ephemeral)
- [x] **AGT-04**: RAG desde sismo_knowledge en build_agent_prompt() para todos los agentes

### Scheduler & Pipeline (SCH)

- [x] **SCH-01**: compute_portfolio_summary() ejecuta a las 11:30 PM y persiste en portfolio_summaries
- [x] **SCH-02**: _compute_financial_report_mensual() genera P&L el dia 1 de cada mes
- [x] **SCH-03**: dlq_retry_job registrado en scheduler cada 5 minutos
- [x] **SCH-04**: CFO lee portfolio_summaries antes que Alegra (get_portfolio_data_for_cfo())

### GitHub CI/CD (GIT)

- [ ] **GIT-01**: ci.yml expandido con pytest, anti-emergent check, anti-pending-status check
- [ ] **GIT-02**: Smoke test job en CI verifica /api/health/smoke (status, collections, bus)
- [ ] **GIT-03**: dependabot.yml creado para pip y npm
- [x] **GIT-04**: /api/health/smoke endpoint mejorado con checks de colecciones, bus, indices, catalogo
- [x] **GIT-05**: README.md actualizado a BUILD 24 (eliminar referencias Emergent y BUILD 18)
- [x] **GIT-06**: CLAUDE.md actualizado con protocolo nuevo bus, worktrees, errores documentados

### Tests (TST)

- [ ] **TST-01**: test_event_bus.py — 11 tests (emit, idempotencia, DLQ, health, no imports viejos)
- [ ] **TST-02**: test_permissions.py — 8 tests (write permissions, alegra permissions por agente)
- [ ] **TST-03**: test_mongodb_init.py — 13 tests (idempotencia, indices, datos sembrados)
- [x] **TST-04**: test_agent_router.py — 7 tests (routing correcto, clarificacion, system prompts)
- [x] **TST-05**: test_smoke_build24.py — 6 tests (health endpoint, colecciones, bus)
- [x] **TST-06**: test_usage_integration.py — 15 tests (portfolio summary, RAG, eventos end-to-end)

## Future Requirements (deferred)

- Atlas M10 con Change Streams (mayo 2026)
- Vector search para sismo_knowledge con voyage-finance-2 (BUILD 27)
- Branch protection rules en GitHub
- Docker Compose + infraestructura propia (Soberania Digital)
- Refactoring de ai_chat.py (decomposicion en modulos)

## Out of Scope

- Migracion de hosting (Render se mantiene para este milestone)
- Frontend changes (BUILD 24 es 100% backend + CI/CD)
- WhatsApp/Mercately changes
- DIAN facturacion electronica

## Traceability

| Requirement | Phase | Plan | Status |
|-------------|-------|------|--------|
| MOD-01 | 1 | TBD | Pending |
| MOD-02 | 1 | TBD | Pending |
| MOD-03 | 1 | TBD | Pending |
| MOD-04 | 1 | TBD | Pending |
| MOD-05 | 1 | TBD | Pending |
| MOD-06 | 1 | TBD | Pending |
| BUS-01 | 2 | TBD | Pending |
| BUS-02 | 2 | TBD | Pending |
| BUS-03 | 2 | TBD | Pending |
| BUS-04 | 2 | TBD | Pending |
| BUS-05 | 2 | TBD | Pending |
| BUS-06 | 2 | TBD | Pending |
| BUS-07 | 2 | TBD | Pending |
| BUS-08 | 2 | TBD | Pending |
| MDB-01 | 3 | TBD | Pending |
| MDB-02 | 3 | TBD | Pending |
| MDB-03 | 3 | TBD | Pending |
| MDB-04 | 3 | TBD | Pending |
| MDB-05 | 3 | TBD | Pending |
| MDB-06 | 3 | TBD | Pending |
| MDB-07 | 3 | TBD | Pending |
| MDB-08 | 3 | TBD | Pending |
| MDB-09 | 3 | TBD | Pending |
| AGT-01 | 4 | TBD | Pending |
| AGT-02 | 4 | TBD | Pending |
| AGT-03 | 4 | TBD | Pending |
| AGT-04 | 4 | TBD | Pending |
| SCH-01 | 4 | TBD | Pending |
| SCH-02 | 4 | TBD | Pending |
| SCH-03 | 4 | TBD | Pending |
| SCH-04 | 4 | TBD | Pending |
| GIT-01 | 5 | TBD | Pending |
| GIT-02 | 5 | TBD | Pending |
| GIT-03 | 5 | TBD | Pending |
| GIT-04 | 5 | TBD | Pending |
| GIT-05 | 5 | TBD | Pending |
| GIT-06 | 5 | TBD | Pending |
| TST-01 | 2 | TBD | Pending |
| TST-02 | 1 | TBD | Pending |
| TST-03 | 3 | TBD | Pending |
| TST-04 | 4 | TBD | Pending |
| TST-05 | 5 | TBD | Pending |
| TST-06 | 4 | TBD | Pending |
