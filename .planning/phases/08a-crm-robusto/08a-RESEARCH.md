# Phase 08a: CRM Robusto — Research

**Researched:** 2026-04-04
**Domain:** CRM + DPD Scheduler + Score multidimensional + Acuerdos de pago
**Confidence:** HIGH (all findings from direct source code inspection)

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Score multidimensional `score_roddos` con fórmula exacta de 4 dimensiones (ver CONTEXT.md)
- Campo `etapa_cobro` calculado en `calcular_dpd_todos()` y persistido en loanbook
- Colección `acuerdos_pago` con esquema exacto definido
- Sync automático en `register_entrega()` → llamar `upsert_cliente_desde_loanbook(db, loan)`
- 6 nuevos RESULTADO_VALIDOS (exactamente estos, sin variantes)
- 5 nuevos endpoints (3 en /api/crm/, 2 en /api/radar/)
- 10 tests obligatorios T1–T10
- Score neutro para cliente nuevo = 70 exacto
- `etapa_cobro` persiste en loanbook (no se calcula on-the-fly)
- `acuerdo_firmado` tanto en RESULTADO_VALIDOS como crea entrada en acuerdos_pago
- `/api/radar/diagnostico` lee `roddos_events` para último run de cada scheduler job
- BackgroundTasks + job_id para `/api/radar/arranque`
- 4 archivos target únicamente: crm_service.py, crm.py, loanbook.py, loanbook_scheduler.py

### Claude's Discretion
- Patrón exacto de mock en tests (AsyncMock vs MagicMock según motor async)
- Estructura interna de `upsert_cliente_desde_loanbook()` más allá de los campos mínimos
- Cómo `POST /api/radar/arranque` dispara los jobs (asyncio.create_task vs BackgroundTasks)
- Nombre del archivo de tests: `test_fase8a_crm_robusto.py` recomendado
- Tests estáticos (análisis de código fuente) vs runtime según aplique

### Deferred Ideas (OUT OF SCOPE)
- FASE 8-B: Mercately Bidireccional
- FASE 8-C: RADAR con Tool Use
- FASE 8-D: n8n Orquestador
- Score multidimensional para RADAR IA (output de 8-A, implementado en 8-C)
</user_constraints>

---

## Summary

FASE 8-A transforma el CRM de SISMO de una ficha de contacto pasiva a un sistema de calificación activo por comportamiento. El código existente está bien estructurado: los 4 archivos target son independientes y sus puntos de inserción están claramente delimitados. No hay dependencias circulares nuevas — `crm_service.py` ya es importado por `loanbook.py` (para `normalizar_telefono`), y `loanbook_scheduler.py` ya importa `crm_service`. Los riesgos de colisión son bajos si se siguen las reglas de inserción identificadas.

La colección `acuerdos_pago` no existe aún — se crea como nueva. El router `radar.py` ya existe con 4 endpoints y los 2 nuevos se agregan ahí. El score multidimensional reemplaza completamente el score simple de `calcular_scores()` pero coexiste con `score_pago` y `estrella_nivel` (el planner debe decidir si los campos legacy se mantienen o deprecan — recomendación: mantener para compatibilidad con frontend).

**Primary recommendation:** Implementar en orden: (1) crm_service.py primero para que los otros archivos puedan importar las funciones nuevas, (2) loanbook_scheduler.py para calcular_dpd_todos + calcular_scores, (3) loanbook.py para el sync en entrega, (4) crm.py para los endpoints nuevos, (5) radar.py para los 2 endpoints de diagnóstico/arranque.

---

## Standard Stack

### Core (ya instalado — sin instalaciones nuevas necesarias)
| Biblioteca | Versión | Propósito |
|------------|---------|-----------|
| motor | 3.7.0 | Async MongoDB — ya integrado |
| FastAPI | 0.110.1 | Routers y endpoints — ya integrado |
| pydantic | 2.7.1 | Modelos de request — ya integrado |
| apscheduler | 3.10.4 | Scheduler CRON — ya integrado |
| python-dateutil | 2.9.0 | Cálculos de fecha — ya integrado |

**No se requieren instalaciones nuevas.** FASE 8-A es puramente código Python sobre el stack existente.

---

## Architecture Patterns

### Patrón MongoDB canónico (INAMOVIBLE)
```python
from database import db  # Motor async — NUNCA recrear conexión
```
Usado en todos los archivos target. `database.py` exporta `db` como `AsyncIOMotorClient[DB_NAME]`.

