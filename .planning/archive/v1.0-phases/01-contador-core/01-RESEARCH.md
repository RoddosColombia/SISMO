# Phase 1: Contador Core - Research

**Researched:** 2026-03-24
**Domain:** Python/FastAPI backend — contabilidad, event bus, cache, decomposicion de modulos
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Prioridad de Ejecucion (LOCKED — usuario definio orden)**
- P-01: PRIMERO: CONT-01 (fix proveedor extraction) — desbloquea la conciliacion bancaria
- P-02: SEGUNDO: CONT-06 (smoke test 20/20) — baseline de calidad ANTES de descomponer
- P-03: TERCERO: CONT-02 (decomposicion ai_chat.py) — refactoring seguro porque el smoke test ya valida
- P-04: CONT-03, CONT-04, CONT-05: en paralelo con CONT-02

**Reglas de Negocio Inviolables (LOCKED — zero tolerance)**
- R-01: NUNCA reportar exito sin verificar HTTP 200 en respuesta de Alegra
- R-02: Endpoint correcto para journals: `/journals` — NUNCA usar `/journal-entries` (retorna 403)
- R-03: IDs de cuentas contables SIEMPRE desde MongoDB coleccion `plan_cuentas_roddos` — nunca hardcoded
- R-04: Auteco NIT 860024781 = autoretenedor. NUNCA aplicar ReteFuente a Auteco

**CONT-00:** Auditar los 32 flujos del SVG contra codigo actual. Matriz de cobertura es entregable obligatorio. D-00d: completado cuando 32 flujos tienen estado Funcional.

**CONT-01:** Fix en `backend/services/bank_reconciliation.py`. Consolidar 4 bloques duplicados en una sola funcion helper.

**CONT-02:** Descomposicion incremental. Estructura objetivo:
- `backend/agents/contador_agent.py`
- `backend/agents/context_builder.py`
- `backend/agents/file_parser.py`
- `backend/agents/prompt_templates.py`
- `backend/ai_chat.py` queda como thin router/dispatcher
- Funciones se mueven tal cual (no refactorizar logica interna)
- Decomposicion DESPUES del smoke test 20/20

**CONT-03:** Esquema key: `{operacion}:{entity_type}:{hash_de_datos_unicos}`. Storage: MongoDB coleccion `idempotency_keys` con TTL index 7 dias. Implementar en `backend/alegra_service.py` como decorator/wrapper.

**CONT-04:** Coleccion MongoDB `dead_letter_queue`. Schema: `{event_id, event_type, payload, error, attempts, next_retry, created_at, resolved_at}`. Retry: max 5 con backoff 1min/5min/15min/1h/4h. Job en APScheduler cada minuto. Alerta via event bus al frontend.

**CONT-05:** Suscribir `shared_state.py` al event bus. Mapeo evento->cache keys. TTL 30s se mantiene como fallback.

**CONT-06:** Se ejecuta en Phase 1 como gate de calidad pre-decomposicion. 20 pasos con IDs reales de Alegra. Cada paso verifica HTTP 200.

### Claude's Discretion
- Nombres exactos de funciones internas y helpers
- Estructura de tests unitarios
- Nivel de logging y telemetria interna

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| CONT-00 | Mandato estrategico — cobertura total de 32 flujos contables RODDOS hacia Alegra via Agente Contador | Matriz de cobertura como entregable; SVG file pending |
| CONT-01 | Fix proveedor extraction en bank_reconciliation.py para activar 30+ reglas de clasificacion | 4 parsers identificados con bloques duplicados; `extract_proveedor` en accounting_engine ya funciona |
| CONT-02 | Decomposicion de ai_chat.py (5,217 lineas) en 4 modulos + thin router | Modulos destino identificados; directorio `backend/agents/` aun no existe |
| CONT-03 | Idempotency keys para todas las operaciones Alegra | AlegraService centralizado verificado; patron decorator/wrapper viable |
| CONT-04 | Dead-letter queue para webhooks Alegra fallidos con retry exponencial | APScheduler existente tiene patron de reintentos en `conciliacion_reintentos`; reusar logica |
| CONT-05 | Cache invalidation event-driven (invalidar inmediatamente al emitir evento) | `shared_state.py` tiene `_invalidate_keys()` y `_STATE_RULES` — ya parcialmente implementado para algunos eventos |
| CONT-06 | Smoke test 20/20 ciclo completo contable con IDs reales | `run_smoke_test.py` existe con 20 tests en 5 bloques; corre contra `sismo-backend.onrender.com` |
</phase_requirements>

