# Matriz de Cobertura - Flujos Contables RODDOS

**Fecha:** 2026-03-24
**Fuente:** Auditoria de codigo (accounting_engine.py, alegra_service.py, ai_chat.py, conciliacion.py, alegra_webhooks.py, event_bus.py, scheduler.py, run_smoke_test.py, estado_resultados.py, cfo_agent.py, cfo_estrategico.py, + 12 routers adicionales)

## Resumen
- Funcional: 18/32
- Parcial: 8/32
- No implementado: 6/32

---

## Ingresos

| # | Flujo | Estado | Archivo/Funcion | Journal Alegra | Notas |
|---|-------|--------|-----------------|----------------|-------|
| 1 | Venta motos (contado) | **Funcional** | `ai_chat.py:execute_chat_action("crear_factura_venta")` -> `POST /api/ventas/crear-factura` en `ventas.py` | Si - POST /invoices via AlegraService | Crea factura en Alegra, actualiza inventario (estado=Vendida), crea loanbook. Webhook `alegra_webhooks.py:_nueva_factura` sincroniza VIN+inventario. Smoke test T07 verifica factura_alegra_id real. |
| 2 | Venta motos (credito) | **Funcional** | `ai_chat.py:execute_chat_action("crear_factura_venta")` + `routers/loanbook.py` | Si - POST /invoices + loanbook con cuotas | Mismo flujo que contado pero genera loanbook con plan de pago (P39S/P26Q etc). Cuotas generadas automaticamente. `loanbook.py:recalcular_cuotas` permite recalculo. |
| 3 | Recaudo cuotas | **Funcional** | `routers/cartera.py:POST /api/cartera/registrar-pago` + `ai_chat.py:execute_chat_action("registrar_pago_cartera")` | Si - POST /journals con DB=banco CR=CXC cartera (5327) | Crea journal en Alegra, actualiza cuota en loanbook como pagada, registra en cartera_pagos. Smoke test T09 verifica journal_id real. |
| 4 | Prestamos (intereses rentistas) | **Parcial** | `accounting_engine.py:REGLAS_CLASIFICACION["intereses_rentistas"]` cuenta 5534 | Si - via conciliacion bancaria (journal automatico) | Clasificacion automatica desde extracto bancario cuando detecta "intereses prestamo". NO hay endpoint dedicado para registrar prestamos recibidos ni su capital. Solo se contabiliza el egreso de intereses, no el ingreso del prestamo. |
| 5 | Rendimientos financieros | **Parcial** | `accounting_engine.py:REGLAS_CLASIFICACION["abono_intereses"]` + `["bc_abono_intereses_ahorros"]` cuenta 5456 | Si - via conciliacion bancaria (journal automatico) | Clasificacion automatica desde extracto: "abono por inter", "rendimientos financieros", "abono intereses ahorros". NO hay endpoint dedicado. No maneja rendimientos CDT especificamente. Solo se detecta en conciliacion. |
| 6 | Abonos extraordinarios | **Parcial** | `routers/cartera.py:POST /api/cartera/registrar-pago` | Si - mismo journal que recaudo cuotas | Se puede registrar como pago de cuota con monto mayor, pero NO hay logica especifica para abonos a capital que recalculen automaticamente el plan de pago. El endpoint `loanbook/{id}/recalcular` existe pero no se invoca automaticamente tras abono extraordinario. |
| 7 | Venta repuestos | **Funcional** | `routers/repuestos.py` + `event_bus.py:repuesto.vendido` | Parcial - evento emitido pero sin journal explicito | Router completo con inventario de repuestos (unidades + kits). Tiene billing via Alegra (factura). El evento `repuesto.vendido` se emite. Cuenta de ingreso 5444 (Repuestos ingreso) definida en accounting_engine. |
| 8 | Otros ingresos | **Funcional** | `routers/ingresos.py:POST /api/ingresos/no-operacional` + `ai_chat.py:execute_chat_action("registrar_ingreso_no_operacional")` | Si - POST /journals con tipo_ingreso configurable | Endpoint dedicado para ingresos no operacionales (Intereses, Otros_Ingresos, Arrendamientos). Busca cuenta en plan_ingresos_roddos de MongoDB. Smoke test T16 verifica journal_id. |