### Patrón de imports en loanbook_scheduler.py
El scheduler usa imports locales dentro de cada función async para evitar circular imports:
```python
async def calcular_dpd_todos() -> None:
    from database import db
    from services.event_bus_service import EventBusService
    from event_models import RoddosEvent
    from services.shared_state import handle_state_side_effects
```
**Los nuevos imports en calcular_dpd_todos() y calcular_scores() DEBEN seguir este patrón — NO poner imports al nivel del módulo.**

### Patrón de auth en routers
```python
from dependencies import get_current_user
current_user=Depends(get_current_user)
```
Todos los endpoints nuevos deben usar este patrón exacto (igual que los existentes en crm.py y radar.py).

### Patrón EventBus
```python
from services.event_bus_service import EventBusService
bus = EventBusService(db)
await bus.emit(RoddosEvent(
    source_agent="crm",
    event_type="...",  # DEBE estar en EVENT_TYPES de event_models.py
    actor=registrado_por,
    target_entity=loanbook_id,
    payload={...},
))
```

---

## Estado Actual de Cada Archivo Target

### 1. `backend/services/crm_service.py` (241 líneas)

**RESULTADO_VALIDOS actual (líneas 42-53):**
```python
RESULTADO_VALIDOS = {
    "contestó_pagará_hoy",
    "contestó_prometió_fecha",
    "contestó_no_pagará",
    "no_contestó",
    "número_equivocado",
    "respondió_pagará",
    "respondió_prometió_fecha",
    "visto_sin_respuesta",
    "no_entregado",
    "acuerdo_de_pago_firmado",   # ← ya existe una variante, diferente al nuevo "acuerdo_firmado"
}
```

**Funciones existentes:**
- `normalizar_telefono(telefono)` — líneas 16-40 — utilidad pura
- `upsert_cliente(db, telefono, datos)` — líneas 56-109 — crea o actualiza crm_clientes por telefono_principal
- `registrar_gestion(db, loanbook_id, canal, resultado, nota, autor, ptp_fecha)` — líneas 112-189 — escribe en gestiones_cartera + loanbook.gestiones[] + crm_clientes.gestiones[]
- `registrar_ptp(db, loanbook_id, ptp_fecha, ptp_monto, registrado_por)` — líneas 192-224
- `agregar_nota(db, cliente_id, nota, autor)` — líneas 227-241

**Campos actuales de `crm_clientes` al crear (upsert_cliente):**
`id, telefono_principal, nombre_completo, cedula, telefono_alternativo, direccion, barrio, ciudad, email, fecha_nacimiento, ocupacion, referencia_1, referencia_2, score_pago, estrella_nivel, score_historial[], dpd_actual, bucket_actual, gestiones[], wa_ultimo_mensaje, wa_ultimo_comprobante, notas[], alertas[], ptp_activo, ultima_interaccion, created_at, updated_at`

**CAMPOS FALTANTES para FASE 8-A** (no existen en upsert_cliente actual):
- `score_roddos` (nuevo — valor inicial 70)
- `etapa_cobro` (nuevo — valor inicial "preventivo")
- `loanbook_id` (necesario para vincular con loanbook desde crm_clientes)

**Punto de inserción — nuevas funciones a agregar al final del archivo:**
- `calcular_score_roddos(db, loan)` — función pura de cálculo (4 dimensiones)
- `upsert_cliente_desde_loanbook(db, loan)` — sync automático desde loanbook
- `crear_acuerdo(db, loanbook_id, datos, autor)` — nueva función para acuerdos_pago
- `actualizar_estado_acuerdo(db, acuerdo_id, estado)` — actualiza estado acuerdo

**Colisión potencial:** `"acuerdo_de_pago_firmado"` ya existe en RESULTADO_VALIDOS. El nuevo es `"acuerdo_firmado"`. Son distintos — ambos coexisten. El planner debe verificar que `registrar_gestion()` no tenga lógica especial para `"acuerdo_de_pago_firmado"` que cause confusión con el nuevo `"acuerdo_firmado"`. (Revisado: línea 129 tiene `tiene_ptp = "prometió" in resultado or resultado == "acuerdo_de_pago_firmado"` — el nuevo `"acuerdo_firmado"` NO disparará esta condición, lo cual es correcto para el nuevo flujo donde el acuerdo tiene su propia colección.)