---

## Summary

SISMO es un sistema FastAPI/Python con MongoDB que actua como cerebro operativo de RODDOS S.A.S., usando Alegra como libro legal contable. Esta fase elimina deuda tecnica critica que corrompe silenciosamente la contabilidad: un bug de propagacion de proveedor que desactiva 30+ reglas de clasificacion, un monolito de 5,217 lineas que es punto unico de falla, y ausencia de mecanismos de seguridad ante reintentos (idempotency, dead-letter queue).

El codigo existente revela que la arquitectura ya tiene las piezas fundamentales en su lugar: `accounting_engine.py` tiene `extract_proveedor()` y 50+ reglas de clasificacion, `shared_state.py` tiene `_invalidate_keys()` y un mapa parcial de evento->cache, `scheduler.py` tiene un patron de reintentos (en `conciliacion_reintentos`) que puede ser adaptado para dead-letter queue, y `alegra_service.py` centraliza todas las llamadas a Alegra. El trabajo es quirurgico: propagar lo que ya existe, no construir de cero.

La secuencia de ejecucion es inviolable: CONT-01 primero (desbloquea el flujo de mayor volumen), CONT-06 segundo (gate de calidad), CONT-02 tercero (decomposicion segura bajo smoke test), luego CONT-03/04/05 en paralelo. CONT-00 es transversal y debe completarse como auditoria antes o durante el trabajo.

**Primary recommendation:** Ejecutar en el orden P-01 → P-02 → P-03 → P-04 definido por el usuario. No hay alternativas — el orden protege contra regresiones.

---

## Standard Stack

### Core (ya instalado en el proyecto)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | current | Framework web async | Ya en produccion |
| Motor (PyMongo async) | current | MongoDB async driver | Ya en produccion, usado en todo el backend |
| APScheduler | current | Scheduler de jobs async | Ya en `scheduler.py` con 10+ jobs registrados |
| httpx | current | HTTP async client | Ya usado en `alegra_service.py` y webhooks |
| Anthropic | current | Claude SDK para agente | Ya en `ai_chat.py` |
| hashlib | stdlib | Generar hash para idempotency keys | stdlib, sin instalacion |

### No se necesitan dependencias nuevas
Todos los mecanismos de esta fase (dead-letter queue, idempotency, cache invalidation) usan MongoDB + APScheduler que ya estan en produccion. No hay paquetes nuevos que instalar.

---

## Architecture Patterns

### Estructura del proyecto (estado actual)
```
backend/
├── ai_chat.py                     # MONOLITO 5,217 lineas — objetivo CONT-02
├── alegra_service.py              # Cliente Alegra centralizado — objetivo CONT-03
├── event_bus.py                   # Bus append-only (emit_event) — base CONT-04/05
├── run_smoke_test.py              # Smoke test 20 pasos — objetivo CONT-06
├── agents/                        # NO EXISTE — crear para CONT-02
│   ├── contador_agent.py
│   ├── context_builder.py
│   ├── file_parser.py
│   └── prompt_templates.py
├── services/
│   ├── accounting_engine.py       # 50+ reglas + extract_proveedor — fuente CONT-01
│   ├── bank_reconciliation.py     # 4 parsers con bloques duplicados — objetivo CONT-01
│   ├── shared_state.py            # Cache TTL 30s + _invalidate_keys — objetivo CONT-05
│   └── scheduler.py               # APScheduler — base CONT-04
└── routers/
    ├── alegra_webhooks.py         # Webhooks Alegra — fuente eventos para DLQ
    └── conciliacion.py            # Conciliacion bancaria
```

