# Requirements: SISMO

**Defined:** 2026-03-24
**Core Value:** Contabilidad automatizada sin intervencion humana + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Contador Agent (Accounting Automation)

- [ ] **CONT-01**: Fix proveedor extraction en bank_reconciliation.py para activar 30+ reglas de clasificacion
- [ ] **CONT-02**: Decomposicion de ai_chat.py (5,217 lineas) en modulos: contador_agent.py, context_builder.py, file_parser.py, prompt_templates.py
- [ ] **CONT-03**: Implementar idempotency keys para todas las operaciones Alegra (contactos, facturas, pagos, recibos)
- [ ] **CONT-04**: Dead-letter queue para webhooks Alegra fallidos con retry exponencial y alertas
- [ ] **CONT-05**: Cache invalidation event-driven (invalidar inmediatamente al emitir evento, TTL como fallback)
- [ ] **CONT-06**: Smoke test 20/20 ciclo completo contable con IDs reales de Alegra: crear contacto, crear factura, registrar pago, emitir recibo de caja, conciliar movimiento bancario
- [ ] **CONT-07**: Clasificacion contable con confianza >= 85% para transacciones con proveedor identificado
- [ ] **CONT-08**: Reconciliacion bancaria batch optimizada (asyncio.gather para Alegra API, $in para MongoDB)

### Orquestacion de Agentes (Agent Orchestration)

- [ ] **ORQU-01**: Bus de eventos tipado con schemas validados por evento (pago.cuota.registrado, factura.causada, etc.)
- [ ] **ORQU-02**: Dashboard de monitoreo del bus: eventos procesados, fallidos, pendientes, latencia por tipo
- [ ] **ORQU-03**: Flujos de trabajo documentados: cada operacion backoffice tiene un flujo definido con agentes responsables
- [ ] **ORQU-04**: Trazabilidad end-to-end: desde accion del usuario hasta reflejo en Alegra, cada paso registrado en roddos_events
- [ ] **ORQU-05**: System prompts diferenciados por agente: cada agente (Contador, CFO, RADAR, Loanbook) tiene su propio bloque de identidad como system message con contexto, herramientas y restricciones especificas
- [ ] **ORQU-06**: Router con confidence threshold: si confidence < 0.7, preguntar al usuario en vez de despachar al agente equivocado; routing explicito con justificacion

### WhatsApp 360 (Customer Ecosystem Hub)

- [ ] **WA360-01**: WhatsApp como canal central de interaccion 360: saldo, pagos, soporte, gestiones de cobranza
- [ ] **WA360-02**: Deteccion de intenciones mejorada: saldo, pago realizado, dificultad de pago, consulta de repuestos, estado de moto
- [ ] **WA360-03**: Respuesta automatica contextual: el sistema responde con datos reales del loanbook del cliente (saldo, proxima cuota, historial)
- [ ] **WA360-04**: Confirmacion de pagos via WhatsApp: cliente reporta pago -> sistema verifica en extracto bancario -> confirma o escala
- [ ] **WA360-05**: Historial de conversaciones por cliente vinculado al CRM (timeline 360)

### Loanbook Intelligence (Portfolio Analytics)

- [ ] **LOAN-01**: Loanbook FSM con concurrency guards y transiciones validadas (pendiente_entrega -> activo -> cancelado)
- [ ] **LOAN-06**: Regla del Miercoles como constraint inviolable: toda logica de cuotas, fechas de corte y generacion de planes de pago respeta la Regla del Miercoles sin excepcion
- [ ] **LOAN-02**: Metricas PAR30/PAR60/PAR90 calculadas diariamente con datos reales de cuotas
- [ ] **LOAN-03**: Scoring de probabilidad de default por cliente basado en historial de pagos y DPD
- [ ] **LOAN-04**: Alertas predictivas de morosidad: detectar clientes en riesgo antes de que caigan en mora
- [ ] **LOAN-05**: Collection queue priorizada: ordenar cobranza por riesgo, monto, y dias de mora