### 2. `backend/routers/crm.py` (342 líneas)

**Endpoints existentes:**
- `GET /api/crm` — lista clientes con DPD y score on-the-fly (línea 94)
- `GET /api/crm/{id}` — perfil 360° (línea 177)
- `PUT /api/crm/{id}/datos` — editar contacto (línea 256)
- `POST /api/crm/{id}/nota` — nota inmutable (línea 289)
- `POST /api/crm/{id}/gestion` — registrar gestión (línea 306)
- `POST /api/crm/{id}/ptp` — compromiso de pago (línea 330)

**Imports actuales (líneas 1-12):**
```python
from services.crm_service import registrar_gestion, agregar_nota, registrar_ptp
```
Hay un `upsert_cliente` importado inline en `update_datos()` (línea 277). Los nuevos endpoints necesitan importar `crear_acuerdo`, `actualizar_estado_acuerdo` desde crm_service.

**Modelos Pydantic existentes:** DatosEditables, NotaCreate, GestionCreate, PTPCreate.

**Nuevos modelos Pydantic requeridos:**
- `AcuerdoCreate` — campos: tipo, condiciones, monto_acordado, fecha_inicio, fecha_limite, cuotas_acuerdo[]
- `EstadoAcuerdoUpdate` — campos: estado (activo|cumplido|incumplido|cancelado)

**Punto de inserción:** Añadir los 3 nuevos endpoints al final del archivo, después de `register_ptp`. Añadir los nuevos modelos en la sección `── Models ──`.

**Helper _compute_score en crm.py (líneas 47-63):** Este score simple (% cuotas a tiempo) sigue siendo usado en `list_crm_clientes()` y `get_crm_cliente()`. Para FASE 8-A NO se reemplaza aquí — el score multidimensional se calcula en el scheduler y se lee desde loanbook/crm_clientes. El `_compute_score` antiguo puede quedarse para compatibilidad del frontend, o el planner puede actualizar estas funciones para leer `score_roddos` desde el documento. **Recomendación:** Actualizar `list_crm_clientes()` para devolver `score_roddos` y `etapa_cobro` si existen en el loanbook (read del campo persistido).

### 3. `backend/routers/loanbook.py`

**Función `register_entrega` — líneas 1046-1290:**

Flujo actual al final de la función (líneas 1235-1289):
1. Emite evento `loanbook.activado` (línea 1237)
2. Emite evento `inventario.moto.entrada` (línea 1255)
3. Llama `await invalidar_cache_cfo()` (línea 1273)
4. Llama `await log_action(...)` (línea 1275)
5. Retorna el objeto loan

**Punto de inserción exacto para el sync CRM:**
Después de `await invalidar_cache_cfo()` (línea 1273) y ANTES de `await log_action(...)` (línea 1275). Código a insertar:

```python
# Sync CRM — crear/actualizar ficha en crm_clientes
try:
    from services.crm_service import upsert_cliente_desde_loanbook
    await upsert_cliente_desde_loanbook(db, loan)
except Exception as _crm_err:
    logger.warning("[register_entrega] CRM sync error (no bloqueante): %s", _crm_err)
```

**Por qué no bloqueante:** Si el sync CRM falla, el loanbook ya fue activado correctamente. La entrega no debe fallar por un error de CRM.

**Import necesario en loanbook.py:** `normalizar_telefono` ya está importado (línea 15). Solo se necesita importar `upsert_cliente_desde_loanbook` inline dentro de la función (patrón que ya existe en el router con `from services.crm_service import upsert_cliente` en línea 277 de crm.py — pero aquí es mejor import inline para evitar dependencia circular a nivel módulo).

**Colisión potencial:** El import de `from services.crm_service import normalizar_telefono` ya existe a nivel módulo (línea 15 de loanbook.py). Un import adicional de `upsert_cliente_desde_loanbook` a nivel módulo sería seguro, pero el import inline dentro de `register_entrega` es más conservador y sigue el patrón del scheduler.

### 4. `backend/services/loanbook_scheduler.py`

**`calcular_dpd_todos()` — líneas 102-204:**

Actualmente escribe en loanbook estos campos (líneas 157-165):
```python
update_fields = {
    "dpd_actual":             dpd_actual,
    "dpd_bucket":             bucket,
    "dpd_maximo_historico":   nuevo_dpd_max,
    "interes_mora_acumulado": round(interes_mora, 2),
    "updated_at":             now_iso,
}
if nuevo_estado != estado_actual:
    update_fields["estado"] = nuevo_estado
```

