# Phase 8-A: CRM Robusto — Context

**Gathered:** 2026-04-05
**Status:** Ready for planning
**Source:** PRD Express Path (docs/FASE8_MASTER_PROMPT.md)

<domain>
## Phase Boundary

Convertir el CRM de SISMO de ficha de contacto a sistema de calificación por comportamiento.
Sin esta capa, RADAR IA (FASE 8-C) no tiene datos de calidad para razonar.

**Entrega concreta:**
- Score multidimensional `score_roddos` (4 dimensiones) en lugar del score unidimensional actual
- Campo `etapa_cobro` en loanbook (6 etapas basadas en DPD)
- Colección `acuerdos_pago` con estructura formal
- Sync automático loanbook → CRM al activar entrega
- 6 nuevos RESULTADO_VALIDOS en crm_service.py
- 5 nuevos endpoints: 3 en /api/crm/, 2 en /api/radar/

**4 archivos que se modifican (solo estos):**
1. `backend/services/crm_service.py`
2. `backend/routers/crm.py`
3. `backend/routers/loanbook.py`
4. `backend/services/loanbook_scheduler.py`

</domain>

<decisions>
## Implementation Decisions

### Score Multidimensional — Fórmula Exacta (LOCKED)

```python
score_roddos = round(
    (dimension_dpd * 0.40) +
    (dimension_gestion * 0.30) +
    (dimension_velocidad * 0.20) +
    (dimension_trayectoria * 0.10)
, 1)
```

**dimension_dpd (0-100):**
- dpd_actual == 0 y dpd_max < 7 → 100
- dpd_actual == 0 y dpd_max < 15 → 80
- dpd_actual <= 7 → 60
- dpd_actual <= 14 → 40
- dpd_actual <= 21 → 20
- dpd_actual >= 22 → 0

**dimension_gestion (0-100):**
- ratio_ptp = ptps_cumplidos / max(ptps_prometidos, 1)
- contactabilidad = veces_contactado / max(intentos_gestion, 1)
- score = round((ratio_ptp * 0.6 + contactabilidad * 0.4) * 100)

**dimension_velocidad (0-100)** — promedio últimas 5 cuotas pagadas:
- 0 días (mismo día) → 100
- 1-2 días → 85
- 3-7 días → 65
- 8-14 días → 40
- > 14 días → 15

**dimension_trayectoria (0-100)** — compara dpd_actual con dpd_hace_4_semanas:
- Mejorando (dpd bajó > 3) → 100
- Estable (dpd cambió < 3) → 60
- Empeorando (dpd subió > 3) → 20
- Sin historial → 60 (neutro)

**Etiquetas finales:**
- >= 85 → "A+" (Diamante)
- >= 70 → "A" (Excelente)
- >= 55 → "B" (Regular)
- >= 40 → "C" (En riesgo)
- >= 25 → "D" (Crítico)
- < 25  → "E" (Recuperación)

### Campo etapa_cobro — Cálculo en calcular_dpd_todos() (LOCKED)

Calculado en `loanbook_scheduler.py::calcular_dpd_todos()` y persistido en loanbook:
- dpd == 0 y proxima_cuota > 2 días → "preventivo"
- dpd == 0 y proxima_cuota <= 2 días → "vencimiento_proximo"
- dpd 1-7   → "gestion_activa"
- dpd 8-14  → "alerta_formal"
- dpd 15-21 → "escalacion"
- dpd >= 22 → "recuperacion"

### Colección acuerdos_pago — Esquema (LOCKED)

Campos: `id`, `loanbook_id`, `cliente_nombre`, `tipo` (pago_parcial|descuento_mora|refinanciacion|acuerdo_total), `condiciones`, `monto_acordado`, `fecha_inicio`, `fecha_limite`, `cuotas_acuerdo[]`, `estado` (activo|cumplido|incumplido|cancelado), `creado_por`, `created_at`

### Sync Automático loanbook → CRM (LOCKED)

En `register_entrega()` de `loanbook.py`, después de activar el loanbook:
- Llamar a `upsert_cliente_desde_loanbook(db, loan)` en crm_service.py
- Inicializa: `score_roddos = 70` (neutro), `etapa_cobro = "preventivo"`, `ptp_activo = null`
- Crea o actualiza `crm_clientes` con datos del loanbook

### Nuevos RESULTADO_VALIDOS — 6 adicionales (LOCKED)

Agregar a `crm_service.py`:
- `"sin_respuesta_72h"` — no contestó en 72h después de gestión
- `"bloqueo_detectado"` — número bloqueó el contacto
- `"numero_apagado"` — número fuera de servicio
- `"pago_parcial_reportado"` — pagó una parte, queda saldo
- `"acuerdo_firmado"` — acuerdo de pago formal creado
- `"disputa_deuda"` — cliente disputa el saldo

### Nuevos Endpoints (LOCKED)

**crm.py:**
- `POST /api/crm/{id}/acuerdo` — crea en acuerdos_pago + gestión "acuerdo_firmado" + actualiza etapa_cobro
- `GET /api/crm/{id}/acuerdos` — todos los acuerdos del loanbook con estado
- `PUT /api/crm/acuerdos/{acuerdo_id}/estado` — actualiza estado (cumplido/incumplido/cancelado)

**radar.py (o crm.py según conveniencia):**
- `GET /api/radar/diagnostico` — loanbooks con dpd_actual calculado, con score_roddos, con etapa_cobro, estado Mercately api_key, último run de cada scheduler job
- `POST /api/radar/arranque` — triggerear calcular_dpd_todos → calcular_scores → generar_cola_radar sin esperar 06:00; retorna job_id