### Estructura objetivo al final de Phase 1
```
backend/
├── ai_chat.py                     # Thin router/dispatcher (importa de agents/)
├── alegra_service.py              # + idempotency wrapper/decorator
├── agents/                        # NUEVO
│   ├── __init__.py
│   ├── contador_agent.py          # Tool calls, decision making
│   ├── context_builder.py         # Construccion de contexto (Alegra, MongoDB, loanbooks)
│   ├── file_parser.py             # Parsing extractos, facturas, documentos
│   └── prompt_templates.py        # System prompts y templates
├── services/
│   ├── bank_reconciliation.py     # + helper _extraer_proveedor_consolidado()
│   ├── shared_state.py            # + suscripcion al event bus para invalidation
│   └── scheduler.py               # + job dead_letter_retry cada 60s
└── (MongoDB collections nuevas)
    ├── idempotency_keys            # TTL 7 dias
    └── dead_letter_queue           # Schema DLQ
```

### Pattern 1: CONT-01 — Consolidacion de proveedor extraction

**Que:** Los 4 parsers de banco (Bancolombia, BBVA, Davivienda, Nequi) tienen bloques identicos de 3 lineas que llaman `extract_proveedor`. La deuda tecnica es de divergencia futura, no un bug de funcionalidad roto — el proveedor SI se extrae pero el codigo duplicado puede divergir.

**El bug real:** Segun STATE.md linea 73: "proveedor extraction bug activo en bank_reconciliation.py linea 357 — silently disables 30+ classification rules". Inspeccion del codigo muestra que `clasificar_movimiento` recibe `proveedor=mov.proveedor` correctamente (lineas 379/389). El bug puede ser sutilmente en que `mov.proveedor` queda como string vacio `""` cuando la descripcion no matchea ningun patron en `extract_proveedor`, lo que hace que las reglas que usan `proveedores` en su lista no hagan match. La funcion `extract_proveedor` retorna `desc[:30].lower()` como fallback — esto NO es el nombre real del proveedor y puede interferir con las reglas.

**Fix quirurgico:**
```python
# En bank_reconciliation.py — reemplazar los 4 bloques identicos con:
def _extraer_proveedor(descripcion: str) -> str:
    """Helper consolidado — unica fuente de verdad para extraccion de proveedor."""
    from services.accounting_engine import extract_proveedor
    return extract_proveedor(descripcion)

# En cada parser, una sola linea:
proveedor = _extraer_proveedor(descripcion)
```

**Nota:** El planner debe revisar el codigo de clasificacion para confirmar exactamente donde falla la propagacion antes de codificar el fix. El problema puede ser en el fallback `desc[:30]` que interfiere con reglas de proveedor.

### Pattern 2: CONT-02 — Decomposicion incremental de ai_chat.py

**Que:** ai_chat.py tiene 5,217 lineas. La decomposicion es por extraccion de grupos de funciones a nuevos modulos, sin cambiar la logica interna.

**Orden de extraccion seguro (un modulo a la vez, verificar smoke test entre cada uno):**

1. `prompt_templates.py` — extraer primero (solo strings/templates, sin dependencias complejas)
2. `file_parser.py` — extraer `_tabular_to_text`, `_is_tabular_file` y funciones de parsing
3. `context_builder.py` — extraer funciones que construyen contexto desde DB/Alegra
4. `contador_agent.py` — extraer la logica del agente (tool calls, decision making)
5. `ai_chat.py` queda como thin dispatcher que importa de los 4 modulos

**Pattern de extraccion:**
```python
# En ai_chat.py (antes)
def build_context_for_agent(db, loanbook_id):
    # 100 lineas de logica
    ...

# Despues del movimiento:
# backend/agents/context_builder.py
def build_context_for_agent(db, loanbook_id):
    # Las mismas 100 lineas SIN modificar
    ...

# backend/ai_chat.py (thin router)
from agents.context_builder import build_context_for_agent
```

**Regla de oro:** Si la funcion tiene `import` internos (dentro del cuerpo), moverlos al top del modulo nuevo. No cambiar ninguna otra logica.

### Pattern 3: CONT-03 — Idempotency Keys

**Que:** Antes de cada escritura a Alegra, verificar si la operacion ya fue ejecutada usando un hash deterministico.

**Esquema de key:** `{operacion}:{entity_type}:{hash_de_datos_unicos}`
- Ejemplo contacto: `create:contact:{sha256(nit + nombre)[:16]}`
- Ejemplo factura: `create:invoice:{sha256(contact_id + items_sorted + date)[:16]}`
- Ejemplo pago: `create:payment:{sha256(invoice_id + monto + fecha)[:16]}`