**Punto de inserción para `etapa_cobro`:** Agregar `"etapa_cobro": _calcular_etapa_cobro(dpd_actual, proxima_cuota_dias)` en `update_fields`. Necesita una nueva función helper `_calcular_etapa_cobro(dpd, dias_para_proxima)` que implemente la lógica de las 6 etapas. Para calcular `dias_para_proxima`, loanbook ya tiene las cuotas — se puede extraer del primer cuota pendiente con fecha futura.

**Advertencia:** `calcular_dpd_todos()` solo lee `"cuotas": 1` en la proyección (línea 117). Para calcular `proxima_cuota_dias` se necesita la fecha de la próxima cuota — los datos ya están en el campo `cuotas` que ya se está leyendo.

**`calcular_scores()` — líneas 377-467:**

Actualmente lee de loanbook: `dpd_actual, dpd_maximo_historico, cuotas, gestiones, cliente_nombre, cliente_telefono, ptp_fecha, ptp_monto`.

Escribe en loanbook: `score_pago` (letra A+..E), `estrella_nivel` (0-5), `score_historial` (append).

**Para FASE 8-A:** Necesita escribir adicionalmente `score_roddos` (número 0-100) y `etiqueta_roddos` (A+/A/B/C/D/E). También necesita actualizar `crm_clientes.score_roddos`.

**Campos adicionales requeridos en la proyección de `calcular_scores()`:**
- Para `dimension_velocidad`: fechas de pago de las últimas 5 cuotas pagadas (campo `fecha_pago` en cuotas)
- Para `dimension_trayectoria`: `dpd_hace_4_semanas` — este campo NO existe actualmente en loanbook

**Hallazgo crítico — `dpd_hace_4_semanas`:** No existe como campo persistido. Opciones:
1. Calcularlo leyendo `score_historial` del loanbook (tiene `dpd_actual` en cada entrada)
2. Agregar campo `dpd_snapshot_hace_4sem` que se actualiza cada vez que se calcula

**Recomendación:** Leer `score_historial` y buscar la entrada de hace ~28 días por `fecha`. Ya está siendo escrito por `calcular_scores()`. Esto no requiere campo nuevo. Lógica: filtrar `score_historial` donde `fecha` <= hace 28 días, tomar el más reciente, leer su `dpd_actual`.

**Para `dimension_gestion`:**
- `ptps_prometidos` = gestiones donde resultado contiene "prometió" o "acuerdo_de_pago_firmado" o nuevo "acuerdo_firmado"
- `ptps_cumplidos` = gestiones donde `ptp_fue_cumplido is True`
- `veces_contactado` = gestiones donde resultado no es "no_contestó" ni de los nuevos "sin_respuesta_72h"/"numero_apagado"/"bloqueo_detectado"
- `intentos_gestion` = len(gestiones)

Todos estos están en `loan.gestiones[]` — ya leídos en la proyección existente.

**Para `dimension_velocidad`:** Campo `fecha_pago` en cuotas pagadas. Este campo existe — se puede ver en `cartera_pagos` y en cuotas con `estado=pagada`. Verificar que `fecha_pago` esté en el subdocumento de cuotas en loanbook. (El scheduler ya lee `cuotas` completo — incluye `fecha_pago`.)

---

## Radar Router — Estado y Puntos de Inserción

**`backend/routers/radar.py` — YA EXISTE** con 4 endpoints:
- `GET /api/radar/portfolio-health` (línea 14)
- `GET /api/radar/queue` (línea 20)
- `GET /api/radar/semana` (línea 28)
- `GET /api/radar/roll-rate` (endpoint no mostrado en lectura parcial)

**Registrado en server.py:** `app.include_router(radar_router.router, prefix=PREFIX)` (línea 180)

**No se necesita crear nuevo archivo.** Los 2 nuevos endpoints (`GET /diagnostico`, `POST /arranque`) se agregan al final de `radar.py`.

**Sin embargo**, radar.py está listado como archivo INAMOVIBLE en el CONTEXT.md... Verificación:

> De CONTEXT.md: "Archivos INAMOVIBLES — No Tocar: backend/services/shared_state.py, backend/routers/conciliacion.py, backend/services/bank_reconciliation.py, backend/services/database.py, backend/dependencies.py, backend/services/alegra_service.py, **Cualquier router no mencionado en los 4 archivos objetivo**"

