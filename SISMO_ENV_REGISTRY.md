# SISMO — Registro Canónico de Rutas, Jobs y Variables
**Actualizado:** 5 abril 2026 — Auditoría completa, todos los 41 routers verificados desde código fuente
**Regla de uso:** Antes de crear cualquier ruta, job o variable, verificar aquí que no exista ya.

---

## 1. Variables de Entorno — Render (Producción)

| Variable | Header / Uso | Notas |
|---|---|---|
| `MONGO_URL` | Conexión MongoDB | `mongodb+srv://sismo_admin:...@sismo-prod.rzebxlv.mongodb.net` |
| `ALEGRA_EMAIL` | Auth Alegra | `contabilidad@roddos.com` |
| `ALEGRA_TOKEN` | Auth Alegra | Token Plan Pro — Basic Base64(email:token) |
| `ANTHROPIC_API_KEY` | Claude Sonnet API | Modelo: `claude-sonnet-4-20250514` |
| `N8N_API_KEY` | Auth n8n → SISMO | Header: `X-N8N-Key` |
| `GLOBAL66_WEBHOOK_SECRET` | Auth Global66 → SISMO | Header: `x-api-key` (NO HMAC) |
| `WEBHOOK_SECRET` | Auth webhook Alegra legacy | Header: `X-Alegra-Secret` |
| `CORS_ORIGINS` | Orígenes permitidos | Default: `*` |
| `APP_URL` | URL base backend | Para registro de webhooks Alegra |
| `DIAN_TOKEN` | Auth DIAN | Pendiente credenciales reales |
| `DIAN_AMBIENTE` | Entorno DIAN | `habilitacion` (default) |
| `DIAN_NIT` | NIT empresa DIAN | `9010126221` |

---

## 2. MongoDB — Configuración

| Parámetro | Valor | Error histórico a evitar |
|---|---|---|
| **Nombre DB** | `sismo` | NO usar `sismo-prod` — existe pero está vacía |
| **Variable de conexión** | `MONGO_URL` | NO usar `MONGODB_URI` ni `MONGO_URI` |

### 2.1 Colecciones activas