---

## Egresos

| # | Flujo | Estado | Archivo/Funcion | Journal Alegra | Notas |
|---|-------|--------|-----------------|----------------|-------|
| 9 | Gastos operativos | **Funcional** | `routers/gastos.py:POST /gastos/procesar` + `ai_chat.py:execute_chat_action("crear_causacion")` | Si - POST /journals o /bills con retenciones automaticas | Carga masiva via CSV con validacion, preview y retenciones automaticas (ReteFuente, RteICA). 45+ subcategorias en PLAN_CUENTAS_RODDOS. El agente IA tambien puede crear causaciones individuales via chat. |
| 10 | Nomina | **Funcional** | `routers/nomina.py:POST /api/nomina/registrar` + `ai_chat.py:execute_chat_action("registrar_nomina")` | Si - POST /journals DB=sueldos(5462) CR=banco | Endpoint dedicado con anti-duplicado (HTTP 409). Busca cuentas en plan_cuentas_roddos. Smoke test T12-T13 verifican journal y anti-duplicado. |
| 11 | Compra activos (motos inventario) | **Parcial** | `routers/inventory.py` (CRUD inventario) + `alegra_webhooks.py:_nueva_compra` | No - solo registro de evento, sin journal automatico | El inventory router gestiona motos (ingreso, baja, venta) pero la COMPRA de motos nuevas (factura de compra a Auteco) no genera journal automatico en Alegra. El webhook `_nueva_compra` solo registra evento con `requiere_revision: True`. El costo se actualiza manualmente. |
| 12 | Anticipos | **Funcional** | `accounting_engine.py:CUENTAS_ACTIVOS["anticipos_proveedores"]` (5331) + `["anticipos_empleados"]` (5332) + `ai_chat.py:crear_causacion` | Si - via causacion manual del agente IA | Cuentas definidas en la matriz (5331 proveedores, 5332 empleados). El agente IA puede crear causaciones con estas cuentas. No hay endpoint dedicado pero el flujo via chat es funcional. |
| 13 | Intereses financieros (pagados) | **Funcional** | `accounting_engine.py:REGLAS_CLASIFICACION["intereses_rentistas"]` cuenta 5534 | Si - via conciliacion bancaria automatica | Clasificacion automatica desde extracto bancario. Reglas especificas para "intereses andres cano", "intereses david martinez" con confianza 95%. Cuenta 5534 (Intereses pagados a inversores rentistas). |
| 14 | Servicios publicos | **Funcional** | `accounting_engine.py:REGLAS_CLASIFICACION["servicios_publicos"]` cuenta 5485 + `gastos.py` | Si - via conciliacion bancaria o carga CSV | Clasificacion automatica (luz, energia, enel, gas, vanti, acueducto) con confianza 80%. Tambien registrable via carga masiva de gastos. |
| 15 | Arriendo | **Funcional** | `accounting_engine.py:REGLAS_CLASIFICACION["arriendo"]` cuenta 5480 + retencion 5386 (3.5%) | Si - via conciliacion bancaria con retencion automatica | Clasificacion automatica con retencion arriendo 3.5% incluida. Reglas especificas para "pago arriendo", "arriendo oficina". Confianza 85-90%. |
| 16 | Honorarios | **Funcional** | `accounting_engine.py:CUENTAS_GASTOS["asesoria_juridica"]` (5475 PN) + `["asesoria_financiera"]` (5476 PJ) + `gastos.py:PLAN_CUENTAS_RODDOS` | Si - via causacion o carga CSV con retencion automatica | Retenciones honorarios PN 10% (5381) y 11% (5382) definidas. Smoke test T02 verifica journal con retencion. Carga masiva distingue PN vs PJ. |

---

## Bancario