`radar.py` NO está en los 4 archivos objetivo (crm_service.py, crm.py, loanbook.py, loanbook_scheduler.py). Pero el CONTEXT.md también dice "2 en /api/radar/" para los endpoints nuevos.

**Resolución:** El CONTEXT.md dice "radar.py (o crm.py según conveniencia)" para los endpoints de radar. La opción segura es agregar los endpoints de `/api/radar/diagnostico` y `/api/radar/arranque` **en crm.py** como rutas con prefijo diferente, o usar `radar.py` y ampliarlo. Dado que el PRD dice explícitamente `/api/radar/`, y la regla dice "cualquier router no mencionado", la interpretación correcta es que `radar.py` sí debe modificarse — es el archivo correcto para rutas `/api/radar/`. El planner debe aclararlo en el plan, pero técnicamente es `radar.py`.

**Alternativa sin riesgo:** El planner podría agregar estos 2 endpoints en `crm.py` con paths `/api/crm/radar/diagnostico` y `/api/crm/radar/arranque`, pero rompe la URL esperada. La opción más limpia es agregar `radar.py` como 5to archivo modificado, declarándolo explícitamente.

---

## Don't Hand-Roll

| Problema | No construir | Usar en cambio |
|----------|-------------|----------------|
| Disparo async de jobs | No crear threads manuales | `asyncio.create_task()` (ya usado en crm_service línea 185) |
| Generación de IDs | No usar secuencias | `str(uuid.uuid4())` — patrón establecido |
| Normalización teléfonos | No duplicar lógica | `normalizar_telefono()` ya en crm_service |
| Conexión MongoDB | No recrear | `from database import db` |
| Autenticación endpoints | No crear auth propia | `Depends(get_current_user)` |
| Eventos bus | No llamar directamente | `EventBusService(db).emit(RoddosEvent(...))` |

---

## Common Pitfalls

### Pitfall 1: Import circular crm_service ↔ loanbook
**Qué falla:** Si `crm_service.py` importa algo de `loanbook.py` a nivel módulo (o viceversa), habrá circular import.
**Por qué pasa:** loanbook.py ya importa `normalizar_telefono` de crm_service. Si crm_service importa desde loanbook, hay ciclo.
**Cómo evitar:** `upsert_cliente_desde_loanbook(db, loan)` recibe el dict `loan` como parámetro — NO importa nada de loanbook. El import en register_entrega debe ser inline dentro de la función.

### Pitfall 2: score_pago vs score_roddos — colisión de campos
**Qué falla:** El campo `score_pago` (letra A+..E) y `estrella_nivel` (0-5) ya existen y el frontend los consume. Si se sobrescriben con la nueva lógica de etiquetas, el frontend puede romperse.
**Cómo evitar:** Escribir `score_roddos` como campo NUEVO (número 0-100) y `etiqueta_roddos` (A+..E nuevo sistema). Mantener `score_pago` y `estrella_nivel` intactos hasta que el frontend se actualice.

### Pitfall 3: RESULTADO_VALIDOS — colisión de nombres
**Qué falla:** `"acuerdo_de_pago_firmado"` (existente) vs `"acuerdo_firmado"` (nuevo). Son distintos en el set.
**Cómo evitar:** No renombrar el existente. Agregar los 6 nuevos tal como están definidos en CONTEXT.md.

### Pitfall 4: calcular_scores() proyección insuficiente
**Qué falla:** La proyección actual no incluye todos los campos necesarios para el score multidimensional (especialmente `fecha_pago` en cuotas y datos históricos).
**Cómo evitar:** Ampliar la proyección del `find()` en `calcular_scores()` para incluir `score_historial` (para dimension_trayectoria) y asegurarse de que las cuotas pagadas incluyan `fecha_pago`.

### Pitfall 5: etapa_cobro en calcular_dpd_todos — campo proxima_cuota
**Qué falla:** La etapa "preventivo" y "vencimiento_proximo" requieren saber cuántos días faltan para la próxima cuota. Si no hay cuota pendiente futura, el cálculo puede fallar.
**Cómo evitar:** Buscar la primera cuota con `estado in ("pendiente")` y `fecha_vencimiento > hoy_str`. Si no existe, usar `dias=999` (muy lejos = preventivo). Manejar loan sin cuotas (Contado o completado — no deberían llegar al query pero defensivo).

