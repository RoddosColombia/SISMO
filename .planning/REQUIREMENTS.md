# Requirements: SISMO

**Defined:** 2026-03-24
**Core Value:** Contabilidad automatizada sin intervencion humana + visibilidad financiera en tiempo real + orquestacion confiable de agentes via bus de eventos

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Contador Agent (Accounting Automation)

- [ ] **CONT-00**: Mandato estrategico — cobertura total de flujos contables RODDOS hacia Alegra: toda operacion de ingresos, egresos, movimientos bancarios y analisis definida en Flujos_contables_Roddos.svg debe tener un path automatizado hacia Alegra a traves del Agente Contador. Criterio de exito: los 32 flujos del SVG tienen estado Funcional. Alegra es el libro legal; SISMO es el cerebro operativo.
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

### Agente de Ventas y CRM

- [ ] **SALES-01a**: Agente Vendedor Motos WhatsApp — responde consultas sobre motos nuevas disponibles, precios, planes de credito P39S/P52S/P78S y contado. Califica al prospecto con preguntas clave (presupuesto, uso, zona). Escala a humano cuando hay intencion de compra confirmada. Canal: Mercately.
- [ ] **SALES-01b**: Agente Vendedor Repuestos WhatsApp — venta consultiva de repuestos multimarca. Identifica la moto del cliente (modelo, ano), recomienda el repuesto correcto, verifica disponibilidad en inventario, cotiza y cierra. Flujo mas largo que motos — requiere multiples turnos de conversacion. Canal: Mercately.
- [ ] **SALES-02**: CRM unificado — toda interaccion de clientes (WhatsApp motos, WhatsApp repuestos, web) llega a coleccion crm_clientes en MongoDB con origen y tipo de interes. Pipeline con estados: prospecto -> calificado -> en proceso -> cerrado. Los dos agentes de venta alimentan el mismo CRM.
- [ ] **SALES-03**: Pagina web RODDOS integrada a SISMO — catalogo de motos disponibles (inventario_motos en tiempo real), catalogo de repuestos, formulario de solicitud de credito, boton WhatsApp. Los leads entran directamente al CRM.
- [ ] **SALES-04**: Motor de Score crediticio — calificacion automatica para otorgamiento de credito basada en: historial de pagos en SISMO, comportamiento DPD, consulta Datacredito/Experian (futuro), y reglas de negocio RODDOS. Output: score A+ a E + recomendacion aprobar/rechazar/condicionar.

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
| Portal de cliente web dedicado | La web es canal de captacion integrado a SISMO, no un portal de autoservicio separado |
| Facturacion electronica DIAN produccion | Bloqueado por certificado externo — diferido a v2 |
| Cobranza autonoma sin supervision | Riesgo regulatorio (Ley 1480) — requiere suppression logic primero |
| Machine Learning para scoring | 34 motos no justifica ML — scoring basado en reglas/estadistica |

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| CONT-00 | Phase 1 | Pending |
| CONT-01 | Phase 1 | Pending |
| CONT-02 | Phase 1 | Pending |
| CONT-03 | Phase 1 | Pending |
| CONT-04 | Phase 1 | Pending |
| CONT-05 | Phase 1 | Pending |
| CONT-06 | Phase 2 | Pending |
| CONT-07 | Phase 2 | Pending |
| CONT-08 | Phase 2 | Pending |
| ORQU-05 | Phase 2 | Pending |
| ORQU-06 | Phase 2 | Pending |
| ORQU-01 | Phase 3 | Pending |
| ORQU-02 | Phase 3 | Pending |
| ORQU-03 | Phase 3 | Pending |
| ORQU-04 | Phase 3 | Pending |
| LOAN-01 | Phase 4 | Pending |
| LOAN-06 | Phase 4 | Pending |
| LOAN-02 | Phase 4 | Pending |
| LOAN-03 | Phase 4 | Pending |
| LOAN-04 | Phase 4 | Pending |
| LOAN-05 | Phase 4 | Pending |
| WA360-01 | Phase 5 | Pending |
| WA360-02 | Phase 5 | Pending |
| WA360-03 | Phase 5 | Pending |
| WA360-04 | Phase 5 | Pending |
| WA360-05 | Phase 5 | Pending |
| SALES-01a | Phase 5 | Pending |
| SALES-01b | Phase 5 | Pending |
| SALES-02 | Phase 5 | Pending |
| SALES-03 | Phase 5 | Pending |
| SALES-04 | Phase 4 | Pending |
| INFRA-01 | Phase 6 | Pending |
| INFRA-02 | Phase 6 | Pending |
| INFRA-03 | Phase 6 | Pending |
| INFRA-04 | Phase 6 | Pending |
| INFRA-05 | Phase 6 | Pending |
| INFRA-06 | Phase 6 | Pending |

**Coverage:**
- v1 requirements: 37 total
- Mapped to phases: 37
- Unmapped: 0

---
*Requirements defined: 2026-03-24*
*Last updated: 2026-03-24 — added SALES-01a/01b/02/03/04 (Agente de Ventas y CRM)*