**Implementacion como decorator sobre AlegraService:**
```python
# backend/alegra_service.py
import hashlib

async def _check_idempotency(self, key: str) -> dict | None:
    """Retorna resultado previo si la key existe. None si es nueva."""
    existing = await self.db.idempotency_keys.find_one(
        {"key": key}, {"_id": 0}
    )
    return existing.get("result") if existing else None

async def _store_idempotency(self, key: str, result: dict) -> None:
    """Almacena resultado con TTL automatico (7 dias)."""
    await self.db.idempotency_keys.update_one(
        {"key": key},
        {"$set": {"key": key, "result": result, "created_at": datetime.now(timezone.utc)}},
        upsert=True,
    )
```

**MongoDB index requerido:**
```python
# TTL index — MongoDB elimina documentos automaticamente despues de 7 dias
await db.idempotency_keys.create_index(
    "created_at",
    expireAfterSeconds=604800  # 7 dias
)
# Index de busqueda rapida
await db.idempotency_keys.create_index("key", unique=True)
```

### Pattern 4: CONT-04 — Dead-Letter Queue

**El sistema ya tiene un patron similar:** `conciliacion_reintentos` en `scheduler.py` (lineas 210-324) implementa reintentos con backoff para journals de Alegra fallidos. La DLQ para webhooks puede seguir exactamente el mismo patron.

**Schema MongoDB `dead_letter_queue`:**
```python
{
    "event_id": str,           # UUID del evento original
    "event_type": str,         # Tipo de evento Alegra (new-invoice, etc.)
    "payload": dict,           # Payload completo del webhook
    "error": str,              # Ultimo error
    "attempts": int,           # Contador de intentos (0-5)
    "next_retry": datetime,    # Cuando procesar siguiente intento
    "created_at": datetime,
    "resolved_at": datetime | None,  # None si aun pendiente
    "status": str,             # "pending" | "failed" | "resolved"
}
```

**Backoff exponencial:** `[1, 5, 15, 60, 240]` minutos (1min, 5min, 15min, 1h, 4h)

**Job en scheduler (cada 60 segundos):**
```python
async def _process_dead_letter_queue() -> None:
    from database import db
    ahora = datetime.now(timezone.utc)
    items = await db.dead_letter_queue.find(
        {"status": "pending", "next_retry": {"$lte": ahora}}
    ).limit(20).to_list(20)
    # Para cada item: reintentar handler, actualizar attempts/next_retry o marcar resolved/failed
```

**Integracion con alegra_webhooks.py:** Cuando `procesar_evento_webhook` falla, en lugar de solo hacer log, insertar en `dead_letter_queue`.

### Pattern 5: CONT-05 — Cache Invalidation Event-Driven

**Estado actual:** `shared_state.py` YA tiene `_invalidate_keys()` y `_STATE_RULES` con mapeo evento->cache keys. La funcion `emit_state_change` ya invalida el cache para eventos de estado. **El problema es que `event_bus.emit_event()` NO invalida el cache** — solo inserta en MongoDB.

**Gap a cerrar:** Cuando se emite un evento via `event_bus.emit_event()` (no via `shared_state.emit_state_change()`), el cache no se invalida. Los dos sistemas de eventos son independientes.

**Fix:** Agregar invalidacion al `event_bus.emit_event()` o crear un mapa de evento->cache_keys en event_bus.py similar al que ya existe en shared_state.py:

```python
# backend/event_bus.py — agregar mapa de invalidacion
EVENT_CACHE_INVALIDATION: dict[str, list[str]] = {
    "pago.cuota.registrado":   ["loanbook:", "portfolio_health", "daily_queue:"],
    "factura.venta.creada":    ["moto:", "portfolio_health"],
    "asiento.contable.creado": ["portfolio_health"],
    # etc.
}

async def emit_event(db, source, event_type, payload, alegra_synced=False):
    # ... logica existente ...
    event = await db.roddos_events.insert_one(...)

    # NUEVO: invalidar cache inmediatamente
    from services.shared_state import _invalidate_keys
    keys = EVENT_CACHE_INVALIDATION.get(event_type, [])
    if keys:
        _invalidate_keys(keys)

    return event
```

### Anti-Patterns a Evitar