### Pitfall 6: acuerdos_pago — nueva colección sin índice
**Qué falla:** Sin índice en `loanbook_id`, las queries de GET /api/crm/{id}/acuerdos serán lentas.
**Cómo evitar:** Agregar un task en el plan para crear índice `{"loanbook_id": 1}` en `acuerdos_pago` en Wave 0 o Wave 1.

### Pitfall 7: register_entrega sync CRM no bloqueante
**Qué falla:** Si el sync CRM falla y no tiene try/except, bloquea la entrega del loanbook.
**Cómo evitar:** Siempre envolver el call a `upsert_cliente_desde_loanbook` en try/except con log warning.

### Pitfall 8: `dpd_hace_4_semanas` no existe como campo
**Qué falla:** `dimension_trayectoria` requiere comparar `dpd_actual` con dpd de hace 4 semanas. No hay campo dedicado.
**Cómo evitar:** Leer `score_historial` del loanbook y buscar entradas con fecha ~28 días atrás. Ya está disponible en el array. Si el array tiene menos de 28 días de historia → retornar 60 (neutro, "Sin historial").

---

## Code Examples

### Patrón tests estáticos (de test_fase5_vin_sync.py)
```python
from pathlib import Path

# Cargar código fuente una sola vez
CRM_SERVICE_SOURCE = (
    Path(__file__).parent.parent / "services" / "crm_service.py"
).read_text(encoding="utf-8")

def test_t1_nuevos_resultado_validos_presentes():
    """Los 6 nuevos RESULTADO_VALIDOS están en crm_service.py."""
    nuevos = [
        "sin_respuesta_72h", "bloqueo_detectado", "numero_apagado",
        "pago_parcial_reportado", "acuerdo_firmado", "disputa_deuda",
    ]
    for rv in nuevos:
        assert rv in CRM_SERVICE_SOURCE, f"Falta RESULTADO_VALIDO: {rv}"
```

### Patrón calcular_score_roddos (estructura base)
```python
async def calcular_score_roddos(db, loan: dict) -> dict:
    """Calcula score_roddos multidimensional. Retorna {"score_roddos": float, "etiqueta_roddos": str}."""
    dpd_actual = loan.get("dpd_actual", 0)
    dpd_max = loan.get("dpd_maximo_historico", 0)
    cuotas = loan.get("cuotas", [])
    gestiones = loan.get("gestiones", [])
    score_historial = loan.get("score_historial", [])

    # dimension_dpd (40%)
    # ... lógica exacta de CONTEXT.md ...

    # dimension_gestion (30%)
    # ... ratio_ptp y contactabilidad ...

    # dimension_velocidad (20%)
    # últimas 5 cuotas pagadas — campo fecha_pago vs fecha_vencimiento

    # dimension_trayectoria (10%)
    # buscar en score_historial la entrada de hace ~28 días

    score_roddos = round(
        (dim_dpd * 0.40) + (dim_gestion * 0.30) +
        (dim_velocidad * 0.20) + (dim_trayectoria * 0.10), 1
    )
    # Etiqueta
    if score_roddos >= 85: etiqueta = "A+"
    elif score_roddos >= 70: etiqueta = "A"
    elif score_roddos >= 55: etiqueta = "B"
    elif score_roddos >= 40: etiqueta = "C"
    elif score_roddos >= 25: etiqueta = "D"
    else: etiqueta = "E"
    return {"score_roddos": score_roddos, "etiqueta_roddos": etiqueta}
```

### Patrón etapa_cobro helper
```python
def _calcular_etapa_cobro(dpd: int, dias_proxima_cuota: int) -> str:
    if dpd == 0 and dias_proxima_cuota > 2:
        return "preventivo"
    if dpd == 0 and dias_proxima_cuota <= 2:
        return "vencimiento_proximo"
    if dpd <= 7:
        return "gestion_activa"
    if dpd <= 14:
        return "alerta_formal"
    if dpd <= 21:
        return "escalacion"
    return "recuperacion"
```