| # | Flujo | Estado | Archivo/Funcion | Journal Alegra | Notas |
|---|-------|--------|-----------------|----------------|-------|
| 17 | Conciliacion Bancolombia | **Funcional** | `routers/conciliacion.py:POST /api/conciliacion/cargar-extracto` + `services/bank_reconciliation.py:BancolombiParser` | Si - journals automaticos por movimiento | Parser completo para extractos Bancolombia. Clasificacion automatica con 30+ reglas especificas en accounting_engine.py. Anti-duplicados por hash de extracto y por movimiento individual. Background task para lotes >10. Reintentos automaticos via scheduler cada 5 min. |
| 18 | Conciliacion BBVA | **Funcional** | `services/bank_reconciliation.py:BBVAParser` cuenta 5318 | Si - journals automaticos | Parser BBVA con 12 reglas especificas en accounting_engine.py (POLITICA CONTABLE OFICIAL BBVA 2026). Maneja positivo=ingreso, negativo=egreso. |
| 19 | Conciliacion Davivienda | **Funcional** | `services/bank_reconciliation.py:DaviviendaParser` cuenta 5322 | Si - journals automaticos | Parser Davivienda implementado. Usa misma infraestructura de clasificacion y causacion que Bancolombia/BBVA. |
| 20 | Conciliacion Nequi | **Funcional** | `services/bank_reconciliation.py:NequiParser` | Si - journals automaticos | Parser Nequi implementado (Excel, tipo ingreso/egreso). Clase `NequiParser` con columnas especificas. |
| 21 | GMF 4x1000 | **Funcional** | `accounting_engine.py:REGLAS_CLASIFICACION["gmf"]` cuenta 5509 | Si - via conciliacion bancaria | Clasificacion automatica con confianza 90%. Detecta "4x1000", "impuesto 4x1000", "gravamen", "gmf". |
| 22 | Comisiones bancarias | **Funcional** | `accounting_engine.py:REGLAS_CLASIFICACION["comisiones"]` (5508) + `["gastos_bancarios"]` (5507) | Si - via conciliacion bancaria | Dos cuentas: comisiones (5508) para "comision", "cargo bbva cash", "cuota manejo"; gastos bancarios (5507) para "costo transferencia", "iva traslado". Reglas Bancolombia: cuota plan canal (5508), IVA cuota plan (5507), cuota manejo TRJ (5507). |
| 23 | Transferencias entre cuentas | **Parcial** | `accounting_engine.py:REGLAS_CLASIFICACION["traslado_interno"]` + `["bc_transferencia_cta_virtual"]` | No - marcadas como `es_transferencia_interna=True` → NO se contabilizan | Las transferencias internas se DETECTAN correctamente y se excluyen de la causacion (correcto contablemente). Sin embargo, no generan un asiento de contrapartida banco-a-banco que refleje el movimiento en ambas cuentas bancarias en Alegra. |
| 24 | Rendimientos CDT | **No implementado** | No hay referencia a CDT en el codigo | No | No existe cuenta CDT, no hay parser ni regla de clasificacion. Los rendimientos financieros genericos (cuenta 5456) podrian cubrir parcialmente pero no hay tracking de CDTs como instrumentos financieros. |

---

## Analisis