- **Big-bang decomposition:** No mover todo ai_chat.py de una vez. Un modulo a la vez, smoke test entre cada movimiento.
- **Refactorizar durante la extraccion:** CONT-02 es separacion pura. No "mejorar" funciones mientras se mueven.
- **Idempotency key no deterministica:** El hash DEBE producir el mismo resultado con los mismos datos. Usar sorted() en listas antes de hashear.
- **Dead-letter sin limite:** Sin max_attempts el scheduler puede intentar para siempre. Max 5 intentos es inviolable.
- **Cache invalidation circular:** `_invalidate_keys` desde `emit_event` puede crear imports circulares entre `event_bus.py` y `shared_state.py`. Solucionar con import lazy o moviendo `_invalidate_keys` a un modulo neutral.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| TTL en MongoDB | Logica Python para limpiar docs viejos | MongoDB TTL index (`expireAfterSeconds`) | MongoDB limpia automaticamente; sin cron |
| Scheduling de reintentos | Timer manual en Python | APScheduler ya en `scheduler.py` | Ya configurado, con max_instances=1 para evitar solapamiento |
| Hash deterministico | UUID aleatorio | `hashlib.sha256()` sobre datos canonicos | UUID cambia en cada llamada — rompe idempotencia |
| Import circular prevention | Arquitectura compleja | Import lazy `from module import X` dentro de funciones | Ya usado en todo el codebase (ver `scheduler.py` lineas 46, 101) |

**Key insight:** El proyecto ya tiene patrones establecidos para todos estos problemas. El trabajo es aplicar los patrones existentes, no inventar nuevos.

---

## Runtime State Inventory

> Esta seccion aplica porque hay cambios de estructura (nuevo directorio `agents/`, nuevas colecciones MongoDB).

| Category | Items Found | Action Required |
|----------|-------------|------------------|
| Stored data | MongoDB collections existentes: `roddos_events`, `conciliacion_reintentos`, `conciliacion_movimientos_procesados` | Nuevas colecciones `idempotency_keys` y `dead_letter_queue` se crean en runtime al primer insert; crear indexes en startup |
| Live service config | APScheduler en produccion con 10+ jobs registrados | Agregar nuevo job `dead_letter_retry` sin remover jobs existentes |
| OS-registered state | Render.com deployment — backend desplegado en `sismo-backend-40ca.onrender.com` | Ningun cambio de registro OS; solo deploy de nuevo codigo |
| Secrets/env vars | `ALEGRA_EMAIL`, `ALEGRA_TOKEN` — usados directamente en bank_reconciliation.py (modo background). Idempotency no requiere nuevas vars. | No se necesitan nuevas variables de entorno |
| Build artifacts | `backend/agents/` directorio nuevo | Crear con `__init__.py` vacio; asegurar que imports relativos funcionen |

**Nada encontrado que requiera migracion de datos** — las nuevas colecciones (`idempotency_keys`, `dead_letter_queue`) empiezan vacias y se auto-populan.

---

## Common Pitfalls

### Pitfall 1: Imports circulares en decomposicion ai_chat.py
**What goes wrong:** `contador_agent.py` importa de `context_builder.py`, que importa de `alegra_service.py`, que importa de `database.py`. Si `ai_chat.py` importa de todos a la vez, Python puede encontrar ciclos.
**Why it happens:** ai_chat.py usa imports internos (dentro de funciones) como defense mechanism. Al extraer a modulos separados, estos imports internos se vuelven top-level.
**How to avoid:** Mantener imports lazy (dentro de funciones) en los modulos nuevos hasta que se confirme que no hay ciclos. Verificar con `python -c "from agents.contador_agent import X"`.
**Warning signs:** `ImportError: cannot import name X from partially initialized module`

### Pitfall 2: Hash no deterministico rompe idempotency
**What goes wrong:** `create:invoice:{hash}` produce distinto hash para la misma factura porque los items llegan en distinto orden.
**Why it happens:** Python dicts/lists no tienen orden garantizado en serializacion naive.
**How to avoid:** Antes de hashear: `json.dumps(sorted_data, sort_keys=True, ensure_ascii=False)`. Para listas de items: `sorted(items, key=lambda x: x['id'])`.
**Warning signs:** Duplicados en Alegra a pesar de tener idempotency implementado.

