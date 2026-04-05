# SISMO — FASE 8: RADAR IA + CRM Robusto + Mercately Bidireccional + n8n Orquestador
## Master Prompt para ejecución con GSD

**Fecha:** Abril 2026
**Build target:** FASE 8 completa
**Repo:** RoddosColombia/SISMO (branch: main)
**Backend:** FastAPI Python 3.11 · MongoDB Atlas · Render
**Dev machine:** C:\Users\AndresSanJuan\roddos-workspace\SISMO

---

## REGLAS DE ORO — INAMOVIBLES

ROG-1: Nunca reportar éxito sin verificar HTTP 200 en Alegra. El juez es Alegra, no el agente.
ROG-2: Sin atajos. Sin deuda técnica. Cada fase deja el sistema mejor que antes.
ROG-3: Todo debe funcionar desde SISMO. No parchear con scripts externos.

Reglas adicionales inamovibles:
- Ningún movimiento bancario se descarta silenciosamente
- BackgroundTasks + job_id para lotes > 10 registros
- Anti-duplicados en toda operación masiva
- Cobranza 100% remota — NUNCA sugerir visitas en campo ni geolocalización
- Los gastos de socios van a CXC socios — NUNCA como gasto operativo
- Campo VIN en inventario: `chasis` — buscar siempre con $or [{chasis}, {vin}]
- IVA cuatrimestral: ene-abr / may-ago / sep-dic
- Fallback cuenta Alegra: 5493 — NUNCA 5495
- DB MongoDB: `sismo` — NUNCA `sismo-prod`

---

## CONTEXTO TÉCNICO AUDITADO — LO QUE EXISTE HOY

### Lo que ya funciona y NO se modifica

**Loanbook (loanbook.py) — COMPLETO:**
- CRUD completo: crear, editar, entregar, registrar pago, gestionar, PTP
- Regla del Miércoles implementada correctamente en _first_wednesday()
- Cálculo DPD on-the-fly + _compute_stats()
- Mutex anti-doble venta
- Bus de eventos después de cada operación

**RADAR scheduler (loanbook_scheduler.py) — 13 jobs:**
- calcular_dpd_todos() 06:00 — calcula DPD + bucket + interés mora 15%EA
- calcular_scores() 06:30 — score simple (% cuotas a tiempo)
- generar_cola_radar() 07:00 — invalida caché y genera cola
- alertar_buckets_criticos() 06:05 — WA diferenciado DPD 8/15/22
- recordatorio_preventivo/vencimiento/notificar_mora_nueva
- Todos los jobs tienen guard: sin api_key → solo log, sin crash

**RADAR router (radar.py) — 4 endpoints:**
- GET /api/radar/portfolio-health
- GET /api/radar/queue
- GET /api/radar/semana
- GET /api/radar/roll-rate

**CRM (crm.py + crm_service.py) — BASE EXISTENTE:**
- GET /api/crm — lista con DPD y score calculados on-the-fly
- GET /api/crm/{id} — perfil 360° con gestiones, WA, pagos
- PUT /api/crm/{id}/datos — editar contacto
- POST /api/crm/{id}/nota — notas inmutables
- POST /api/crm/{id}/gestion — registrar gestión (10 resultados válidos)
- POST /api/crm/{id}/ptp — compromiso de pago
- RESULTADO_VALIDOS: 10 valores en crm_service.py
- Colecciones: crm_clientes, gestiones_cartera, cartera_gestiones

**Mercately (mercately.py) — CANAL OUTBOUND FUNCIONAL:**
- enviar_whatsapp(phone, mensaje) — función base, nunca lanza excepción
- 5 templates: T1 preventivo, T2 vencimiento, T3 mora D+1, T4 confirmación pago, T5 mora severa
- Webhook inbound: recibe comprobantes → OCR → propuesta → SI/NO → registra en Alegra
- Detección de intención en texto libre (SALDO/PAGO/DIFICULTAD)
- Session TTL 5 min para flujos de confirmación
- Mensajes de INTERNO → Agente Contador via process_chat