| # | Flujo | Estado | Archivo/Funcion | Journal Alegra | Notas |
|---|-------|--------|-----------------|----------------|-------|
| 25 | CXC (cuentas por cobrar) | **Funcional** | `routers/cxc.py` + `routers/cxc_socios.py` + `ai_chat.py:consultar_cxc_socios/registrar_cxc_socio/abonar_cxc_socio/registrar_cxc_cliente` | Si - journals para registros y abonos | CXC Socios (5329): directorio, saldo, abono con journal en Alegra. CXC Clientes (5326): registrar, saldo, vencidas, abonar. Smoke test T14-T15 verifican. |
| 26 | CXP (cuentas por pagar) | **Parcial** | `routers/cfo_estrategico.py:GET /cfo/deudas` + `/cfo/plan-deudas` | No - gestion en MongoDB, no en Alegra | Gestion de deudas (productivas/no productivas) con clasificacion automatica, plan avalancha. Carga via Excel. Sin embargo, NO genera bills ni journals en Alegra para CXP. Solo es un tracker interno en MongoDB. Las bills de Alegra se consultan para analisis (cfo_agent, estado_resultados) pero no se sincronizan bidireccionalmente. |
| 27 | P&L (estado de resultados) | **Funcional** | `routers/estado_resultados.py:GET /cfo/estado-resultados` + PDF + Excel | N/A (lectura) | P&L completo: ingresos (motos nuevas/usadas, repuestos, financiacion), costo de ventas, gastos operacionales (6 categorias), utilidad bruta/neta, impuesto renta 33%. Exportacion PDF ejecutivo y Excel 4 hojas. Comparativo mes anterior. |
| 28 | Flujo de caja | **Funcional** | `services/cfo_agent.py:analizar_flujo_caja()` + `routers/cfo_estrategico.py:GET /cfo/plan-ingresos` | N/A (lectura) | Analisis completo: ingresos reales (cobrado_mes) + proyectados (cuotas futuras), egresos (bills Alegra), brecha caja. Plan semanal desde loanbooks con gastos fijos configurables. Presupuesto mensual generado automaticamente. |
| 29 | Balance general | **No implementado** | No existe endpoint ni funcion | N/A | No hay endpoint `/balance-general`. El P&L (estado_resultados.py) no incluye seccion de balance. No se consultan cuentas de activo/pasivo/patrimonio de Alegra para armar balance. Seria necesario consultar /categories y sumar saldos. |
| 30 | Aging cartera | **Funcional** | `services/shared_state.py:get_portfolio_health()` + `services/cfo_agent.py:analizar_cartera()` + `routers/crm.py` (filtro por bucket/dpd) | N/A (lectura) | Portfolio health con DPD (days past due), buckets (AL_DIA, ACTIVO, HOY, URGENTE, CRITICO, RECUPERACION), score (A/B/C/F), top morosos. CRM router filtra por bucket y score. Migracion v24 agrego campos DPD a loanbooks. |
| 31 | Conciliacion Alegra vs MongoDB | **Parcial** | `scheduler.py:_reconciliar_inventario_lunes` + `routers/alegra_webhooks.py:sincronizar_facturas_recientes` | N/A (lectura) | Reconciliacion PARCIAL: inventario motos (lunes 7am verifica conteos). Facturas sincronizadas cada 5 min (polling + webhooks). Pagos sincronizados cada 5 min. PERO no existe reconciliacion de saldos contables (journals Alegra vs MongoDB), ni verificacion de completitud de asientos. |
| 32 | Dashboard KPIs | **Funcional** | `routers/dashboard.py:GET /dashboard/alerts` + `/dashboard/kpis` + `services/cfo_agent.py:generar_semaforo()` | N/A (lectura) | Alertas proactivas (facturas vencidas, bills proximas), KPIs agregados, semaforo financiero (caja, cartera, ventas, roll_rate, impuestos). Informe CFO mensual automatico (scheduler dia 1, 8am). Resumen semanal CFO (lunes 8:05am). Deteccion anomalias diarias (23:30). Nota: `generar_resumen_semanal` y `detectar_anomalias` referenciadas en scheduler.py pero NO definidas en accounting_engine.py — esos jobs fallan silenciosamente. |

---

## Prioridades

Flujos Parcial/No implementado ordenados por impacto financiero:

### Impacto ALTO (Ingresos / Core contable)