### Patrón tests con AsyncMock (para T4, T7, T9)
```python
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

@pytest.mark.asyncio
async def test_t4_sync_crm_al_entregar():
    """register_entrega llama upsert_cliente_desde_loanbook."""
    from services.crm_service import upsert_cliente_desde_loanbook
    mock_db = MagicMock()
    mock_db.crm_clientes.find_one = AsyncMock(return_value=None)
    mock_db.crm_clientes.insert_one = AsyncMock(return_value=None)
    loan = {
        "id": "lb-test-001",
        "cliente_nombre": "Juan Test",
        "cliente_telefono": "3001234567",
        "cliente_nit": "12345678",
    }
    result = await upsert_cliente_desde_loanbook(mock_db, loan)
    assert result["score_roddos"] == 70
    assert result["etapa_cobro"] == "preventivo"
```

---

## Dependencias Internas — Mapa de Imports

```
loanbook.py
  └─ from services.crm_service import normalizar_telefono  [ya existe línea 15]
  └─ from services.crm_service import upsert_cliente_desde_loanbook  [nuevo, inline]

loanbook_scheduler.py
  └─ from services.crm_service import normalizar_telefono  [ya existe línea 23]
  └─ from services.crm_service import calcular_score_roddos  [nuevo, inline en calcular_scores]
  └─ from database import db  [ya existe, inline en cada función]

crm.py
  └─ from services.crm_service import registrar_gestion, agregar_nota, registrar_ptp  [ya existe línea 11]
  └─ from services.crm_service import crear_acuerdo, actualizar_estado_acuerdo  [nuevo, al inicio]

radar.py
  └─ from services.loanbook_scheduler import calcular_dpd_todos, calcular_scores, generar_cola_radar  [nuevo]
  └─ from database import db  [ya existe]
```

**No hay dependencias circulares potenciales** si `crm_service.py` no importa desde loanbook, crm, radar, ni loanbook_scheduler. Verificado: el crm_service.py actual solo importa de `services.event_bus_service`, `event_models`, y `services.shared_state`.

---

## Environment Availability

Step 2.6: SKIPPED — FASE 8-A es puramente código Python sobre stack existente. No hay dependencias externas nuevas. MongoDB Atlas ya conectado, FastAPI ya corriendo. Sin nuevas variables de entorno requeridas.

---

## Colecciones MongoDB — Estado

| Colección | Estado | Acción Requerida |
|-----------|--------|-----------------|
| `crm_clientes` | Existe | Agregar campos `score_roddos`, `etapa_cobro`, `loanbook_id` en documentos nuevos |
| `gestiones_cartera` | Existe | Sin cambios de estructura |
| `acuerdos_pago` | NO EXISTE | Crear nueva — no requiere comando explícito en MongoDB (se crea al primer insert) |
| `loanbook` | Existe | Agregar campos `score_roddos`, `etiqueta_roddos`, `etapa_cobro` en updates |
| `roddos_events` | Existe | Solo lectura en `/api/radar/diagnostico` |

**Índice recomendado para acuerdos_pago:**
```python
await db.acuerdos_pago.create_index("loanbook_id")
await db.acuerdos_pago.create_index("estado")
```

---

## Validation Architecture

### Test Framework
| Propiedad | Valor |
|-----------|-------|
| Framework | pytest (ya instalado) |
| Config file | backend/pytest.ini o pyproject.toml — usar patrón existente |
| Quick run | `pytest backend/tests/test_fase8a_crm_robusto.py -v` |
| Full suite | `pytest backend/tests/test_fase8a_crm_robusto.py backend/tests/test_permissions.py backend/tests/test_event_bus.py -v` |

### Mapeo Tests T1–T10

| Test | Comportamiento | Tipo | Archivo target a verificar |
|------|---------------|------|---------------------------|
| T1 | score_roddos >= 85 → "A+" para cliente 10 cuotas a tiempo | Estático/puro (cálculo) | crm_service.py — función calcular_score_roddos |
| T2 | DPD=22, 3 PTPs incumplidos → score < 25 → "E" | Puro (cálculo) | crm_service.py |
| T3 | Cliente nuevo sin historial → score_roddos=70 → "B" | Puro (cálculo) | crm_service.py |
| T4 | POST /loanbook/{id}/entrega → crm_clientes creado con datos | AsyncMock | loanbook.py + crm_service.py |
| T5 | etapa_cobro="gestion_activa" cuando dpd=3 | Puro (helper) | loanbook_scheduler.py — _calcular_etapa_cobro |
| T6 | etapa_cobro="recuperacion" cuando dpd=22 | Puro (helper) | loanbook_scheduler.py — _calcular_etapa_cobro |
| T7 | POST /api/crm/{id}/acuerdo → crea en acuerdos_pago + gestión "acuerdo_firmado" | AsyncMock | crm.py + crm_service.py |
| T8 | GET /api/radar/diagnostico → 200 sin error 500 | Estático (source) o smoke | radar.py |
| T9 | POST /api/radar/arranque → triggerrea 3 jobs, retorna estado | AsyncMock | radar.py |
| T10 | calcular_scores() actualiza score_roddos y etapa_cobro en todos activos | AsyncMock | loanbook_scheduler.py |