### Pitfall 3: Dead-letter queue crece infinitamente si no hay cleanup
**What goes wrong:** Items con status="failed" (5 intentos agotados) se acumulan en MongoDB indefinidamente.
**Why it happens:** Solo se define cuando mover a "failed", no cuando limpiar.
**How to avoid:** Agregar TTL index de 30 dias sobre `created_at` en `dead_letter_queue`. Items fallidos se auto-limpian.
**Warning signs:** Coleccion `dead_letter_queue` con miles de documentos.

### Pitfall 4: Smoke test 20/20 corre contra produccion real
**What goes wrong:** T07 crea una factura real en Alegra con VIN `9FL25AF31VDB95058`. T12 registra nomina real. Si se corre multiples veces, crea data sucia en Alegra.
**Why it happens:** El smoke test usa `sismo-backend-40ca.onrender.com` (produccion) y crea registros reales.
**How to avoid:** Verificar que idempotency keys (CONT-03) esten activas antes de correr el smoke test multiples veces. Si no, limpiar data de prueba en Alegra manualmente entre runs.
**Warning signs:** Multiples facturas con el mismo VIN en Alegra.

### Pitfall 5: Cache invalidation circular entre event_bus.py y shared_state.py
**What goes wrong:** `event_bus.py` importa `_invalidate_keys` de `shared_state.py`, que importa `emit_event` de `event_bus.py`.
**Why it happens:** Los dos modulos necesitan funcionalidad del otro.
**How to avoid:** Usar import lazy dentro de `emit_event`: `from services.shared_state import _invalidate_keys` dentro del cuerpo de la funcion, no al top del archivo. Este patron ya es estandar en el proyecto (ver `scheduler.py` linea 46).
**Warning signs:** `ImportError` o `circular import` al arrancar el servidor.

### Pitfall 6: CONT-00 bloqueado si SVG no esta disponible
**What goes wrong:** La auditoria de 32 flujos (CONT-00) requiere `Flujos_contables_Roddos.svg` que segun CONTEXT.md "NO esta en el repo aun".
**Why it happens:** El archivo debe ser agregado manualmente antes de iniciar CONT-00.
**How to avoid:** Agregar el SVG al repo como primer paso de CONT-00. Si no esta disponible, usar la descripcion de las 4 categorias del CONTEXT.md como proxy inicial.
**Warning signs:** Error 404 al intentar leer el SVG desde el directorio del proyecto.

---

## Code Examples

### Idempotency key generation (deterministic)
```python
# Source: logica derivada del esquema definido en CONTEXT.md D-03
import hashlib
import json

def generar_idempotency_key(operacion: str, entity_type: str, datos: dict) -> str:
    """Genera key deterministica para idempotency check."""
    # Serializar con orden garantizado
    datos_canonicos = json.dumps(datos, sort_keys=True, ensure_ascii=False)
    hash_datos = hashlib.sha256(datos_canonicos.encode()).hexdigest()[:16]
    return f"{operacion}:{entity_type}:{hash_datos}"

# Uso:
key_contacto = generar_idempotency_key(
    "create", "contact",
    {"nit": "860024781", "nombre": "Auteco"}
)
# → "create:contact:a3f8e2b1c4d5e6f7"
```

### Dead-letter queue insert on webhook failure
```python
# Source: patron derivado de conciliacion_reintentos en scheduler.py
from datetime import datetime, timezone, timedelta

BACKOFF_MINUTES = [1, 5, 15, 60, 240]  # 1min, 5min, 15min, 1h, 4h

async def mover_a_dead_letter(db, event_id: str, event_type: str, payload: dict, error: str):
    """Inserta evento fallido en dead_letter_queue."""
    await db.dead_letter_queue.insert_one({
        "event_id": event_id,
        "event_type": event_type,
        "payload": payload,
        "error": error,
        "attempts": 1,
        "next_retry": datetime.now(timezone.utc) + timedelta(minutes=BACKOFF_MINUTES[0]),
        "created_at": datetime.now(timezone.utc),
        "resolved_at": None,
        "status": "pending",
    })
```