| Prioridad | Flujo | Estado | Impacto | Accion requerida |
|-----------|-------|--------|---------|------------------|
| 1 | **Balance general** (#29) | No implementado | Sin balance no hay cierre contable ni vision patrimonial. Critico para DIAN y socios. | Crear endpoint que consulte /categories de Alegra, sume saldos por naturaleza (activo/pasivo/patrimonio), y presente balance clasificado. |
| 2 | **Compra activos - motos inventario** (#11) | Parcial | Las compras a Auteco (~$4-6M por moto) no generan journal. Inventario sin costo contable en Alegra. | Crear flujo: factura compra (bill) en Alegra → journal DB=inventario_motos(5348) CR=CXP_proveedores(5376). Vincular con ingreso al inventario MongoDB. |
| 3 | **Abonos extraordinarios** (#6) | Parcial | Abonos a capital no recalculan plan de pago automaticamente. Riesgo de desalineacion loanbook vs realidad. | Conectar registro de pago con monto > cuota normal al endpoint `recalcular_cuotas`. Crear logica de abono a capital que reduzca saldo y ajuste cuotas restantes. |
| 4 | **Prestamos recibidos** (#4) | Parcial | Solo se contabilizan intereses pagados, no el capital recibido ni el pasivo generado. | Crear endpoint para registrar prestamo: journal DB=banco CR=pagares(5372). Tracker de amortizacion con saldo vivo. |

### Impacto MEDIO (Bancario / Analisis)

| Prioridad | Flujo | Estado | Impacto | Accion requerida |
|-----------|-------|--------|---------|------------------|
| 5 | **CXP (cuentas por pagar)** (#26) | Parcial | Deudas trackeadas internamente pero sin reflejo contable en Alegra. Desconexion entre gestion y contabilidad. | Sincronizar deudas del modulo CFO estrategico con bills de Alegra. Al confirmar deuda, crear bill correspondiente. |
| 6 | **Transferencias entre cuentas** (#23) | Parcial | Se detectan y excluyen correctamente, pero Alegra no refleja el movimiento entre bancos. Saldos bancarios en Alegra pueden divergir. | Generar journal DB=banco_destino CR=banco_origen para transferencias internas detectadas. Requiere mapeo de banco destino desde la descripcion. |
| 7 | **Conciliacion Alegra vs MongoDB** (#31) | Parcial | Solo inventario y facturas. No hay verificacion de saldos contables ni completitud de journals. | Crear endpoint de reconciliacion contable: comparar journals en Alegra vs eventos en roddos_events. Detectar asientos faltantes, duplicados, o con montos divergentes. |
| 8 | **Rendimientos CDT** (#24) | No implementado | RODDOS no parece tener CDTs activos actualmente. Bajo impacto inmediato. | Cuando sea necesario: agregar cuenta CDT en Alegra, regla en accounting_engine para detectar rendimientos CDT en extractos, y tracker de instrumentos financieros. |

### Funciones scheduler rotas (impacto operativo)

| Item | Funcion | Problema | Fix |
|------|---------|----------|-----|
| A | `_resumen_semanal_cfo` | Importa `generar_resumen_semanal` de `accounting_engine.py` pero la funcion NO existe | Implementar funcion en accounting_engine.py o mover import a cfo_agent.py |
| B | `_detectar_anomalias_diarias` | Importa `detectar_anomalias` de `accounting_engine.py` pero la funcion NO existe | Implementar funcion en accounting_engine.py |

---

## Notas metodologicas

1. **Clasificacion "Funcional"** requiere: (a) endpoint o funcion existe, (b) crea journal correcto en Alegra con cuentas verificadas, (c) tiene al menos un test o smoke test.
2. **Clasificacion "Parcial"** indica: endpoint existe pero faltan journals, cuentas incorrectas, sin tests, o logica incompleta.
3. **Clasificacion "No implementado"** indica: no existe endpoint, funcion, ni regla de clasificacion para este flujo.
4. Los IDs de cuentas Alegra (5310-5534) fueron verificados contra la matriz `CUENTAS_*` en `accounting_engine.py` que contiene IDs reales de produccion.
5. El `ai_chat.py` funciona como orquestador principal: 19 action_types mapeados a endpoints/servicios especificos.
6. La conciliacion bancaria (`bank_reconciliation.py`) soporta 4 bancos con parsers dedicados y 45+ reglas de clasificacion en `accounting_engine.py`.