### Reglas de Oro Inamovibles (LOCKED)

- ROG-1: Nunca reportar éxito sin verificar HTTP 200 en Alegra
- ROG-2: Sin atajos, sin deuda técnica
- ROG-3: Todo funciona desde SISMO — sin scripts externos
- Campo VIN: buscar siempre con `$or [{"chasis": x}, {"vin": x}]`
- Fallback cuenta Alegra: 5493 — NUNCA 5495
- DB: `sismo` — NUNCA `sismo-prod`
- IVA cuatrimestral: ene-abr / may-ago / sep-dic
- Gastos socios → CXC socios — NUNCA gasto operativo
- BackgroundTasks + job_id para lotes > 10 registros
- Anti-duplicados en toda operación masiva

### Patrón MongoDB Canónico (LOCKED)

```python
from database import db  # motor async client — NUNCA recrear conexión
# db = client[DB_NAME] donde DB_NAME viene de os.environ["DB_NAME"]
```

### Archivos INAMOVIBLES — No Tocar (LOCKED)

- `backend/services/shared_state.py`
- `backend/routers/conciliacion.py`
- `backend/services/bank_reconciliation.py`
- `backend/services/database.py`
- `backend/dependencies.py`
- `backend/services/alegra_service.py`
- Cualquier router no mencionado en los 4 archivos objetivo

### Tests Obligatorios — 10 tests FASE 8-A (LOCKED)

T1: score_roddos correcto para cliente con 10 cuotas a tiempo → score >= 85 → etiqueta "A+"
T2: score_roddos para DPD=22 y 3 PTPs incumplidos → score < 25 → "E"
T3: Cliente nuevo sin historial → score_roddos = 70 → etiqueta "B"
T4: POST /loanbook/{id}/entrega → crm_clientes se crea con telefono, nombre, cedula
T5: etapa_cobro="gestion_activa" cuando dpd=3
T6: etapa_cobro="recuperacion" cuando dpd=22
T7: POST /api/crm/{id}/acuerdo → crea en acuerdos_pago + gestión "acuerdo_firmado"
T8: GET /api/radar/diagnostico → estructura completa sin error 500
T9: POST /api/radar/arranque → triggerrea los 3 jobs y retorna estado
T10: calcular_scores() actualiza score_roddos y etapa_cobro en todos los loanbooks activos

### Claude's Discretion

- Patrón exacto de mock en tests (AsyncMock vs MagicMock según motor async)
- Estructura interna de `upsert_cliente_desde_loanbook()` más allá de los campos mínimos
- Cómo `POST /api/radar/arranque` dispara los jobs (asyncio.create_task vs BackgroundTasks)
- Nombre del archivo de tests: `test_fase8a_crm_robusto.py` recomendado
- Tests estáticos (análisis de código fuente) vs runtime según aplique para evitar dependencias faltantes

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### PRD Principal
- `docs/FASE8_MASTER_PROMPT.md` — Spec completa FASE 8 con fórmulas exactas, esquemas, endpoints, tests

### Archivos a Modificar
- `backend/services/crm_service.py` — CRM service existente + RESULTADO_VALIDOS actuales
- `backend/routers/crm.py` — Endpoints CRM existentes
- `backend/routers/loanbook.py` — register_entrega() donde se agrega el sync
- `backend/services/loanbook_scheduler.py` — calcular_dpd_todos() y calcular_scores()

### Patrones y Contratos
- `backend/services/database.py` — Patrón canónico conexión MongoDB (INAMOVIBLE)
- `backend/services/shared_state.py` — INAMOVIBLE — no modificar
- `backend/routers/conciliacion.py` — INAMOVIBLE — no modificar
- `SISMO_ENV_REGISTRY.md` — Variables de entorno, colecciones, IDs Alegra, reglas de negocio

### Tests de Referencia (Patrón Estático)
- `backend/tests/test_fase5_vin_sync.py` — Patrón tests estáticos usado en este proyecto
- `backend/tests/test_build25_n8n_global66.py` — Patrón análisis estático con Path().read_text()
- `backend/tests/test_permissions.py` — Patrón imports y mocks

</canonical_refs>

<specifics>
## Specific Ideas

- Score neutro para cliente nuevo = 70 exacto (no 65, no 75)
- etapa_cobro debe persistirse en el documento loanbook (no calcularse on-the-fly)
- POST /api/radar/arranque retorna `job_id` — BackgroundTasks pattern ya establecido en el proyecto
- `acuerdo_firmado` debe aparecer tanto en RESULTADO_VALIDOS como crear entrada en acuerdos_pago
- diagnostico endpoint lee `roddos_events` para último run de cada scheduler job

</specifics>

<deferred>
## Deferred Ideas

- FASE 8-B: Mercately Bidireccional (enviar_whatsapp_con_gestion, webhook cierra loop)
- FASE 8-C: RADAR con Tool Use (ciclo ReAct, 7 tools formales, system prompts diferenciados)
- FASE 8-D: n8n Orquestador (W4 Miércoles, W5 PTPs, W6 Silencio, W7 Webhook, W8 Reporte)
- Score multidimensional para RADAR IA (usa output de 8-A, implementado en 8-C)

</deferred>

---

*Phase: 08a-crm-robusto*
*Context gathered: 2026-04-05 via PRD Express Path (docs/FASE8_MASTER_PROMPT.md)*