### MongoDB index creation at startup
```python
# Source: patron estandar Motor/PyMongo para TTL indexes
async def crear_indexes_fase1(db) -> None:
    """Crear indexes para nuevas colecciones de Phase 1."""
    # idempotency_keys: TTL 7 dias + unique lookup
    await db.idempotency_keys.create_index("created_at", expireAfterSeconds=604800)
    await db.idempotency_keys.create_index("key", unique=True)

    # dead_letter_queue: TTL 30 dias para cleanup automatico
    await db.dead_letter_queue.create_index("created_at", expireAfterSeconds=2592000)
    # Index para el scheduler job
    await db.dead_letter_queue.create_index([("status", 1), ("next_retry", 1)])
```

### Cache invalidation from event_bus (lazy import)
```python
# Source: patron de import lazy ya establecido en scheduler.py linea 46
async def emit_event(db, source, event_type, payload, alegra_synced=False):
    # ... codigo existente de insercion ...

    # Invalidar cache inmediatamente (lazy import previene circular)
    from services.shared_state import _invalidate_keys
    keys_to_invalidate = EVENT_CACHE_INVALIDATION.get(event_type, [])
    if keys_to_invalidate:
        _invalidate_keys(keys_to_invalidate)

    return event
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Alegra `/journal-entries` endpoint | `/journals` endpoint exclusivamente | Aprendido en produccion (R-02) | `/journal-entries` retorna 403 — constraint hard |
| IDs de cuentas hardcoded | Solo desde `plan_cuentas_roddos` MongoDB (R-03) | Aprendido en produccion | IDs hardcoded rompen cuando Alegra cambia numeracion |
| ReteFuente aplicada a todos | Auteco NIT 860024781 excluido explicitamente (R-04) | Aprendido en produccion | Auteco es autoretenedor — aplicar ReteFuente es error legal |
| ai_chat.py monolito | Modulos separados por responsabilidad | Phase 1 (objetivo) | Puntos de falla aislados, tests unitarios posibles |

**Deprecated/outdated:**
- `conciliacion_reintentos`: La coleccion existente maneja reintentos de journals. La nueva `dead_letter_queue` es para webhooks Alegra. Son complementarias, no reemplazos.

---

## Open Questions

1. **Bug exacto de CONT-01**
   - What we know: STATE.md dice "bug en linea 357". Inspeccion muestra que `proveedor` SI se pasa a `clasificar_movimiento` en lineas 379/389. `extract_proveedor` devuelve `desc[:30].lower()` como fallback.
   - What's unclear: Si el fallback `desc[:30]` esta causando matches incorrectos en reglas de proveedor, o si hay otra ruta de codigo donde `proveedor` queda vacio.
   - Recommendation: El implementador debe verificar con un `print(mov.proveedor)` debug o log temporal antes del fix para confirmar el valor real que llega a `clasificar_movimiento`.

2. **SVG Flujos_contables_Roddos.svg no esta en el repo**
   - What we know: CONTEXT.md confirma que el archivo "NO esta en el repo aun". CONT-00 depende de el.
   - What's unclear: Cuando se agrega y si contiene exactamente 32 flujos o puede diferir.
   - Recommendation: El primer task de CONT-00 debe ser "Obtener y agregar SVG al repo". Si no esta disponible en el momento de planear, hacer la auditoria basada en las 4 categorias descritas en CONTEXT.md D-00c como fallback.

3. **Modelo de descomposicion de ai_chat.py**
   - What we know: 5,217 lineas. Tiene imports lazy internos (`from X import Y` dentro de funciones). Tiene helpers como `_safe_num`, `_safe_str`, `_tabular_to_text` claramente extraibles.
   - What's unclear: Cuantas funciones tiene exactamente y cuales son las dependencias entre ellas. El smoke test protege regresiones funcionales pero no descubre dependencias ocultas.
   - Recommendation: El implementador debe hacer `grep -n "^def \|^async def \|^class "` en ai_chat.py para mapear todas las funciones antes de iniciar la extraccion.

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| MongoDB (Motor async) | CONT-03/04/05 nuevas colecciones | Asumido (ya en produccion) | current | — |
| APScheduler | CONT-04 dead-letter retry job | Confirmado en scheduler.py | current | — |
| Alegra API `/journals` | CONT-06 smoke test | Asumido (ya en produccion) | v1 | — |
| Python hashlib | CONT-03 idempotency keys | stdlib, siempre disponible | stdlib | — |
| `Flujos_contables_Roddos.svg` | CONT-00 auditoria | NO disponible en repo | — | Usar categorias D-00c como proxy |

**Missing dependencies con fallback:**
- SVG de flujos contables: fallback es usar las 4 categorias textuales del CONTEXT.md para la auditoria inicial.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | run_smoke_test.py (requests, script custom) — no pytest detectado |
| Config file | No existe — smoke test es script standalone |
| Quick run command | `python backend/run_smoke_test.py` |
| Full suite command | `python backend/run_smoke_test.py` (mismo, corre los 20 tests) |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| CONT-00 | 32 flujos tienen path a Alegra | manual | Revisar matriz de cobertura | Entregable es documento, no test |
| CONT-01 | Proveedor extraido activa reglas de clasificacion | integration | `python backend/run_smoke_test.py` (T01-T04 cubren clasificacion) | Existente |
| CONT-02 | Sistema funciona identicamente tras decomposicion | smoke | `python backend/run_smoke_test.py` (20/20) | Existente |
| CONT-03 | Reintento no crea duplicado en Alegra | integration | T13 en smoke test (POST nomina → 409) | Existente |
| CONT-04 | Webhook fallido llega a DLQ y se reintenta | integration | Test manual: simular webhook con error + verificar en MongoDB | Wave 0 gap |
| CONT-05 | Cache invalida inmediatamente tras evento | unit | Test unitario en shared_state — verificar `_cache` vacio tras emit | Wave 0 gap |
| CONT-06 | 20/20 tests pasan con IDs reales Alegra | smoke | `python backend/run_smoke_test.py` | Existente |

### Sampling Rate
- **Per task commit:** `python backend/run_smoke_test.py` — verificar que los tests afectados por el task pasan
- **Per wave merge:** `python backend/run_smoke_test.py` — 20/20 green
- **Phase gate:** 20/20 green antes de marcar Phase 1 como completada

### Wave 0 Gaps
- [ ] Test unitario para CONT-04: `backend/tests/test_dead_letter_queue.py` — verificar insert en DLQ cuando handler falla, y que retry job procesa items pendientes
- [ ] Test unitario para CONT-05: `backend/tests/test_cache_invalidation.py` — verificar que `_cache` se vacia inmediatamente tras `emit_event` con evento registrado

*(El smoke test existente cubre CONT-01, CONT-02, CONT-03, CONT-06. No hay pytest configurado — los tests de Wave 0 pueden ser scripts simples al estilo del smoke test existente.)*

---

## Sources

### Primary (HIGH confidence)
- Codigo fuente directamente leido: `backend/services/bank_reconciliation.py` — 4 parsers con bloques duplicados confirmados
- Codigo fuente directamente leido: `backend/services/shared_state.py` — `_invalidate_keys`, `_STATE_RULES`, y `emit_state_change` verificados
- Codigo fuente directamente leido: `backend/event_bus.py` — `emit_event` no invalida cache confirmado
- Codigo fuente directamente leido: `backend/services/scheduler.py` — patron `conciliacion_reintentos` confirmado como base para DLQ
- Codigo fuente directamente leido: `backend/alegra_service.py` — estructura centralizada confirmada, sin idempotency actual
- Codigo fuente directamente leido: `backend/services/accounting_engine.py` — 50+ reglas y `extract_proveedor` verificados
- Codigo fuente directamente leido: `backend/run_smoke_test.py` — 20 tests en 5 bloques confirmados

### Secondary (MEDIUM confidence)
- `.planning/phases/01-contador-core/01-CONTEXT.md` — decisiones del usuario verificadas contra codigo
- `.planning/STATE.md` — blockers y estado del proyecto

### Tertiary (LOW confidence)
- Ninguna — toda la investigacion es sobre codigo local, no fuentes externas

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — todo el stack ya esta en produccion, no hay incertidumbre
- Architecture: HIGH — codigo leido directamente, patrones confirmados
- Pitfalls: HIGH para los identificados en codigo; MEDIUM para el bug exacto de CONT-01 (requiere debug en runtime)
- CONT-00: MEDIUM — no se puede completar la auditoria sin el SVG

**Research date:** 2026-03-24
**Valid until:** 2026-04-24 (30 dias — stack estable, sin dependencias de terceros cambiantes en esta fase)