**n8n (n8n_hooks.py + workflows en n8n/):**
- W1 health monitor (cada 5 min)
- W2 resumen lunes CEO+CFO (lunes 8:10 AM Bogotá)
- W3 alerta backlog conciliación (diario 9 AM Bogotá)
- 9 endpoints /api/n8n/* con autenticación X-N8N-Key
- ALLOWED_JOBS en scheduler.py: 16 jobs triggereables

**shared_state.py — 6 funciones (INAMOVIBLE):**
- get_portfolio_health, get_daily_collection_queue, get_loanbook_snapshot
- get_client_360, get_moto_status, handle_state_side_effects
- Caché TTL 30s en memoria

### Brechas identificadas que bloquean FASE 8

BRECHA 1 — RADAR es scheduler, no agente IA:
Los agentes de SISMO están al 60% hacia agente autónomo real. Tienen
system prompts, permisos en código, RAG, bus de eventos — pero NO tienen
Tool Use real de Anthropic API ni ciclo ReAct (Reason-Act-Observe).
RADAR hoy: scheduler que dispara templates fijos sin razonar sobre el cliente.
RADAR necesario: agente que revisa historial, decide acción, encadena pasos.

BRECHA 2 — Score unidimensional:
Score actual = % cuotas a tiempo. Un cliente que siempre paga 2 días tarde
tiene score F aunque nunca haya fallado. Necesitamos 4 dimensiones:
DPD histórico (40%) + comportamiento gestión PTPs (30%) + velocidad pago (20%) + trayectoria (10%).

BRECHA 3 — No existen acuerdos de pago estructurados:
PTP es "prometió pagar el jueves". Un acuerdo tiene condiciones, descuentos de mora,
nuevas fechas, firma, seguimiento. Sin colección acuerdos_pago, los 3 clientes
en DPD > 22 no tienen instrumento de gestión.

BRECHA 4 — Webhook no cierra el loop:
Cuando cliente responde "ya pagué" → alerta creada pero NO gestión en CRM,
NO actualización de cola RADAR, NO verificación automática de cuota.
El cobrador debe registrar manualmente. RADAR nunca se entera.

BRECHA 5 — APScheduler frágil en Render:
Render free tier reinicia procesos. Cuando el proceso muere, los schedulers
del miércoles 06:00 mueren silenciosamente. Los 17 loanbooks activos pueden
tener dpd_actual=0 porque el job no corrió. n8n corre fuera de Render y
tiene retry nativo — es el orquestador correcto para el Miércoles de Cobro.

BRECHA 6 — CRM no se sincroniza automáticamente:
Cuando se activa un loanbook (/entrega), crm_clientes no se crea/actualiza.
Los 17 loanbooks activos pueden no tener ficha CRM completa.

BRECHA 7 — Pipeline de etapas sin definir:
No hay campo etapa_cobro en loanbook. Todos los clientes en mora se tratan
igual independientemente de si están en gestión activa (DPD 1-7) o en
protocolo recuperación (DPD 22+). RADAR necesita etapas con acciones distintas.

---

## ARQUITECTURA DE FASE 8 — 4 CAPAS EN SECUENCIA

```
Capa 1: CRM Robusto (base de datos de comportamiento)
  └─ Score multidimensional, acuerdos_pago, pipeline etapas, sync automático

Capa 2: Mercately Bidireccional (canal de cobranza real)
  └─ Webhook cierra loop, enviar_whatsapp_con_gestion(), whitelist dinámica

Capa 3: RADAR con Tool Use (agente que razona)
  └─ System prompt diferenciado, 7 tools formales, ciclo ReAct

Capa 4: n8n Orquestador (infraestructura resiliente)
  └─ W4 Miércoles, W5 PTPs, W6 Silencio, W7 Webhook, W8 Reporte
```

---

## FASE 8-A: CRM ROBUSTO

### Objetivo
Convertir el CRM de ficha de contacto a sistema de calificación por comportamiento.
Sin esta capa, RADAR IA no tiene datos de calidad para razonar.

### Archivos a modificar
- backend/services/crm_service.py — score multidimensional + sync automático
- backend/routers/crm.py — endpoints acuerdos + pipeline
- backend/routers/loanbook.py — trigger sync CRM al activar entrega
- backend/services/loanbook_scheduler.py — actualizar score multidimensional en calcular_scores()

### Archivos a NO modificar
- backend/services/shared_state.py (INAMOVIBLE)
- backend/routers/conciliacion.py (INAMOVIBLE)
- backend/services/bank_reconciliation.py
- Cualquier router no mencionado arriba

### Nuevas colecciones MongoDB
- acuerdos_pago: acuerdos formales de pago/reestructuración
  Campos: id, loanbook_id, cliente_nombre, tipo (pago_parcial|descuento_mora|
  refinanciacion|acuerdo_total), condiciones, monto_acordado, fecha_inicio,
  fecha_limite, cuotas_acuerdo[], estado (activo|cumplido|incumplido|cancelado),
  creado_por, created_at

### Score multidimensional — definición exacta

score_roddos = round(
  (dimension_dpd * 0.40) +
  (dimension_gestion * 0.30) +
  (dimension_velocidad * 0.20) +
  (dimension_trayectoria * 0.10)
, 1)

dimension_dpd (0-100):
  dpd_actual == 0 y dpd_max < 7 → 100
  dpd_actual == 0 y dpd_max < 15 → 80
  dpd_actual <= 7 → 60
  dpd_actual <= 14 → 40
  dpd_actual <= 21 → 20
  dpd_actual >= 22 → 0

dimension_gestion (0-100):
  ratio_ptp = ptps_cumplidos / max(ptps_prometidos, 1)
  contactabilidad = veces_contactado / max(intentos_gestion, 1)
  score = round((ratio_ptp * 0.6 + contactabilidad * 0.4) * 100)

dimension_velocidad (0-100):
  Para cuotas pagadas: días_entre(vencimiento, fecha_pago)
  0 días (mismo día) → 100
  1-2 días → 85
  3-7 días → 65
  8-14 días → 40
  > 14 días → 15
  promedio de las últimas 5 cuotas pagadas

dimension_trayectoria (0-100):
  Comparar dpd_actual con dpd_hace_4_semanas (desde score_historial[])
  Mejorando (dpd bajó > 3) → 100
  Estable (dpd cambió < 3) → 60
  Empeorando (dpd subió > 3) → 20
  Sin historial → 60 (neutro)

Etiqueta final:
  score_roddos >= 85 → "A+" (Diamante)
  score_roddos >= 70 → "A"  (Excelente)
  score_roddos >= 55 → "B"  (Regular)
  score_roddos >= 40 → "C"  (En riesgo)
  score_roddos >= 25 → "D"  (Crítico)
  score_roddos < 25  → "E"  (Recuperación)

### Pipeline de etapas — campo etapa_cobro en loanbook

etapa_cobro se calcula en calcular_dpd_todos() y se persiste en loanbook:
  dpd == 0 y proxima_cuota > 2 días → "preventivo"
  dpd == 0 y proxima_cuota <= 2 días → "vencimiento_proximo"
  dpd 1-7   → "gestion_activa"
  dpd 8-14  → "alerta_formal"
  dpd 15-21 → "escalacion"
  dpd >= 22 → "recuperacion"

### Sync automático loanbook → CRM

En register_entrega() de loanbook.py, después de activar el loanbook,
llamar a upsert_cliente_desde_loanbook(db, loan):
  Crea o actualiza crm_clientes con todos los datos del loanbook
  Inicializa score_roddos = 70 (neutro para cliente nuevo)
  Inicializa etapa_cobro = "preventivo"
  Inicializa ptp_activo = null

### Tipificación granular — ampliar RESULTADO_VALIDOS

Agregar a crm_service.py:
  "sin_respuesta_72h"        — no contestó en 72h después de gestión
  "bloqueo_detectado"        — número bloqueó el contacto
  "numero_apagado"           — número fuera de servicio
  "pago_parcial_reportado"   — pagó una parte, queda saldo
  "acuerdo_firmado"          — acuerdo de pago formal creado
  "disputa_deuda"            — cliente disputa el saldo

### Nuevos endpoints CRM

POST /api/crm/{id}/acuerdo
  Body: {tipo, monto_acordado, fecha_limite, condiciones, cuotas_acuerdo[]}
  Crea en acuerdos_pago + registra gestión "acuerdo_firmado" + actualiza etapa_cobro

GET /api/crm/{id}/acuerdos
  Retorna todos los acuerdos del loanbook con estado

PUT /api/crm/acuerdos/{acuerdo_id}/estado
  Actualiza estado del acuerdo (cumplido/incumplido/cancelado)

GET /api/radar/diagnostico
  Retorna: cuántos loanbooks tienen dpd_actual calculado, cuántos tienen
  score_roddos, cuántos tienen etapa_cobro, estado Mercately api_key,
  último run de cada job del scheduler (desde roddos_events)

POST /api/radar/arranque
  Triggerear inmediatamente: calcular_dpd_todos → calcular_scores →
  generar_cola_radar sin esperar al 06:00. Retorna job_id con estado.

### Tests FASE 8-A (todos deben pasar antes de continuar a 8-B)

T1: score_roddos se calcula correctamente para cliente con 10 cuotas pagadas
    a tiempo → score >= 85 → etiqueta "A+"
T2: score_roddos para cliente con DPD=22 y 3 PTPs incumplidos → score < 25 → "E"
T3: Cliente nuevo (sin historial) → score_roddos = 70 (neutro) → etiqueta "B"
T4: POST /loanbook/{id}/entrega → crm_clientes se crea automáticamente
    con telefono, nombre, cedula del loanbook
T5: etapa_cobro="gestion_activa" cuando dpd=3
T6: etapa_cobro="recuperacion" cuando dpd=22
T7: POST /api/crm/{id}/acuerdo → crea en acuerdos_pago + gestión "acuerdo_firmado"
T8: GET /api/radar/diagnostico → retorna estructura completa sin error 500
T9: POST /api/radar/arranque → triggerrea los 3 jobs y retorna estado
T10: calcular_scores() actualiza score_roddos y etapa_cobro en todos los loanbooks activos

---

## FASE 8-B: MERCATELY BIDIRECCIONAL

### Objetivo
Cerrar el loop de cobranza: cada respuesta de cliente genera una acción
automática en el CRM. Mercately pasa de canal outbound a canal de cobranza real.

### Archivos a modificar
- backend/routers/mercately.py — webhook loop cerrado + nueva función
- backend/services/crm_service.py — ningún cambio, solo usar lo nuevo de 8-A

### Cambio 1 — Función enviar_whatsapp_con_gestion()

Nueva función que reemplaza enviar_whatsapp() para cobranza:

async def enviar_whatsapp_con_gestion(
    loanbook_id: str,
    telefono: str,
    mensaje: str,
    template_id: str,      # T1/T2/T3/T4/T5/libre/recordatorio_ptp
    resultado_gestion: str,  # del RESULTADO_VALIDOS
    nota: str = "",
    autor: str = "sistema"
) -> bool:
    sent = await enviar_whatsapp(telefono, mensaje)
    if sent:
        await registrar_gestion(db, loanbook_id, "whatsapp",
                                resultado_gestion, nota, autor)
    await _log_gestion_whatsapp(...)
    return sent

Todos los templates T1-T5 deben migrar a esta función.
enviar_whatsapp() se mantiene solo para mensajes sin contexto de loanbook.

### Cambio 2 — Webhook cierra el loop

En _handle_cliente_text(), después de detectar la intención y responder:

SI intención == "PAGO":
  → registrar_gestion(loanbook_id, "whatsapp", "contestó_pagará_hoy",
                      "Cliente reportó pago por WhatsApp", "webhook")
  → Publicar evento en roddos_events tipo "pago.reportado.whatsapp"
  → Invalidar caché RADAR para que la cola refleje el cambio

SI intención == "DIFICULTAD" y el cliente menciona una fecha:
  → Extraer fecha del texto (regex básico: "el lunes", "el jueves", "el X")
  → registrar_ptp(db, loanbook_id, fecha_extraida, monto_cuota, "webhook")
  → registrar_gestion(..., "contestó_prometió_fecha", ...)
  → Publicar evento "ptp.registrado" al bus

SI intención == "DIFICULTAD" sin fecha:
  → registrar_gestion(..., "contestó_no_pagará", "Reportó dificultad sin fecha")
  → Publicar evento "mora.detectada" al bus

SI intención == "NO_RECONOCIDA" y el loanbook tiene dpd > 7:
  → registrar_gestion(..., "sin_respuesta_72h" NO — este es texto recibido)
  → Mantener flujo actual (mensaje genérico + número RODDOS)

### Cambio 3 — Whitelist dinámica

En _detect_sender(), en lugar de leer solo cfg.get("whitelist"):
  whitelist_config = cfg.get("whitelist", [])
  usuarios_internos = await db.users.find(
      {"role": {"$in": ["admin", "contador", "cobrador"]}},
      {"_id": 0, "phone": 1}
  ).to_list(50)
  whitelist_dinamica = whitelist_config + [u.get("phone","") for u in usuarios_internos]
  whitelist = [w for w in whitelist_dinamica if w]

### Cambio 4 — Templates con contexto del score

T3 (mora D+1) debe incluir mora acumulada real:
  Leer dpd_actual y interes_mora_acumulado del loanbook
  Incluir en el mensaje: "llevas X días con mora acumulada de $Y"

T5 (mora severa) debe incluir etapa_cobro:
  Si etapa_cobro == "recuperacion" → incluir número CEO para escalación directa

### Tests FASE 8-B

T11: Cliente envía "ya pagué" → gestión "contestó_pagará_hoy" creada en gestiones_cartera
T12: Cliente envía "el jueves te pago" → PTP creado con fecha del próximo jueves
T13: Cliente en whitelist dinámica (usuario con role="cobrador") →
     detectado como INTERNO, mensajes pasan al Agente Contador
T14: enviar_whatsapp_con_gestion() retorna True Y gestión queda en gestiones_cartera
T15: T1 enviado → gestión "recordatorio_enviado" registrada automáticamente
T16: T3 enviado → mensaje incluye mora acumulada real del loanbook

---

## FASE 8-C: RADAR CON TOOL USE

### Objetivo
Convertir RADAR de scheduler con templates a agente que razona sobre cada cliente
antes de actuar. Implementar Tool Use real de Anthropic API.

### La brecha central (del diagnóstico SISMO_Protocolo_Hibrido_IA.docx)
Patrón actual: LLM responde texto → ACTION_MAP parsea → dispatcher llama handler
Patrón objetivo: LLM recibe tools[] → decide cuál llamar → verifica resultado → encadena

La migración NO descarta código existente. Los handlers Python existentes
se declaran como tool definitions con sus schemas en la API de Anthropic.

### Archivos a modificar
- backend/agent_prompts.py — agregar SYSTEM_PROMPT_RADAR
- backend/ai_chat.py — agregar endpoint de chat RADAR + tool definitions
- backend/routers/chat.py — verificar que existe routing a RADAR

### System prompt RADAR — texto exacto

SYSTEM_PROMPT_RADAR = """
Eres el Agente RADAR de RODDOS S.A.S. — gestor inteligente de cobranza 100% remota.

IDENTIDAD Y DOMINIO:
Tu dominio exclusivo es la cartera activa, el ciclo DPD, los contactos de cobranza
y las gestiones con clientes. Eres el único agente que puede registrar gestiones
de cobranza y enviar mensajes de cobro.

REGLA ABSOLUTA: Cobranza 100% remota.
NUNCA sugieras visitas en campo. NUNCA uses geolocalización.
Canal único: llamada telefónica + WhatsApp Mercately.

ANTES DE ACTUAR:
Siempre revisa el perfil 360° del cliente antes de decidir qué mensaje enviar.
Un cliente con score A+ que falló su primera cuota recibe trato diferente
al cliente score E con 3 PTPs incumplidos.

PRIORIDADES:
1. Clientes en etapa "recuperacion" (DPD >= 22) → escalar al CEO siempre
2. Clientes en etapa "escalacion" (DPD 15-21) → mensaje formal + oferta de acuerdo
3. Clientes en etapa "alerta_formal" (DPD 8-14) → gestión activa + PTP obligatorio
4. Clientes en etapa "gestion_activa" (DPD 1-7) → contacto + registro de gestión
5. Clientes "vencimiento_proximo" → recordatorio preventivo personalizado

HERRAMIENTAS DISPONIBLES:
Usa las herramientas para obtener información antes de actuar.
Nunca inventes datos — consulta siempre antes de responder.

RESTRICCIONES TÉCNICAS:
- NO puedes crear journals en Alegra → eso lo hace el Agente Contador
- NO puedes modificar el loanbook directamente → solo gestiones y PTPs
- NO puedes acceder a datos financieros del CFO → ese es el Agente CFO
- SÍ puedes registrar gestiones, PTPs, acuerdos y enviar WhatsApp
"""

### Tool definitions para RADAR (7 tools)

Declarar en ai_chat.py como tools[] para la llamada a la API de Anthropic:

tool_consultar_cola_priorizada:
  description: "Lista la cola de cobranza del día ordenada por urgencia.
                Incluye DPD, score_roddos, etapa_cobro, último contacto,
                PTP activo y monto a cobrar por cliente."
  input_schema: {}
  handler: → get_daily_collection_queue(db) de shared_state

tool_get_perfil_360:
  description: "Obtiene el perfil completo de un cliente: datos de contacto,
                historial de pagos, gestiones anteriores, score multidimensional,
                PTPs activos y acuerdos vigentes. SIEMPRE llamar antes de contactar."
  input_schema: {loanbook_id: string}
  handler: → GET /api/crm/{loanbook_id} (crm.py get_crm_cliente)

tool_registrar_gestion:
  description: "Registra un contacto de cobranza. Persiste en gestiones_cartera,
                loanbook.gestiones[] y crm_clientes. Siempre registrar después de
                cualquier intento de contacto, exitoso o no."
  input_schema:
    loanbook_id: string (requerido)
    canal: enum [llamada, whatsapp, email] (requerido)
    resultado: enum RESULTADO_VALIDOS (requerido)
    nota: string (opcional, máx 500 chars)
  handler: → registrar_gestion() de crm_service

tool_registrar_ptp:
  description: "Registra un compromiso de pago formal del cliente.
                Solo usar cuando el cliente prometió una fecha específica."
  input_schema:
    loanbook_id: string (requerido)
    ptp_fecha: string ISO date (requerido)
    ptp_monto: float (requerido)
  handler: → registrar_ptp() de crm_service

tool_registrar_acuerdo:
  description: "Crea un acuerdo formal de pago o reestructuración de deuda.
                Solo para clientes en etapa escalacion o recuperacion.
                Requiere aprobación implícita en el contexto de la conversación."
  input_schema:
    loanbook_id: string (requerido)
    tipo: enum [pago_parcial, descuento_mora, refinanciacion, acuerdo_total]
    monto_acordado: float (requerido)
    fecha_limite: string ISO date (requerido)
    condiciones: string (descripción del acuerdo, máx 500 chars)
  handler: → POST /api/crm/{id}/acuerdo (nuevo endpoint de 8-A)

tool_enviar_whatsapp_cobranza:
  description: "Envía un mensaje WhatsApp de cobranza Y registra la gestión
                automáticamente. Personaliza el mensaje según el perfil del cliente.
                No usar templates genéricos — adaptar al contexto del cliente."
  input_schema:
    loanbook_id: string (requerido)
    telefono: string +57XXXXXXXXXX (requerido)
    mensaje: string (requerido, máx 1000 chars)
    template_id: string (T1/T2/T3/T4/T5/libre)
  handler: → enviar_whatsapp_con_gestion() de mercately (nuevo de 8-B)

tool_consultar_score:
  description: "Consulta el score multidimensional de un cliente con desglose
                por dimensión. Útil para explicar al usuario por qué se prioriza
                un cliente sobre otro."
  input_schema: {loanbook_id: string}
  handler: → DB loanbook + crm_clientes, retorna score_roddos + dimensiones

### Ciclo ReAct del Miércoles de Cobro

Ejemplo de flujo autónomo cuando el usuario dice "Arrancar cobranza del miércoles":

1. RADAR llama tool_consultar_cola_priorizada()
   → Ve: 2 en recuperación, 3 en escalación, 5 en alerta_formal, 7 preventivos

2. Para cada cliente en recuperación (DPD >= 22):
   RADAR llama tool_get_perfil_360(loanbook_id)
   → Analiza: ¿tiene PTP activo? ¿cuántos intentos sin respuesta?
   → Si no contestó en 72h → herramienta "sin_respuesta_72h"
   → Llama tool_registrar_gestion(resultado="sin_respuesta_72h")
   → Llama tool_enviar_whatsapp_cobranza(mensaje personalizado al CEO)

3. Para cada cliente en alerta_formal sin PTP:
   RADAR llama tool_get_perfil_360(loanbook_id)
   → Revisa última gestión, score, historial de PTPs
   → Construye mensaje personalizado según score (A vs E reciben mensaje diferente)
   → Llama tool_enviar_whatsapp_cobranza(mensaje_personalizado)
   → Llama tool_registrar_gestion(resultado="contestó_prometió_fecha" si tiene respuesta)

4. Para clientes preventivos con score >= 70:
   → Recordatorio amable
   → Para score < 40: incluir mención de mora acumulada
   → Llama tool_enviar_whatsapp_cobranza()
   → tool_registrar_gestion(resultado="recordatorio_enviado")

5. RADAR responde al usuario:
   "Procesé 17 clientes. 2 escalados al CEO (DPD 22+).
    5 mensajes formales con solicitud de PTP.
    7 recordatorios preventivos enviados.
    3 clientes tienen PTP activo — monitoreando."

### Endpoint chat RADAR

POST /api/radar/chat
  Body: {message: string, session_id: string}
  Auth: JWT
  Handler: similar a /api/chat pero con SYSTEM_PROMPT_RADAR + tools RADAR
  Session: agent_sessions con TTL 72h (mismo patrón que Contador)

### Tests FASE 8-C

T17: "¿Quién tiene DPD más alto esta semana?" → RADAR llama consultar_cola
     y responde con los clientes ordenados, no con texto inventado
T18: "Registra gestión de llamada a LB-2026-0012, no contestó" →
     RADAR llama tool_registrar_gestion → gestión creada en gestiones_cartera
T19: "¿Cuántas cuotas debe Chenier Quintero y cuál es su score?" →
     RADAR llama get_perfil_360 → responde con datos reales de DB
T20: RADAR no intenta crear journal en Alegra cuando registra un pago
     → Error 403 nunca ocurre porque RADAR no tiene esa tool
T21: Usuario dice "mándale un WhatsApp a María que debe 2 cuotas" →
     RADAR llama get_perfil_360 primero (para obtener teléfono) →
     luego enviar_whatsapp_con_gestion → gestión registrada automáticamente
T22: SYSTEM_PROMPT_RADAR está en SYSTEM_PROMPTS['radar'] y el router
     despacha correctamente cuando el intent es de cobranza
T23: En una sola conversación RADAR puede: consultar cola → ver perfil →
     enviar WhatsApp → registrar gestión → sin que usuario confirme cada paso

---

## FASE 8-D: N8N WORKFLOWS W4-W8

### Objetivo
Mover el Miércoles de Cobro fuera de Render para eliminar la fragilidad del
APScheduler. Agregar workflows de seguimiento, escalación y reporte.

### Prerequisito
Los endpoints /api/n8n/* ya existen y están verificados.
Variable SISMO_N8N_KEY ya configurada en n8n.

### W4 — Miércoles de Cobro (reemplaza APScheduler)

Archivo: n8n/W4_miercoles_cobro.json
Trigger: CRON "0 11 * * 3" (11:00 UTC = 06:00 AM Bogotá, miércoles)

Nodos:
1. Trigger Miércoles 06:00 AM Bogotá
2. POST /api/n8n/scheduler/calcular_dpd_todos (auth)
   → IF error: POST /api/n8n/alerta tipo="sistema_degradado" → esperar 10 min → retry
3. Esperar 25 minutos (APScheduler tarda ~15 min con 17 loanbooks)
4. POST /api/n8n/scheduler/calcular_scores (auth)
   → IF error: alerta
5. Esperar 20 minutos
6. POST /api/n8n/scheduler/generar_cola_radar (auth)
7. Esperar hasta 09:00 AM (espera calculada desde hora actual)
8. GET /api/n8n/health → verificar que SISMO está vivo
   → IF status != "ok": alerta sistema_degradado → NO enviar WhatsApp
9. IF ok: POST /api/n8n/scheduler/recordatorio_vencimiento (auth)
10. Log final: cuántos clientes procesados, cuántos mensajes enviados

Nota crítica: el APScheduler existente para estos mismos jobs NO se elimina
todavía — W4 corre en paralelo inicialmente como redundancia. Solo desactivar
APScheduler cuando W4 haya corrido 3 miércoles consecutivos sin error.

### W5 — Seguimiento de PTPs

Archivo: n8n/W5_seguimiento_ptps.json
Trigger: CRON "0 13 * * *" (13:00 UTC = 08:00 AM Bogotá, diario)

Nodos:
1. Trigger diario 08:00 AM Bogotá
2. POST /api/n8n/agente/radar accion="cola_cobro" (auth)
   → Nodo Code: filtrar items donde ptp_fecha == hoy O ptp_fecha == mañana
3. Para PTPs de HOY (si los hay):
   → POST /api/n8n/agente/radar accion="triggerear_recordatorios" (auth)
   → POST /api/n8n/alerta tipo="backlog_alto" si hay PTPs sin seguimiento
4. Para PTPs de MAÑANA:
   → POST alerta interna al CEO: "PTPs mañana: N clientes"

### W6 — Escalación por silencio

Archivo: n8n/W6_escalacion_silencio.json
Trigger: CRON "0 15 * * 6" (15:00 UTC = 10:00 AM Bogotá, sábado)

Nodos:
1. Trigger sábado 10:00 AM
2. GET /api/n8n/status/backlog (sin auth) → verificar sistema activo
3. POST /api/n8n/agente/radar accion="mora_activa" (auth)
4. Nodo Code JavaScript:
   const clientes = items.filter(c =>
     c.dpd_actual >= 8 &&
     c.ultima_gestion_hace_dias > 3 &&
     c.ultima_gestion_resultado !== "acuerdo_firmado"
   )
   return clientes.map(c => ({
     json: {
       loanbook_id: c.loanbook_id,
       cliente: c.cliente_nombre,
       dpd: c.dpd_actual,
       sin_contacto_dias: c.ultima_gestion_hace_dias
     }
   }))
5. IF hay clientes sin contacto > 72h:
   → POST /api/n8n/alerta tipo="mora_critica"
     mensaje: "X clientes DPD 8+ sin contacto en 72h: [lista]"
   → severidad: "alta" si alguno DPD > 15, "media" si todos < 15

### W7 — Webhook Mercately → SISMO (intermediario)

Archivo: n8n/W7_webhook_mercately.json
Trigger: Webhook (recibe POST de Mercately)
URL de respuesta a configurar en Mercately: https://roddos.app.n8n.cloud/webhook/...

Este workflow actúa como buffer asíncrono para el webhook de Mercately:
1. Webhook Trigger → responde 200 OK a Mercately inmediatamente (< 500ms)
2. En background (sin bloquear):
   → POST /api/mercately/webhook al backend SISMO con el mismo payload
   → Timeout de 30 segundos (Mercately no espera, SISMO puede tardar)
3. IF SISMO responde error:
   → Guardar payload en n8n para reintento
   → Retry en 5 minutos
4. IF SISMO responde OK:
   → Log del evento procesado

Nota: Este workflow solo tiene valor si el webhook de Mercately hoy está
apuntando directo a SISMO y está fallando por timeout. Si el webhook
funciona bien, W7 puede construirse después.

### W8 — Reporte del Jueves

Archivo: n8n/W8_reporte_jueves.json
Trigger: CRON "0 13 * * 4" (13:00 UTC = 08:00 AM Bogotá, jueves)

Nodos:
1. Trigger jueves 08:00 AM Bogotá
2. POST /api/n8n/agente/cfo accion="semaforo" (auth)
3. GET /api/radar/semana (auth) → cobrado vs esperado
4. POST /api/n8n/agente/radar accion="mora_activa" (auth)
5. Nodo Code JavaScript (construir resumen):
   const semaforo = $node["CFO semaforo"].json
   const semana = $node["RADAR semana"].json
   const mora = $node["RADAR mora"].json

   const emoji = semaforo.caja === "VERDE" ? "🟢" :
                 semaforo.caja === "AMARILLO" ? "🟡" : "🔴"

   const mensaje = `${emoji} Reporte Miércoles de Cobro\n` +
     `💰 Recaudo: ${semana.valor_cobrado.toLocaleString('es-CO')} / ` +
                  `${semana.valor_esperado.toLocaleString('es-CO')} ` +
                  `(${semana.pct_cobranza}%)\n` +
     `⚠️ En mora activa: ${mora.total} clientes\n` +
     `📊 Próximas acciones: ver cola RADAR en SISMO`

   return [{json: {mensaje}}]
6. POST /api/n8n/alerta tipo="mora_critica" si pct_cobranza < 70%
7. POST /api/n8n/agente/contador accion="consultar_journals"
   → Para verificar que los pagos del miércoles se causaron correctamente

### Secuencia de construcción n8n

Orden de construcción dentro de Claude Code:
1. W4 primero — es el más crítico para la operación del miércoles
2. W5 — depende de que FASE 8-A esté funcionando (PTPs en CRM)
3. W8 — depende de que los endpoints de radar/semana estén poblados
4. W6 — depende de que el campo ultima_gestion_hace_dias exista en la cola
5. W7 — solo si el webhook directo está fallando por timeout

### Tests FASE 8-D

T24: W4 corre manualmente → POST calcular_dpd_todos ejecutado → job en logs
T25: W4 con SISMO caído → alerta sistema_degradado creada en SISMO notifications
T26: W5 diario → identifica PTPs del día si los hay en DB
T27: W8 construye el mensaje de reporte con datos reales del semáforo CFO
T28: Todos los workflows nuevos aparecen en n8n con estado "Published"

---

## CRITERIOS DE ÉXITO — FASE 8 COMPLETA

Antes de declarar FASE 8 completada, todos los siguientes deben pasar:

☐ 17 loanbooks activos tienen score_roddos calculado (no null, no cero)
☐ 17 loanbooks activos tienen etapa_cobro asignada correctamente
☐ 17 loanbooks activos tienen ficha crm_clientes creada/actualizada
☐ El próximo miércoles los jobs de cobranza corren desde W4 de n8n (con log visible)
☐ Cuando un cliente responde "ya pagué" por WhatsApp → gestión en gestiones_cartera
☐ RADAR Chat responde "¿quién tiene DPD más alto?" con datos reales de DB
☐ RADAR no intenta crear journals en Alegra (tool no disponible)
☐ Un acuerdo de pago se puede crear desde el chat de RADAR para un cliente en escalación
☐ El reporte del jueves llega al CEO con datos del miércoles de cobro

---

## INSTRUCCIONES DE EJECUCIÓN CON GSD

1. Iniciar sesión en Claude Code con este prompt como contexto completo
2. /gsd:discuss-phase FASE-8-A — resolver ambigüedades antes de codificar
3. /gsd:plan-phase FASE-8-A — plan atómico, tareas de 2-3 pasos
4. /gsd:execute-phase FASE-8-A — waves paralelas donde sea posible
5. /gsd:verify-work FASE-8-A — verificar T1-T10 antes de continuar
6. Repetir para 8-B, 8-C, 8-D en ese orden

COMMIT PROTOCOL antes de cada push:
  grep -n "sismo-prod\|MONGODB_URI\|5495\|/journal-entries\|/accounts" backend/
  grep -rn "request_with_verify\|create_task\|BackgroundTasks" si hay nuevos endpoints Alegra
  pytest backend/tests/ -x -q 2>&1 | tail -10
  git add [archivos específicos] — nunca git add .
  git commit -m "feat(FASE8-X): descripción específica"
  git push origin main

NO usar worktrees para FASE 8. Ejecutar siempre directamente en main.
GSD worktrees = solo discuss+plan. Execute siempre en main.

---

*SISMO — Sistema Inteligente de Soporte y Monitoreo Operativo*
*RODDOS S.A.S. · FASE 8 · Abril 2026 · Bogotá D.C., Colombia*
*Generado con base en auditoría completa de radar.py, loanbook.py, crm.py,*
*crm_service.py, mercately.py, shared_state.py, loanbook_scheduler.py*
*y el documento SISMO_Protocolo_Hibrido_IA.docx*
