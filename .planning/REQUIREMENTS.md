# Requirements: SISMO v23.0 BUILD 23 — Agente Contador 8.5/10 + Alegra 100%

**Defined:** 2026-03-30
**Core Value:** Contabilidad automatizada sin intervencion humana — toda operacion financiera ejecutada correctamente en Alegra con verificacion HTTP 200

## v23.0 Requirements — BUILD 23

### Auditoria Alegra (AUDIT)

- [x] **AUDIT-01**: Auditar utils/alegra.py vs services/alegra_service.py — identificar cual es la fuente de verdad, documentar duplicacion y conflictos
- [x] **AUDIT-02**: Probar cada endpoint de Alegra con request real y documentar resultado: GET /invoices, GET /categories, GET /payments, POST /journals
- [x] **AUDIT-03**: Verificar que request_with_verify() usa la URL base correcta (`https://api.alegra.com/api/v1/`) en toda operacion de escritura
- [x] **AUDIT-04**: Auditar ACTION_MAP en ai_chat.py — listar acciones registradas, acciones faltantes, y acciones rotas
- [x] **AUDIT-05**: Generar reporte de auditoria: que funciona, que esta roto, que falta — base para todas las fases siguientes

### Consolidacion Capa Alegra (ALEGRA)

- [ ] **ALEGRA-01**: Consolidar utils/alegra.py y services/alegra_service.py en arquitectura clara con unica fuente de verdad
- [ ] **ALEGRA-02**: ALEGRA_BASE_URL como unica constante importada por todos los modulos que llaman a Alegra (`https://api.alegra.com/api/v1/`)
- [x] **ALEGRA-03**: request_with_verify() robusto: POST → verificar con GET → HTTP 200 obligatorio antes de reportar exito al usuario
- [ ] **ALEGRA-04**: Manejo de errores en espanol — nunca exponer stack traces ni mensajes crudos de la API al usuario
- [ ] **ALEGRA-05**: Test por cada endpoint confirmando respuesta correcta: GET /invoices, GET /categories, GET /payments, GET /journals, POST /journals
- [x] **ALEGRA-06**: Endpoints prohibidos (/journal-entries, /accounts) bloqueados — su uso genera error explicito antes de emitir la llamada HTTP

### ACTION_MAP Completo (ACTION)

- [ ] **ACTION-01**: Accion de lectura `consultar_facturas` registrada en ACTION_MAP: GET /invoices con filtros de fecha en formato yyyy-MM-dd
- [ ] **ACTION-02**: Accion de lectura `consultar_pagos` registrada en ACTION_MAP: GET /payments con filtro type in/out
- [ ] **ACTION-03**: Accion de lectura `consultar_journals` registrada en ACTION_MAP: GET /journals con filtros de fecha y descripcion
- [ ] **ACTION-04**: Accion de lectura `consultar_cartera` registrada en ACTION_MAP: lee MongoDB loanbook y cartera_pagos, no llama a Alegra
- [ ] **ACTION-05**: Accion de lectura `consultar_plan_cuentas` registrada en ACTION_MAP: GET /categories retorna plan de cuentas con IDs correctos

### Chat Transaccional Real (CHAT)

- [ ] **CHAT-01**: Usuario describe gasto en lenguaje natural → agente clasifica usando motor matricial de accounting_engine (no heuristica manual)
- [ ] **CHAT-02**: Agente calcula ReteFuente + ReteICA automaticamente segun tipo: Arrendamiento 3.5%, Servicios 4%, Honorarios persona natural 10% / persona juridica 11%, Compras 2.5% (base minima $1.344.573), ReteICA Bogota 0.414% en toda operacion
- [ ] **CHAT-03**: Agente propone asiento con cuentas reales de plan_cuentas_roddos, espera confirmacion explicita del usuario — maximo una pregunta por turno de interaccion
- [ ] **CHAT-04**: Tras confirmacion del usuario: POST /journals → GET verificacion → retorna ID real del journal en Alegra (nunca simula exito)
- [ ] **CHAT-05**: Casos especiales correctos: Auteco NIT 860024781 = autoretenedor (nunca aplicar ReteFuente), socios CC 80075452 / CC 80086601 = CXC socios (nunca gasto operativo)

### Facturacion Venta Motos (FACTURA)

- [ ] **FACTURA-01**: POST /invoices con formato de descripcion obligatorio: "[Modelo] [Color] - VIN:[x] / Motor:[x]"
- [ ] **FACTURA-02**: VIN y numero de motor son campos obligatorios — HTTP 400 si faltan, el sistema nunca crea una factura de moto sin ellos
- [ ] **FACTURA-03**: Al crear factura exitosa: moto marcada como Vendida en inventario_motos
- [ ] **FACTURA-04**: Al crear factura exitosa: loanbook creado en estado pendiente_entrega + evento factura.venta.creada publicado en bus de eventos

### Ingresos Cuotas Cartera (CARTERA)

- [ ] **CARTERA-01**: Pago de cuota registrado → POST /payments type:in → journal de ingreso en Alegra con cuenta correcta de plan_ingresos_roddos
- [ ] **CARTERA-02**: Anti-duplicados activo: antes de registrar, verificar que el mismo pago no existe ya en Alegra — nunca crear dos registros del mismo pago
- [ ] **CARTERA-03**: CFO puede consultar y verificar el ingreso registrado via portfolio_summaries — recaudo visible en reportes financieros