| Colección | Propósito | Escritura exclusiva |
|---|---|---|
| `loanbook` | Créditos — campo VIN: `chasis` (NO `vin`) | Agente Loanbook |
| `inventario_motos` | Motos TVS — campo VIN: `chasis` | Agente Loanbook |
| `cartera_pagos` | Pagos de cuotas registrados | Agente Contador |
| `plan_cuentas_roddos` | 28 entradas con IDs reales Alegra | Agente Contador |
| `plan_ingresos_roddos` | IDs Alegra para ingresos | Agente Contador |
| `cxc_socios` | CXC Andrés + Iván | Agente Contador |
| `cxc_clientes` | CXC clientes distintos a loanbooks | Agente Contador |
| `contabilidad_pendientes` | Backlog movimientos baja confianza | Sistema |
| `conciliacion_jobs` | Estado jobs background de extractos | Sistema |
| `conciliacion_extractos_procesados` | Anti-dup hash extracto completo | Sistema |
| `conciliacion_movimientos_procesados` | Anti-dup hash movimiento individual | Sistema |
| `conciliacion_reintentos` | Movimientos fallidos — reintento 5 min | Sistema |
| `global66_eventos_recibidos` | Registro eventos Global66 (BUILD 25) | Sistema |
| `ingresos_no_operacionales` | Ingresos no operacionales registrados | Sistema |
| `roddos_events` | Bus de eventos append-only | Todos los agentes |
| `agent_sessions` | Historial conversacional 72h TTL | Sistema |
| `agent_memory` | Correcciones y aprendizajes | Sistema |
| `agent_errors` | Log de errores del agente | Sistema |
| `agent_pending_topics` | Temas pendientes TTL 72h | Sistema |
| `cfo_cache` | Caché CFO invalidable | CFO |
| `cfo_alertas` | Alertas CFO para el agente | CFO |
| `cfo_configuracion` | Parámetros CFO (watermarks de sync) | CFO |
| `cfo_config` | Config CFO (WhatsApp, etc.) | CFO |
| `cfo_informes` | Informes CFO generados | CFO |
| `cfo_jobs` | Jobs de generación de informes CFO | CFO |
| `cfo_deudas` | Deudas productivas/no productivas | CFO |
| `cfo_instrucciones` | Instrucciones permanentes al CFO | CFO Chat |
| `cfo_compromisos` | Compromisos registrados en CFO chat | CFO Chat |
| `cfo_chat_historia` | Historial chat CFO estratégico | CFO Chat |
| `cfo_financiero_config` | Config gastos fijos semanales | CFO Est. |
| `cfo_presupuesto_mensual` | Presupuestos mensuales generados | CFO Est. |
| `crm_clientes` | CRM de clientes | RADAR |
| `gestiones_cobranza` | Historial gestiones de cobro | RADAR |
| `gestiones_cartera` | Gestiones de cobro adicionales | RADAR |
| `cartera_gestiones` | Gestiones WhatsApp Mercately | RADAR |
| `radar_queue` | Cola de cobro priorizada | RADAR |
| `mercately_config` | Config API Mercately | Sistema |
| `mercately_sessions` | Sesiones activas Mercately (TTL 5 min) | Sistema |
| `catalogo_planes` | Planes de crédito (NUNCA hardcodear) | Loanbook |
| `catalogo_motos` | Catálogo modelos motos | Settings |
| `catalogo_servicios` | SOAT, matrícula, GPS (extras) | Settings |
| `notifications` | Notificaciones frontend | Sistema |
| `webhook_config` | Config webhook Alegra registrado | Sistema |
| `webhook_subscriptions` | Suscripciones Alegra webhooks | Sistema |
| `contactos` | Clientes sync desde Alegra | Sistema |
| `dian_facturas_procesadas` | Anti-dup DIAN | Sistema |
| `proveedores_config` | Autoretenedores y reglas por NIT | Agente Contador |
| `alegra_credentials` | Credenciales Alegra en BD | Sistema |
| `system_config` | Flags de sistema | Sistema |
| `presupuesto` | Presupuesto anual por categoría | Sistema |
| `default_accounts` | Cuentas por defecto de operaciones | Settings |
| `audit_logs` | Log de acciones de usuarios | Sistema |
| `repuestos_catalogo` | Catálogo repuestos TVS | Sistema |
| `repuestos_facturas` | Facturas de venta de repuestos | Sistema |
| `repuestos_movimientos` | Movimientos de stock repuestos | Sistema |
| `sismo_knowledge` | Base de conocimiento RAG | Sistema |
| `gastos_cleanup_jobs` | Jobs de limpieza de journals Alegra | Sistema |
| `auditoria_jobs` | Jobs de auditoría Alegra (TTL 24h) | Sistema |
| `auditoria_aprobaciones` | Aprobaciones de limpieza | Sistema |
| `telegram_config` | Config bot Telegram | Sistema |
| `telegram_sessions` | Sesiones Telegram activas | Sistema |
| `chat_messages` | Historial chat del agente | Sistema |

---

## 3. URLs Canónicas

| Servicio | URL |
|---|---|
| Backend | `https://sismo-backend-40ca.onrender.com` |
| Frontend | `https://sismo-bice.vercel.app` |
| Alegra API | `https://api.alegra.com/api/v1/` — NUNCA `app.alegra.com/api/r1/` |
| n8n | `https://roddos.app.n8n.cloud` |
| Repo GitHub | `github.com/RoddosColombia/SISMO` (privado — branch: main) |

---

## 4. Alegra — Endpoints Permitidos y Prohibidos

| Endpoint | Estado | Regla |
|---|---|---|
| `POST /journals` | UNICO para comprobantes | Siempre con `request_with_verify()` |
| `GET /journals` | Verificacion + consulta | TIMEOUT en lotes grandes |
| `GET /categories` | Plan de cuentas | |
| `GET /invoices` | Polling facturas | |
| `GET /payments` | Sync pagos | |
| `GET /bills` | Sync compras | |
| `POST /invoices` | Crear facturas | |
| `POST /bills` | Crear bills | |
| `POST /payments` | Registrar pagos | |
| `DELETE /bills/{id}` | Solo desde auditoria.py (admin) | httpx directo, bypass AlegraService |
| `DELETE /journals/{id}` | Solo desde auditoria.py (admin) | Solo limpieza de duplicados |
| `POST /journal-entries` | PROHIBIDO | Da 403 siempre |
| `GET /accounts` | PROHIBIDO | Da 403 siempre |

---