### Infraestructura y Soberania Digital

- [ ] **INFRA-01**: Docker Compose para toda la aplicacion (frontend, backend, MongoDB)
- [ ] **INFRA-02**: CI/CD pipeline automatizado (build, test, deploy)
- [ ] **INFRA-03**: MongoDB Atlas -> Community migration path documentado y probado
- [ ] **INFRA-04**: Nginx como reverse proxy con SSL/TLS (Certbot)
- [ ] **INFRA-05**: Secrets management encriptado (no mas .env en texto plano)
- [ ] **INFRA-06**: JWT rotation implementado (short-lived tokens + refresh tokens)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### RADAR Collection Automation

- **RADAR-01**: Cobranza autonoma por WhatsApp con suppression windows (respetar Ley 1480)
- **RADAR-02**: Acuerdos de pago negociados via WhatsApp con aprobacion humana
- **RADAR-03**: Escalamiento automatico a operador humano cuando IA no puede resolver

### DIAN Integration

- **DIAN-01**: Auto-causacion de facturas electronicas DIAN en produccion (requiere certificado)
- **DIAN-02**: Sincronizacion automatica de facturas recibidas desde portal DIAN

### Advanced Analytics

- **ANLY-01**: Dashboard de rentabilidad por moto/cliente
- **ANLY-02**: Proyeccion de flujo de caja con escenarios (optimista, base, pesimista)
- **ANLY-03**: Reportes automaticos para inversionistas (PDF)

### Monitoring & Observability

- **OBSV-01**: Prometheus + Grafana stack completo
- **OBSV-02**: Self-hosted error tracking (GlitchTip)
- **OBSV-03**: Self-hosted LLM fallback (solo despues de smoke test 20/20 establecido)

## Out of Scope

| Feature | Reason |
|---------|--------|
| App movil nativa | Web-first, mobile responsive suficiente para equipo de 2-5 |
| Multitenancy | SISMO es exclusivo para RODDOS S.A.S. |
| Integracion bancaria directa | Reconciliacion via CSV/Excel es suficiente por ahora |
| Portal de cliente web | WhatsApp es el canal del cliente, no necesita portal web |
| Facturacion electronica DIAN produccion | Bloqueado por certificado externo — diferido a v2 |
| Cobranza autonoma sin supervision | Riesgo regulatorio (Ley 1480) — requiere suppression logic primero |
| Machine Learning para scoring | 34 motos no justifica ML — scoring basado en reglas/estadistica |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONT-01 | TBD | Pending |
| CONT-02 | TBD | Pending |
| CONT-03 | TBD | Pending |
| CONT-04 | TBD | Pending |
| CONT-05 | TBD | Pending |
| CONT-06 | TBD | Pending |
| CONT-07 | TBD | Pending |
| CONT-08 | TBD | Pending |
| ORQU-01 | TBD | Pending |
| ORQU-02 | TBD | Pending |
| ORQU-03 | TBD | Pending |
| ORQU-04 | TBD | Pending |
| WA360-01 | TBD | Pending |
| WA360-02 | TBD | Pending |
| WA360-03 | TBD | Pending |
| WA360-04 | TBD | Pending |
| WA360-05 | TBD | Pending |
| LOAN-01 | TBD | Pending |
| LOAN-02 | TBD | Pending |
| LOAN-03 | TBD | Pending |
| LOAN-04 | TBD | Pending |
| LOAN-05 | TBD | Pending |
| INFRA-01 | TBD | Pending |
| INFRA-02 | TBD | Pending |
| INFRA-03 | TBD | Pending |
| INFRA-04 | TBD | Pending |
| INFRA-05 | TBD | Pending |
| ORQU-05 | TBD | Pending |
| ORQU-06 | TBD | Pending |
| LOAN-06 | TBD | Pending |
| INFRA-06 | TBD | Pending |

**Coverage:**
- v1 requirements: 31 total
- Mapped to phases: 0
- Unmapped: 31

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 after initial definition*