### Nomina Mensual (NOMINA)

- [ ] **NOMINA-01**: Registrar nomina mensual discriminada por empleado con los montos reales: Enero 2026 (Alexa $3.220.000, Luis $3.220.000, Liz $1.472.000), Febrero 2026 (Alexa $4.500.000, Liz $2.200.000)
- [ ] **NOMINA-02**: Anti-duplicados por mes + empleado: sistema verifica antes de registrar que el mismo empleado no tiene nomina del mismo mes ya en Alegra — intento de duplicado retorna error claro
- [ ] **NOMINA-03**: Journal discriminado por empleado en Alegra — un asiento por empleado por mes, no un journal consolidado del mes

### Smoke Test Final Alegra 100% (SMOKE)

- [ ] **SMOKE-01**: GET /invoices retorna facturas reales de RODDOS (HTTP 200, lista no vacia) en smoke test
- [ ] **SMOKE-02**: GET /categories retorna plan de cuentas con IDs correctos (ID 5493 presente, ID 5495 ausente)
- [ ] **SMOKE-03**: Chat end-to-end: "Pagamos arriendo $3.614.953" → journal en Alegra con ID real retornado
- [ ] **SMOKE-04**: Consulta end-to-end: "Muestrame las facturas de marzo" → lista facturas reales, no datos mock
- [ ] **SMOKE-05**: Venta moto con VIN real → factura en Alegra creada + inventario actualizado + loanbook en estado pendiente_entrega
- [ ] **SMOKE-06**: Pago cuota → journal ingreso en Alegra → CFO puede consultar el recaudo en reportes
- [ ] **SMOKE-07**: Nomina enero → registrada en Alegra → segundo intento del mismo mes bloqueado con error claro
- [ ] **SMOKE-08**: Alegra caido o sin conectividad → error en espanol devuelto al usuario, UI no rompe ni muestra stack trace
- [ ] **SMOKE-09**: ACTION_MAP: consultar_facturas, consultar_pagos, consultar_journals responden con datos reales
- [ ] **SMOKE-10**: Todos los greps del COMMIT PROTOCOL dan 0 resultados (app.alegra.com/api/r1, /journal-entries, estado.*pending)

---

## Future Requirements (deferred)

- Facturacion electronica DIAN en produccion (requiere certificado DIAN)
- Nomina con deducciones de seguridad social automaticas (solo valor bruto en BUILD 23)
- Refactoring de ai_chat.py (decomposicion en modulos — BUILD 25+)
- Integracion bancaria directa (reconciliacion via CSV/Excel es suficiente hoy)

## Out of Scope

- Multitenancy (SISMO exclusivo para RODDOS)
- App movil nativa (web-first, mobile responsive es suficiente)
- WhatsApp/Mercately changes (fuera de alcance BUILD 23)
- Frontend UI changes (BUILD 23 es 100% backend + integracion Alegra)

---

## Traceability

| Requirement | Phase | Status |
|-------------|-------|--------|
| AUDIT-01 | Phase 1 | Complete |
| AUDIT-02 | Phase 1 | Complete |
| AUDIT-03 | Phase 1 | Complete |
| AUDIT-04 | Phase 1 | Complete |
| AUDIT-05 | Phase 1 | Complete |
| ALEGRA-01 | Phase 2 | Pending |
| ALEGRA-02 | Phase 2 | Pending |
| ALEGRA-03 | Phase 2 | Complete |
| ALEGRA-04 | Phase 2 | Pending |
| ALEGRA-05 | Phase 2 | Pending |
| ALEGRA-06 | Phase 2 | Complete |
| ACTION-01 | Phase 3 | Pending |
| ACTION-02 | Phase 3 | Pending |
| ACTION-03 | Phase 3 | Pending |
| ACTION-04 | Phase 3 | Pending |
| ACTION-05 | Phase 3 | Pending |
| CHAT-01 | Phase 4 | Pending |
| CHAT-02 | Phase 4 | Pending |
| CHAT-03 | Phase 4 | Pending |
| CHAT-04 | Phase 4 | Pending |
| CHAT-05 | Phase 4 | Pending |
| FACTURA-01 | Phase 5 | Pending |
| FACTURA-02 | Phase 5 | Pending |
| FACTURA-03 | Phase 5 | Pending |
| FACTURA-04 | Phase 5 | Pending |
| CARTERA-01 | Phase 6 | Pending |
| CARTERA-02 | Phase 6 | Pending |
| CARTERA-03 | Phase 6 | Pending |
| NOMINA-01 | Phase 7 | Pending |
| NOMINA-02 | Phase 7 | Pending |
| NOMINA-03 | Phase 7 | Pending |
| SMOKE-01 | Phase 8 | Pending |
| SMOKE-02 | Phase 8 | Pending |
| SMOKE-03 | Phase 8 | Pending |
| SMOKE-04 | Phase 8 | Pending |
| SMOKE-05 | Phase 8 | Pending |
| SMOKE-06 | Phase 8 | Pending |
| SMOKE-07 | Phase 8 | Pending |
| SMOKE-08 | Phase 8 | Pending |
| SMOKE-09 | Phase 8 | Pending |
| SMOKE-10 | Phase 8 | Pending |