### Estrategia de Tests Recomendada

**Tests T1, T2, T3, T5, T6** → Tests puros sin mocks. Las funciones de cálculo son puras (reciben dict, retornan resultado). No requieren MongoDB.

**Tests T4, T7, T10** → AsyncMock del objeto `db` (motor). Patrón: `MagicMock()` con métodos async como `AsyncMock`.

**Tests T8, T9** → Tests estáticos (análisis de código fuente) verificando que la función existe y tiene la estructura esperada, ó tests con TestClient de FastAPI si el equipo prefiere.

### Wave 0 Gaps
- [ ] `backend/tests/test_fase8a_crm_robusto.py` — no existe aún, se crea en Wave 0
- [ ] Crear índice en `acuerdos_pago` — task en Wave 1 o como parte de crm_service init

---

## Open Questions

1. **¿radar.py es el 5to archivo modificado?**
   - Lo que sabemos: los endpoints `/api/radar/diagnostico` y `/api/radar/arranque` deben estar en `/api/radar/`
   - Lo que está ambiguo: CONTEXT.md lista 4 archivos target pero estos endpoints requieren modificar radar.py
   - Recomendación: El planner debe declarar radar.py como 5to archivo a modificar explícitamente, dado que el PRD lo requiere y no hay alternativa limpia sin cambiar las URLs

2. **¿score_pago y estrella_nivel se deprecan?**
   - Lo que sabemos: el frontend usa `score_letra` (calculado on-the-fly en crm.py) y el scheduler usa `score_pago`/`estrella_nivel`
   - Lo que está ambiguo: ¿el frontend debe mostrar el nuevo `score_roddos` inmediatamente?
   - Recomendación: Mantener ambos sistemas en paralelo en FASE 8-A. La migración del frontend es FASE 8-C.

3. **¿`fecha_pago` existe en subdocumentos de cuotas en loanbook?**
   - Lo que sabemos: existe en colección `cartera_pagos`, y `_update_overdue()` en loanbook.py no establece `fecha_pago` explícitamente
   - Lo que está ambiguo: `register_pago()` en loanbook.py puede o no escribir `fecha_pago` en la cuota individual
   - Recomendación: Verificar en el código de `register_pago()` antes de implementar `dimension_velocidad`. Si no existe, usar `fecha_vencimiento` como proxy (conservador) o leer de `cartera_pagos`.

---

## Sources

### Primary (HIGH confidence — inspección directa de código)
- `backend/services/crm_service.py` — estado actual completo
- `backend/routers/crm.py` — endpoints existentes y modelos
- `backend/routers/loanbook.py` — register_entrega(), líneas 1046-1290
- `backend/services/loanbook_scheduler.py` — calcular_dpd_todos() y calcular_scores()
- `backend/routers/radar.py` — 4 endpoints existentes
- `backend/server.py` — registro de routers
- `backend/tests/test_fase5_vin_sync.py` — patrón tests estáticos

### Secondary (HIGH confidence — documentación del proyecto)
- `.planning/phases/08a-crm-robusto/08a-CONTEXT.md` — decisiones locked
- `SISMO_ENV_REGISTRY.md` — colecciones y variables de entorno

---

## Metadata

**Confidence breakdown:**
- Estado archivos target: HIGH — leídos directamente
- Puntos de inserción: HIGH — líneas exactas identificadas
- Colisiones potenciales: HIGH — verificadas en código
- Patrón de tests: HIGH — basado en test_fase5_vin_sync.py existente
- `dpd_hace_4_semanas` strategy: MEDIUM — solución propuesta via score_historial, no está en CONTEXT.md pero es la única opción sin campo nuevo

**Research date:** 2026-04-04
**Valid until:** 2026-05-04 (código estable, sin cambios de stack)

---

## RESEARCH COMPLETE