## 5. Mapa Completo de Rutas API — VERIFICADO DESDE CÓDIGO FUENTE

Base: `https://sismo-backend-40ca.onrender.com`
Prefijo global en server.py: `/api`

### 5.1 Rutas directas en server.py (no en routers)

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/api/health` | Health check rápido |
| GET | `/api/health/smoke` | Smoke test completo post-deploy |
| GET | `/api/health/bus` | Health del bus de eventos |
| GET | `/api/debug-env` | Estado variables de entorno |
| GET | `/api/debug-alegra` | Test conexión Alegra |
| POST | `/api/webhook/alegra` | LEGACY — solo guarda en notifications, SIN logica |

### 5.2 Tabla de routers — prefijos verificados desde código fuente

| Archivo | Prefijo del router | Ruta base completa | Notas |
|---|---|---|---|
| `auth.py` | `/auth` | `/api/auth` | |
| `settings.py` | `/settings` | `/api/settings` | |
| `alegra.py` | `/alegra` | `/api/alegra` | Proxy Alegra API |
| `chat.py` | `/chat` | `/api/chat` | Agente contador principal |
| `inventory.py` | `/inventario` | `/api/inventario` | |
| `taxes.py` | `/impuestos` | `/api/impuestos` | NO es /taxes |
| `budget.py` | `/presupuesto` | `/api/presupuesto` | |
| `dashboard.py` | (sin prefijo) | `/api/dashboard/...` | tags=["dashboard"] — sin prefix en APIRouter |
| `audit.py` | `/audit-logs` | `/api/audit-logs` | |
| `repuestos.py` | `/repuestos` | `/api/repuestos` | |
| `loanbook.py` | `/loanbook` | `/api/loanbook` | |
| `telegram.py` | `/telegram` | `/api/telegram` | |
| `radar.py` | `/radar` | `/api/radar` | |
| `cfo.py` | `/cfo` | `/api/cfo` | P&L, semáforo, informes, alertas |
| `cfo_estrategico.py` | `/cfo` | `/api/cfo` | Comparte prefijo — agrega /cfo/financiero/*, /cfo/deudas/*, /cfo/presupuesto/*, /cfo/plan-ingresos, /cfo/plan-deudas, /cfo/reporte-lunes, /cfo/cuotas-iniciales, /cfo/indicadores, /cfo/recordatorios |
| `cfo_chat.py` | `/cfo` | `/api/cfo` | Comparte prefijo — agrega /cfo/chat/*, /cfo/instrucciones, /cfo/compromisos |
| `estado_resultados.py` | `/cfo` | `/api/cfo` | Comparte prefijo — agrega /cfo/estado-resultados (JSON/PDF/Excel) |
| `mercately.py` | `/mercately` | `/api/mercately` | |
| `crm.py` | `/crm` | `/api/crm` | |
| `learning.py` | `/crm` | `/api/crm` | Comparte prefijo — agrega solo GET /crm/{id}/learning |
| `scheduler.py` | `/scheduler` | `/api/scheduler` | ALLOWED_JOBS triggerable |
| `alegra_webhooks.py` | `/webhooks` | `/api/webhooks` | Handler REAL con VIN/inventario/loanbook |
| `proveedores_config.py` | `/proveedores` | `/api/proveedores` | NO es /proveedores-config |
| `gastos.py` | `/gastos` | `/api/gastos` | Carga masiva CSV |
| `ventas.py` | `/ventas` | `/api/ventas` | |
| `dian.py` | `/dian` | `/api/dian` | |
| `ingresos.py` | `/ingresos` | `/api/ingresos` | F9 ingresos no operacionales |
| `cartera.py` | `/cartera` | `/api/cartera` | F7 pagos de cuotas de cartera |
| `nomina.py` | `/nomina` | `/api/nomina` | F4 nomina mensual |
| `cxc.py` | `/cxc` | `/api/cxc` | CXC socios + clientes |
| `cxc_socios.py` | `/cxc/socios` | `/api/cxc/socios` | F8 — comparte /cxc con cxc.py |
| `admin_kb.py` | (sin prefijo) | `/api/admin/knowledge-base/...` | Sin prefix en APIRouter |
| `admin_seeds.py` | (sin prefijo) | `/api/admin/run-seed`, `/api/admin/seed-status` | Sin prefix en APIRouter |
| `global66.py` | `/global66` | `/api/global66` | Webhook x-api-key |
| `n8n_hooks.py` | `/n8n` | `/api/n8n` | BUILD 25 |
| `reports.py` | `/reports` | `/api/reports` | Excel export |
| `contabilidad_pendientes.py` | `/contabilidad_pendientes` | `/api/contabilidad_pendientes` | GUION BAJO, no guión medio |
| `conciliacion.py` | `/conciliacion` | `/api/conciliacion` | INAMOVIBLE |
| `auditoria.py` | `/auditoria` | `/api/auditoria` | Auditoría Alegra + limpieza duplicados |
| `sync_manual.py` | `/sync` | `/api/sync` | |
| `diagnostico.py` | `/diagnostico` | `/api/diagnostico` | |

### 5.3 Alertas críticas de rutas

**ALERTA 1 — Dos webhooks Alegra con rutas distintas:**
- `POST /api/webhook/alegra` — server.py legacy — solo guarda en notifications, SIN logica
- `POST /api/webhooks/alegra` — routers/alegra_webhooks.py — handler REAL con VIN, inventario, loanbook
- La ruta activa y correcta es `/api/webhooks/alegra`

**ALERTA 2 — Cuatro routers comparten el prefijo /cfo:**
cfo.py, cfo_estrategico.py, cfo_chat.py, estado_resultados.py
FastAPI une los routers automaticamente — no hay conflicto si las rutas individuales son distintas.

**ALERTA 3 — Prefijos con guion bajo (underscore), NO guion medio:**
- Correcto: `/api/contabilidad_pendientes/listado`
- Incorrecto: `/api/contabilidad-pendientes/listado`

**ALERTA 4 — Prefijos que no son lo que parecen:**
- taxes.py usa `/impuestos` (NO /taxes)
- proveedores_config.py usa `/proveedores` (NO /proveedores-config)
- learning.py usa `/crm` (NO /learning)

**ALERTA 5 — Routers sin prefijo en APIRouter:**
- dashboard.py, admin_kb.py, admin_seeds.py — rutas definidas directamente en cada endpoint

---

## 6. Endpoints n8n Hooks

Base: `/api/n8n`

### Sin autenticación
| Método | Ruta | Campos respuesta clave |
|---|---|---|
| GET | `/api/n8n/health` | status, loanbooks_activos, backlog_pendientes, global66_pendientes, alegra_conectada |
| GET | `/api/n8n/status/global66` | eventos_hoy, pendientes_total, alertar |
| GET | `/api/n8n/status/backlog` | total, por_banco {bbva, bancolombia, nequi, global66, davivienda}, alertar |

### Con autenticación (header X-N8N-Key)
| Método | Ruta | Acciones disponibles (campo accion) |
|---|---|---|
| POST | `/api/n8n/agente/contador` | consultar_backlog, resumen_causaciones, consultar_journals |
| POST | `/api/n8n/agente/cfo` | semaforo, alertas_activas, resumen_semanal |
| POST | `/api/n8n/agente/radar` | cola_cobro, mora_activa, triggerear_recordatorios |
| POST | `/api/n8n/agente/loanbook` | dpd_resumen, scores_resumen, recalcular_dpd |
| POST | `/api/n8n/scheduler/{job_id}` | Cualquier job de ALLOWED_JOBS |
| POST | `/api/n8n/evento` | Publica en bus roddos_events |
| POST | `/api/n8n/alerta` | Inserta en notifications + cfo_alertas + roddos_events |

Tipos de alerta validos: alegra_down, global66_silencio, backlog_alto, mora_critica, cartera_riesgo, sistema_degradado

---

## 7. Inventario Completo de Jobs APScheduler

### Scheduler A: services/scheduler.py (start_scheduler)
Timezone: America/Bogota — 17 jobs

| Job ID | Trigger | Que hace |
|---|---|---|
| dlq_retry | interval 5 min | Reintenta eventos fallidos del bus DLQ |
| process_pending_events | interval 60 seg | Procesa roddos_events estado=pending |
| informe_cfo_mensual | cron dia 1 08:00 | Informe CFO mensual + WhatsApp CEO |
| wa_recordatorios_preventivos | cron lunes 08:00 | Template 1 WA — cuota vence mañana |
| wa_recordatorios_vencimiento | cron miercoles 08:00 | Template 2 WA — dia de cobro |
| wa_alertas_mora_d1 | cron jueves 09:00 | Template 3 WA — mora D+1 |
| wa_alertas_mora_severa | cron sabado 09:00 | Template 5 WA — mora severa +30 dias |
| sync_pagos_alegra | interval 5 min | Pull pagos Alegra → aplica a loanbook |
| sync_facturas_alegra | interval 5 min | Pull facturas Alegra → detecta VIN → actualiza inventario |
| procesar_reintentos_alegra | interval 5 min | Reintenta causaciones fallidas en conciliacion_reintentos |
| reconciliar_inventario_lunes | cron lunes 07:00 | Verifica conteo motos |
| dian_sync_diario | cron 23:00 | Sync facturas DIAN ventana 48h |
| portfolio_summary_diario | cron 23:30 | Snapshot cartera (BUILD 24) |
| financial_report_mensual | cron dia 1 06:00 | P&L mensual (BUILD 24) |
| resumen_semanal_cfo | cron lunes 08:05 | Resumen semanal CFO → cfo_alertas |
| anomalias_contables_diarias | cron 23:30 | Detecta anomalías → cfo_alertas |
| recuperar_global66_pendientes | interval 10 min | Reintenta Global66 no causados (BUILD 25) |

### Scheduler B: services/loanbook_scheduler.py (start_loanbook_scheduler)
Timezone: America/Bogota — 12 jobs

| Job ID | Trigger | Que hace |
|---|---|---|
| calcular_dpd_todos | diario 06:00 | DPD + bucket + interes mora 15%EA |
| alertar_buckets_criticos | diario 06:05 | WA clientes DPD 8/15 + CEO DPD 22 |
| verificar_alertas_cfo | diario 06:10 | Despacha cfo_alertas estado=nueva |
| calcular_scores | diario 06:30 | Scoring A+ a E + seguimiento PTP |
| alertas_predictivas | diario 06:45 | ML riesgo predictivo (BUILD 9) |
| generar_cola_radar | diario 07:00 | Warm-up cache cola RADAR |
| resolver_outcomes | diario 07:30 | Verifica pagos post-gestion (BUILD 9) |
| recordatorio_preventivo | martes 09:00 | WA cuota vence mañana miercoles |
| recordatorio_vencimiento | miercoles 09:00 | WA dia de cobro |
| notificar_mora_nueva | jueves 09:00 | WA DPD == 1 (no pagaron ayer) |
| resumen_semanal_ceo | viernes 17:00 | Resumen enriquecido al CEO |
| procesar_patrones | lunes 08:00 | Patrones ML semanales (BUILD 9) |

### ALLOWED_JOBS — Triggerable via /api/scheduler/trigger o /api/n8n/scheduler

Solo estos 12 son triggereables manualmente:

calcular_dpd_todos, alertar_buckets_criticos, verificar_alertas_cfo,
calcular_scores, generar_cola_radar, recordatorio_preventivo,
recordatorio_vencimiento, notificar_mora_nueva, resumen_semanal_ceo,
alertas_predictivas, resolver_outcomes, procesar_patrones

GAP (P-02): sync_pagos_alegra, sync_facturas_alegra, procesar_reintentos_alegra,
recuperar_global66_pendientes NO estan en ALLOWED_JOBS — no triggereables manualmente aun.

---

## 8. Webhook Global66

| Parametro | Valor |
|---|---|
| Endpoint | POST /api/global66/webhook |
| Auth | Header x-api-key: {GLOBAL66_WEBHOOK_SECRET} (NO HMAC) |
| Body vacio | Prueba de conexion — 200 OK |
| Evento ingreso | WALLET - Founding status — campos: data.originAmount, data.thirdPartyClientName, data.transactionId |
| Evento egreso | RMT - Transaction — campos: payload.originAmount, payload.purpose, payload.transactionId |
| Coleccion | global66_eventos_recibidos — guardar-primero ($setOnInsert), luego causar en Alegra |

---

## 9. Conciliacion Bancaria — Formatos Extractos

Regla absoluta: SIEMPRE .xlsx — NUNCA CSV

| Banco | Hoja | Headers en fila | Columnas |
|---|---|---|---|
| Bancolombia | "Extracto" (obligatoria) | 15 | FECHA (d/m) / DESCRIPCION / VALOR |
| BBVA | primera | 14 | "FECHA DE OPERACION" (DD-MM-YYYY) / "CONCEPTO" / "IMPORTE (COP)" |
| Davivienda | primera | skiprows=4 | Fecha / Descripcion / Valor / Naturaleza (C=ingreso, D=egreso) |
| Nequi | primera | TBD | Parser pendiente — necesita extracto real |
| Global66 | primera | TBD | En enum Banco — parser no implementado |
| Banco de Bogota | — | — | Sin parser |

### Endpoints conciliacion — /api/conciliacion

| Metodo | Ruta | Descripcion |
|---|---|---|
| POST | /cargar-extracto | Upload .xlsx — BackgroundTask si >10 movimientos |
| GET | /job-status/{job_id} | Estado de job en background |
| GET | /pendientes | Movimientos baja confianza pendientes |
| GET | /procesados | Ultimos movimientos causados |
| POST | /resolver/{movimiento_id} | Resolver movimiento manualmente |
| GET | /estado/{fecha} | Estado conciliacion para YYYY-MM-DD |
| GET | /reintentos | Cola de reintentos |
| GET | /diagnostico/causados-hoy | Journals creados hoy |
| GET | /journals-banco | Auditoria por banco y mes (?banco=X&mes=YYYY-MM) |
| POST | /backfill-desde-alegra | Reconstruye procesados desde Alegra |
| POST | /limpiar-bancolombia-parcial | Admin: limpia extractos parciales |
| GET | /test-alegra | Test conexion Alegra directo |
| GET | /job/{job_id}/logs | Logs detallados de un job |

---

## 10. IDs Alegra — Plan de Cuentas RODDOS

| Cuenta | ID Alegra | Notas |
|---|---|---|
| Gastos Generales | 5493 | FALLBACK CORRECTO — NUNCA usar 5495 |
| Sueldos y salarios | 5462 | |
| Honorarios | 5470 | |
| Seguridad Social | 5471 | |
| Dotaciones | 5472 | |
| Honorarios PN (asesoria juridica) | 5475 | |
| Honorarios PJ (asesoria financiera) | 5476 | |
| ICA | 5478 | |
| Arrendamientos | 5480 | ReteFuente 3.5% |
| Servicios / Tech | 5483 | |
| Servicios Publicos | 5484 | |
| Telefono/Internet | 5487 | |
| Mantenimiento | 5490 | |
| Transporte | 5491 | |
| Papeleria | 5497 | |
| Publicidad | 5500 | |
| ICA | 5505 | |
| Comisiones Bancarias | 5508 | |
| GMF 4x1000 | 5509 | |
| Seguros | 5510 | |
| Intereses financieros | 5533 | |
| Intereses rentistas | 5534 | |
| ReteFuente practicada | 236505 | |
| ReteICA practicada | 236560 | |
| Bancolombia | 5314 | Cuenta banco |
| BBVA | 5318 | |
| Davivienda | 5322 | |
| Nequi / Caja | 5310 | |
| CXC Socios | 5329 | |
| CXC Clientes | 5326 | |
| Cartera RDX (creditos RODDOS) | 5327 | |

---

## 11. Reglas de Negocio Criticas

| Regla | Valor |
|---|---|
| Dia de cobro | Siempre miercoles |
| Mora empieza | Jueves (dia siguiente al vencimiento miercoles) |
| Mora diaria | $2.000 COP acumulable — catalogo_planes.mora_diaria |
| IVA | Cuatrimestral: ene-abr / may-ago / sep-dic — NO bimestral |
| ReteICA Bogota | 0.414% |
| ReteFuente arrendamiento | 3.5% |
| ReteFuente honorarios PN | 10% |
| ReteFuente honorarios PJ | 11% |
| ReteFuente servicios | 4% |
| ReteFuente compras | 2.5% (base > $1.344.573) |
| Auteco NIT 860024781 | Autoretenedor — NUNCA ReteFuente |
| Andres Sanjuan CC 80075452 | Gastos → CXC socios — NUNCA gasto operativo |
| Ivan Echeverri CC 80086601 | Gastos → CXC socios — NUNCA gasto operativo |
| Multiplicador quincenal | x2.2 sobre cuota semanal base |
| Multiplicador mensual | x4.4 sobre cuota semanal base |
| Confianza minima para causar | >= 70% |
| Router LLM threshold | 0.70 minimo antes de despachar |
| Campo VIN en inventario | chasis (migrado de vin) — buscar SIEMPRE con $or: [{chasis}, {vin}] |
| Anti-duplicados conciliacion | 3 capas: hash extracto + hash movimiento + GET Alegra |
| Primer cobro loanbook | Primer miercoles de la semana siguiente a la fecha de entrega |

---

## 12. Archivos Inamovibles — NUNCA Modificar

| Archivo | Razon |
|---|---|
| `backend/database.py` | Conexion central MongoDB |
| `backend/dependencies.py` | Inyeccion de dependencias FastAPI |
| `backend/services/alegra_service.py` | Cliente Alegra con request_with_verify() |
| `backend/routers/conciliacion.py` | En produccion — extractos procesados |

---

## 13. Rutas Locales (Dev Machine)

| Recurso | Ruta |
|---|---|
| Repo | C:\Users\AndresSanJuan\roddos-workspace\SISMO |
| Backend | C:\Users\AndresSanJuan\roddos-workspace\SISMO\backend |
| Routers | C:\Users\AndresSanJuan\roddos-workspace\SISMO\backend\routers |
| Services | C:\Users\AndresSanJuan\roddos-workspace\SISMO\backend\services |
| Tests | C:\Users\AndresSanJuan\roddos-workspace\SISMO\tests |
| CLAUDE.md global | ~/.claude/CLAUDE.md |
| CLAUDE.md proyecto | .claude/CLAUDE.md |

---

## 14. Estado de Builds

| Build | Commit | Tests | Entrego |
|---|---|---|---|
| BUILD 24 | v24.0.0 + hotfix-alegra | 67 | EventBusService, 34 cols, 64 indices, URL Alegra corregida |
| BUILD 23 | 884a248 | 37/37 | ACTION_MAP lectura, ROG-1, ventas VIN/motor, cartera, nomina, Backlog |
| BUILD 25 | 8e84ff8 | 9/9 | n8n_hooks 9 endpoints, Global66 x-api-key, recuperacion 10 min |
| Fix n8n | 1d66772 | 65 | db.loanbooks → db.loanbook (4 ocurrencias) + query mora |
| Fix tests | 665c124 | 67 | test_build21 + test_permissions |
| Fix VIN | fc044e5 | 5/5 | _nueva_factura usa $or chasis/vin — PENDIENTE cherry-pick a main (P-01) |

---

## 15. Pendientes Tecnicos (Backlog Arquitectonico)

| ID | Descripcion | Prioridad |
|---|---|---|
| P-01 | Cherry-pick fc044e5 a main — VIN sync fix en _nueva_factura | INMEDIATO |
| P-02 | Agregar sync_pagos_alegra, sync_facturas_alegra, procesar_reintentos_alegra, recuperar_global66_pendientes a ALLOWED_JOBS | Alta |
| P-03 | Construir W1 (monitoreo), W2 (resumen lunes), W3 (alerta backlog) en n8n | Alta |
| P-04 | Parser Nequi para extractos .xlsx | Media |
| P-05 | Parser Global66 para extractos .xlsx mensuales | Media |
| P-06 | Registrar webhooks Alegra manualmente en app.alegra.com | Media |
| P-07 | Extractos bancarios marzo 2026 — pendientes de llegada | Espera |

---

## 16. Notas de Arquitectura

Dos schedulers corren en paralelo al iniciar el servidor:
start_scheduler() + start_loanbook_scheduler() — ambos en startup() de server.py.
Si alguno falla al iniciar, el otro sigue activo.

Cuatro routers comparten prefijo /cfo:
FastAPI une los routers automaticamente — sin conflicto si las rutas individuales son distintas.
Al agregar endpoints CFO nuevos, verificar primero en cual de los 4 archivos corresponde.

cartera.py sigue activo (nota historica enganosa):
El comentario en server.py dice "cartera.py removed in BUILD 6" pero el archivo existe y se registra.
Sus endpoints F7 /api/cartera/registrar-pago estan activos en produccion.

learning.py NO es un router independiente — extiende /crm:
Solo agrega GET /api/crm/{loanbook_id}/learning al prefijo de crm.py.

---

Auditado desde codigo fuente: server.py + 41 archivos de routers/ + services/scheduler.py + services/loanbook_scheduler.py — 5 abril 2026
