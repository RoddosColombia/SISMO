---
phase: 08a-crm-robusto
plan: 01
type: execute
wave: 1
depends_on: []
files_modified:
  - backend/services/crm_service.py
  - backend/services/loanbook_scheduler.py
  - backend/routers/loanbook.py
  - backend/routers/crm.py
  - backend/routers/radar.py
  - backend/tests/test_fase8a_crm_robusto.py
autonomous: true
requirements:
  - CRM-8A-01
  - CRM-8A-02
  - CRM-8A-03
  - CRM-8A-04
  - CRM-8A-05
  - CRM-8A-06

must_haves:
  truths:
    - "score_roddos multidimensional (4 dimensiones, pesos exactos) se calcula en calcular_scores() y persiste en loanbook"
    - "etapa_cobro (6 valores) se calcula en calcular_dpd_todos() y persiste en loanbook"
    - "Al activar entrega de un loanbook, crm_clientes se crea/actualiza con score_roddos=70, etapa_cobro=preventivo"
    - "POST /api/crm/{id}/acuerdo crea un documento en acuerdos_pago y registra gestion acuerdo_firmado"
    - "GET /api/radar/diagnostico retorna estado de loanbooks, scores y ultimo run de schedulers"
    - "POST /api/radar/arranque dispara calcular_dpd_todos + calcular_scores + generar_cola_radar via BackgroundTasks y retorna job_id"
    - "Los 10 tests T1-T10 pasan en verde"
  artifacts:
    - path: "backend/services/crm_service.py"
      provides: "calcular_score_roddos(), upsert_cliente_desde_loanbook(), crear_acuerdo(), actualizar_estado_acuerdo() + 6 RESULTADO_VALIDOS nuevos"
      contains: "acuerdo_firmado"
    - path: "backend/services/loanbook_scheduler.py"
      provides: "etapa_cobro en calcular_dpd_todos(), score_roddos + etiqueta_roddos en calcular_scores()"
      contains: "_calcular_etapa_cobro"
    - path: "backend/routers/loanbook.py"
      provides: "sync CRM no bloqueante en register_entrega() via inline import"
      contains: "upsert_cliente_desde_loanbook"
    - path: "backend/routers/crm.py"
      provides: "3 endpoints acuerdos_pago"
      contains: "AcuerdoCreate"
    - path: "backend/routers/radar.py"
      provides: "GET /diagnostico + POST /arranque"
      contains: "arranque"
    - path: "backend/tests/test_fase8a_crm_robusto.py"
      provides: "10 tests T1-T10 todos GREEN"
      contains: "test_t10"
  key_links:
    - from: "backend/routers/loanbook.py::register_entrega()"
      to: "backend/services/crm_service.py::upsert_cliente_desde_loanbook()"
      via: "inline import dentro de register_entrega, try/except no bloqueante"
      pattern: "upsert_cliente_desde_loanbook"
    - from: "backend/services/loanbook_scheduler.py::calcular_scores()"
      to: "backend/services/crm_service.py::calcular_score_roddos()"
      via: "inline import dentro de calcular_scores"
      pattern: "calcular_score_roddos"
    - from: "backend/routers/crm.py::POST acuerdo"
      to: "backend/services/crm_service.py::crear_acuerdo() + registrar_gestion()"
      via: "import a nivel modulo en crm.py"
      pattern: "crear_acuerdo"
    - from: "backend/routers/radar.py::POST arranque"
      to: "backend/services/loanbook_scheduler.py::calcular_dpd_todos(), calcular_scores()"
      via: "BackgroundTasks + inline import"
      pattern: "calcular_dpd_todos"
---

<objective>
Convertir el CRM de SISMO de ficha de contacto pasiva a sistema de calificacion activo por comportamiento.

Purpose: RADAR IA (FASE 8-C) requiere datos de calidad para razonar. Sin score_roddos multidimensional, etapa_cobro persistida, y acuerdos_pago formales, el agente RADAR no tiene con que trabajar.

Output:
- crm_service.py ampliado con 4 funciones nuevas + 6 RESULTADO_VALIDOS
- loanbook_scheduler.py con etapa_cobro en CRON-1 y score_roddos en CRON-4
- loanbook.py con sync CRM no bloqueante al activar entrega
- crm.py con 3 endpoints de acuerdos_pago
- radar.py con GET /diagnostico y POST /arranque
- 10 tests GREEN en test_fase8a_crm_robusto.py
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/phases/08a-crm-robusto/08a-CONTEXT.md
@.planning/phases/08a-crm-robusto/08a-RESEARCH.md
</context>

<interfaces>
<!-- Contratos exactos que el ejecutor necesita. Extraidos del codigo fuente. -->

De backend/services/crm_service.py (lineas 42-53) — RESULTADO_VALIDOS actual:
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
    "acuerdo_de_pago_firmado",   # ← ya existe, diferente al nuevo "acuerdo_firmado"
}
```

De backend/services/loanbook_scheduler.py — calcular_dpd_todos() update_fields (~linea 157):
```python
update_fields: dict = {
    "dpd_actual":             dpd_actual,
    "dpd_bucket":             bucket,
    "dpd_maximo_historico":   nuevo_dpd_max,
    "interes_mora_acumulado": round(interes_mora, 2),
    "updated_at":             now_iso,
}
```
<!-- Agregar "etapa_cobro": _calcular_etapa_cobro(dpd_actual, proxima_cuota_dias) aqui -->

De backend/services/loanbook_scheduler.py — calcular_scores() write (~linea 442):
```python
await db.loanbook.update_one(
    {"id": loan_id},
    {
        "$set": {"score_pago": score, "estrella_nivel": estrellas, "updated_at": now_iso},
        "$push": {"score_historial": score_entry},
    },
)
```
<!-- Agregar "score_roddos" y "etiqueta_roddos" al $set — NO tocar score_pago ni estrella_nivel -->

De backend/routers/loanbook.py — final de register_entrega() (~linea 1272-1275):
```python
    await invalidar_cache_cfo()      # linea 1273
    # <<< INSERTAR SYNC CRM AQUI (try/except no bloqueante) >>>
    await log_action(current_user, ...) # linea 1275
```

De backend/routers/radar.py — imports existentes:
```python
from fastapi import APIRouter, Depends
from database import db
from dependencies import get_current_user
from services.shared_state import get_portfolio_health, get_daily_collection_queue
router = APIRouter(prefix="/radar", tags=["radar"])
```

De backend/routers/crm.py — imports existentes (linea 11):
```python
from services.crm_service import registrar_gestion, agregar_nota, registrar_ptp
```
<!-- Agregar crear_acuerdo, actualizar_estado_acuerdo a este import -->

Patron inline import en scheduler (OBLIGATORIO para evitar circular imports):
```python
async def calcular_dpd_todos() -> None:
    from database import db                           # ya existe
    from services.event_bus_service import EventBusService  # ya existe
    # Agregar inline:
    from services.crm_service import calcular_score_roddos  # INLINE OBLIGATORIO
```
</interfaces>

<tasks>

<!-- ═══════════════════════════════════════════════════════════════════
     WAVE 1 — FOUNDATION: crm_service.py primero (base de todo lo demas)
     ═══════════════════════════════════════════════════════════════════ -->

<task type="auto" tdd="true">
  <name>Task 1: Ampliar crm_service.py — RESULTADO_VALIDOS + 4 funciones nuevas</name>
  <files>backend/services/crm_service.py</files>
  <behavior>
    - Los 6 nuevos valores estan en RESULTADO_VALIDOS: "sin_respuesta_72h", "bloqueo_detectado", "numero_apagado", "pago_parcial_reportado", "acuerdo_firmado", "disputa_deuda"
    - "acuerdo_de_pago_firmado" (existente) NO se toca — coexiste con el nuevo "acuerdo_firmado"
    - calcular_score_roddos(db, loan: dict) -> dict retorna {"score_roddos": float, "etiqueta_roddos": str}
    - dimension_dpd usa exactamente los 6 umbrales de CONTEXT.md (0/80/60/40/20/0)
    - dimension_gestion: ratio_ptp * 0.6 + contactabilidad * 0.4
    - dimension_velocidad: promedio de las ultimas 5 cuotas pagadas segun dias entre fecha_pago y fecha_vencimiento
    - dimension_trayectoria: lee score_historial[] buscando entrada con fecha <= hace 28 dias; si no hay historia retorna 60 (neutro)
    - score_roddos = round(dim_dpd*0.40 + dim_gestion*0.30 + dim_velocidad*0.20 + dim_trayectoria*0.10, 1)
    - Etiquetas: >=85 A+, >=70 A, >=55 B, >=40 C, >=25 D, <25 E
    - upsert_cliente_desde_loanbook(db, loan: dict): crea/actualiza crm_clientes con loanbook_id, score_roddos=70, etapa_cobro="preventivo"; usa upsert_cliente() existente internamente; NO importa nada de loanbook.py
    - crear_acuerdo(db, loanbook_id: str, datos: dict, autor: str) -> dict: inserta en acuerdos_pago con id=uuid4(), estado="activo", created_at=now; retorna el documento creado
    - actualizar_estado_acuerdo(db, acuerdo_id: str, estado: str) -> dict: hace update_one en acuerdos_pago por id, retorna documento actualizado
  </behavior>
  <action>
Agregar al final de backend/services/crm_service.py (despues de la funcion agregar_nota):

1. Expandir RESULTADO_VALIDOS agregando los 6 valores nuevos al set existente. NO crear un set nuevo — agregar al existente en lineas 42-53.

2. Agregar funcion privada helper `_puntuar_velocidad(dias: int) -> int` que implementa la tabla de velocidad de CONTEXT.md: 0 dias=100, 1-2=85, 3-7=65, 8-14=40, >14=15.

3. Agregar `async def calcular_score_roddos(db, loan: dict) -> dict` con las 4 dimensiones exactas de CONTEXT.md:
   - dimension_dpd: evalua dpd_actual y dpd_maximo_historico con los 6 umbrales
   - dimension_gestion: ptps_prometidos (gestiones donde resultado contiene "prometio" OR == "acuerdo_de_pago_firmado" OR == "acuerdo_firmado"), ptps_cumplidos (ptp_fue_cumplido is True), veces_contactado (resultado NOT IN {"no_contesto", "sin_respuesta_72h", "numero_apagado", "bloqueo_detectado", "no_entregado"}), intentos_gestion=len(gestiones)
   - dimension_velocidad: ultimas 5 cuotas con estado=="pagada" ordenadas por fecha_pago desc; para cada una calcular (date.fromisoformat(fecha_pago) - date.fromisoformat(fecha_vencimiento)).days clamped a 0 minimo; promediar con _puntuar_velocidad; si no hay cuotas pagadas retornar 60
   - dimension_trayectoria: filtrar score_historial donde fecha <= (hoy - 28 dias).isoformat(), tomar el mas reciente (sort desc), leer su dpd_actual como dpd_hace_4sem; si mejoro >3 retorna 100, estable <3 retorna 60, empeoro >3 retorna 20; sin historial retorna 60
   - Calcular etiqueta_roddos con los 6 umbrales de CONTEXT.md

4. Agregar `async def upsert_cliente_desde_loanbook(db, loan: dict) -> dict`:
   - Extraer telefono=normalizar_telefono(loan.get("cliente_telefono",""))
   - Si no hay telefono, loggear warning y retornar {}
   - Llamar a upsert_cliente(db, telefono, datos) donde datos incluye: nombre_completo=loan.get("cliente_nombre"), cedula=loan.get("cliente_cedula" o "cedula"), loanbook_id=loan.get("id"), score_roddos=70, etapa_cobro="preventivo", ptp_activo=None
   - Retornar resultado de upsert_cliente

5. Agregar `async def crear_acuerdo(db, loanbook_id: str, datos: dict, autor: str) -> dict`:
   - Construir doc con todos los campos del esquema CONTEXT.md (id=uuid4(), loanbook_id, cliente_nombre=datos.get("cliente_nombre",""), tipo, condiciones, monto_acordado, fecha_inicio, fecha_limite, cuotas_acuerdo=datos.get("cuotas_acuerdo",[]), estado="activo", creado_por=autor, created_at=now_iso)
   - Insertar en db.acuerdos_pago
   - Crear indice {loanbook_id: 1} en acuerdos_pago si no existe (usar create_index con background=True)
   - Retornar doc (sin _id)

6. Agregar `async def actualizar_estado_acuerdo(db, acuerdo_id: str, estado: str) -> dict`:
   - Validar que estado este en {"activo","cumplido","incumplido","cancelado"}
   - update_one por id, $set estado + updated_at
   - Retornar find_one del documento actualizado (sin _id)
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/backend && python -c "
from services.crm_service import RESULTADO_VALIDOS, calcular_score_roddos, upsert_cliente_desde_loanbook, crear_acuerdo, actualizar_estado_acuerdo
nuevos = ['sin_respuesta_72h','bloqueo_detectado','numero_apagado','pago_parcial_reportado','acuerdo_firmado','disputa_deuda']
for rv in nuevos:
    assert rv in RESULTADO_VALIDOS, f'Falta: {rv}'
print('OK — imports y RESULTADO_VALIDOS correctos')
"</automated>
  </verify>
  <done>
    - Los 6 nuevos RESULTADO_VALIDOS existen en el set (sin tocar "acuerdo_de_pago_firmado")
    - calcular_score_roddos importa sin error y retorna dict con score_roddos y etiqueta_roddos
    - upsert_cliente_desde_loanbook, crear_acuerdo, actualizar_estado_acuerdo importan sin error
    - El modulo crm_service.py pasa python -c "import services.crm_service" sin ImportError
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════
     WAVE 2 — SCHEDULER: loanbook_scheduler.py (depende de crm_service ampliado)
     ═══════════════════════════════════════════════════════════════════ -->

<task type="auto" tdd="true">
  <name>Task 2: Ampliar loanbook_scheduler.py — etapa_cobro en CRON-1 + score_roddos en CRON-4</name>
  <files>backend/services/loanbook_scheduler.py</files>
  <behavior>
    - _calcular_etapa_cobro(dpd, dias_para_proxima) implementa exactamente las 6 reglas de CONTEXT.md
    - etapa_cobro persiste en loanbook via update_fields en calcular_dpd_todos()
    - calcular_scores() escribe score_roddos y etiqueta_roddos en loanbook SIN tocar score_pago ni estrella_nivel
    - calcular_scores() tambien actualiza crm_clientes.score_roddos via upsert inline
    - Los imports nuevos en calcular_dpd_todos() y calcular_scores() son INLINE (dentro de la funcion)
  </behavior>
  <action>
Modificar backend/services/loanbook_scheduler.py:

**Parte A — Helper privado _calcular_etapa_cobro:**
Agregar antes de calcular_dpd_todos():
```python
def _calcular_etapa_cobro(dpd: int, dias_para_proxima: int) -> str:
    """Clasifica la etapa de cobro segun DPD y dias para proxima cuota."""
    if dpd == 0 and dias_para_proxima > 2:
        return "preventivo"
    if dpd == 0 and dias_para_proxima <= 2:
        return "vencimiento_proximo"
    if dpd <= 7:
        return "gestion_activa"
    if dpd <= 14:
        return "alerta_formal"
    if dpd <= 21:
        return "escalacion"
    return "recuperacion"
```

**Parte B — calcular_dpd_todos():**
1. Dentro del loop for loan in loans, despues de calcular dpd_actual y antes de construir update_fields, calcular dias_para_proxima:
```python
# Calcular dias para proxima cuota (para etapa_cobro)
hoy_date = hoy  # ya definido como date.today()
proximas = [
    c for c in cuotas
    if c.get("estado") == "pendiente"
    and c.get("fecha_vencimiento", "") >= hoy_str
]
if proximas:
    prox_fv = min(c["fecha_vencimiento"] for c in proximas)
    dias_para_proxima = (date.fromisoformat(prox_fv) - hoy_date).days
else:
    dias_para_proxima = 999  # Sin cuota pendiente futura = preventivo
etapa = _calcular_etapa_cobro(dpd_actual, dias_para_proxima)
```
2. Agregar `"etapa_cobro": etapa` a update_fields.

**Parte C — calcular_scores():**
1. Ampliar la proyeccion del find() para incluir score_historial:
   Agregar `"score_historial": 1, "cliente_telefono": 1` a la proyeccion existente.

2. Dentro del loop for loan in loans, DESPUES de calcular score y estrellas existentes, agregar inline import y calculo de score_roddos:
```python
# Score multidimensional FASE 8-A
from services.crm_service import calcular_score_roddos  # inline — evita circular import
resultado_score = await calcular_score_roddos(db, loan)
score_roddos_val = resultado_score["score_roddos"]
etiqueta_roddos_val = resultado_score["etiqueta_roddos"]
```

3. En el update_one de loanbook, agregar al $set: `"score_roddos": score_roddos_val, "etiqueta_roddos": etiqueta_roddos_val`. NO modificar score_pago ni estrella_nivel.

4. Agregar score_roddos al score_entry que se hace push a score_historial (para que dimension_trayectoria pueda leerlo en el futuro): agregar `"score_roddos": score_roddos_val, "dpd_actual": dpd` al dict score_entry.

5. Opcional — actualizar crm_clientes.score_roddos si el cliente existe:
```python
telefono = loan.get("cliente_telefono", "")
if telefono:
    from services.crm_service import normalizar_telefono
    tel_norm = normalizar_telefono(telefono)
    await db.crm_clientes.update_one(
        {"telefono_principal": tel_norm},
        {"$set": {"score_roddos": score_roddos_val, "etiqueta_roddos": etiqueta_roddos_val, "updated_at": now_iso}},
    )
```
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/backend && python -c "
from services.loanbook_scheduler import _calcular_etapa_cobro
assert _calcular_etapa_cobro(0, 5) == 'preventivo'
assert _calcular_etapa_cobro(0, 1) == 'vencimiento_proximo'
assert _calcular_etapa_cobro(3, 0) == 'gestion_activa'
assert _calcular_etapa_cobro(10, 0) == 'alerta_formal'
assert _calcular_etapa_cobro(18, 0) == 'escalacion'
assert _calcular_etapa_cobro(22, 0) == 'recuperacion'
print('OK — _calcular_etapa_cobro correcta')
"</automated>
  </verify>
  <done>
    - _calcular_etapa_cobro existe y retorna los 6 valores correctos
    - update_fields en calcular_dpd_todos incluye etapa_cobro
    - calcular_scores escribe score_roddos y etiqueta_roddos en $set sin tocar score_pago/estrella_nivel
    - score_historial entry incluye dpd_actual para que dimension_trayectoria funcione
    - El modulo importa sin error: python -c "import services.loanbook_scheduler"
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════
     WAVE 3 — ROUTERS: loanbook.py + crm.py + radar.py
     (todos dependen de crm_service ampliado — pueden correr en paralelo entre si)
     ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 3: Sync CRM en loanbook.py + 3 endpoints acuerdos en crm.py</name>
  <files>backend/routers/loanbook.py, backend/routers/crm.py</files>
  <action>
**loanbook.py — Sync CRM en register_entrega():**

Localizar el bloque al final de register_entrega() entre `await invalidar_cache_cfo()` y `await log_action(...)` (~linea 1273-1275). Insertar:
```python
# Sync CRM — crear/actualizar ficha en crm_clientes (no bloqueante)
try:
    from services.crm_service import upsert_cliente_desde_loanbook
    await upsert_cliente_desde_loanbook(db, loan)
except Exception as _crm_err:
    logger.warning("[register_entrega] CRM sync error (no bloqueante): %s", _crm_err)
```
El import es INLINE dentro de la funcion (patron ya establecido en el proyecto, ver pitfall 1 de RESEARCH.md). NO agregar import a nivel modulo.

---

**crm.py — 3 endpoints nuevos para acuerdos_pago:**

1. Ampliar el import existente de crm_service (linea 11):
```python
from services.crm_service import (
    registrar_gestion, agregar_nota, registrar_ptp,
    crear_acuerdo, actualizar_estado_acuerdo,
)
```

2. En la seccion de Models (despues de PTPCreate), agregar:
```python
class AcuerdoCreate(BaseModel):
    tipo: str  # pago_parcial | descuento_mora | refinanciacion | acuerdo_total
    condiciones: str
    monto_acordado: float
    fecha_inicio: str  # ISO date YYYY-MM-DD
    fecha_limite: str  # ISO date YYYY-MM-DD
    cuotas_acuerdo: Optional[list] = []
    cliente_nombre: Optional[str] = ""

class EstadoAcuerdoUpdate(BaseModel):
    estado: str  # activo | cumplido | incumplido | cancelado
```

3. Al final del archivo, agregar los 3 endpoints:

```python
@router.post("/{loanbook_id}/acuerdo")
async def crear_acuerdo_pago(
    loanbook_id: str,
    body: AcuerdoCreate,
    current_user=Depends(get_current_user),
):
    """Crea un acuerdo de pago formal + registra gestion 'acuerdo_firmado'."""
    datos = body.model_dump()
    datos["loanbook_id"] = loanbook_id
    acuerdo = await crear_acuerdo(db, loanbook_id, datos, current_user["username"])
    # Registrar gestion acuerdo_firmado
    await registrar_gestion(
        db, loanbook_id, "acuerdo", "acuerdo_firmado",
        f"Acuerdo tipo={body.tipo} monto={body.monto_acordado}",
        current_user["username"], None,
    )
    return acuerdo


@router.get("/{loanbook_id}/acuerdos")
async def listar_acuerdos(
    loanbook_id: str,
    current_user=Depends(get_current_user),
):
    """Retorna todos los acuerdos de pago del loanbook."""
    acuerdos = await db.acuerdos_pago.find(
        {"loanbook_id": loanbook_id}, {"_id": 0}
    ).sort("created_at", -1).to_list(200)
    return {"loanbook_id": loanbook_id, "acuerdos": acuerdos, "total": len(acuerdos)}


@router.put("/acuerdos/{acuerdo_id}/estado")
async def update_estado_acuerdo(
    acuerdo_id: str,
    body: EstadoAcuerdoUpdate,
    current_user=Depends(get_current_user),
):
    """Actualiza el estado de un acuerdo (cumplido/incumplido/cancelado)."""
    actualizado = await actualizar_estado_acuerdo(db, acuerdo_id, body.estado)
    if not actualizado:
        raise HTTPException(status_code=404, detail="Acuerdo no encontrado")
    return actualizado
```
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/backend && python -c "
import ast, pathlib
# Verificar loanbook.py tiene el sync CRM
src = pathlib.Path('routers/loanbook.py').read_text(encoding='utf-8')
assert 'upsert_cliente_desde_loanbook' in src, 'Falta sync CRM en loanbook.py'
# Verificar crm.py tiene los nuevos endpoints y modelos
src2 = pathlib.Path('routers/crm.py').read_text(encoding='utf-8')
assert 'AcuerdoCreate' in src2, 'Falta AcuerdoCreate'
assert 'acuerdos' in src2, 'Falta endpoint acuerdos'
assert 'EstadoAcuerdoUpdate' in src2, 'Falta EstadoAcuerdoUpdate'
print('OK — sync CRM y endpoints acuerdos presentes')
"</automated>
  </verify>
  <done>
    - loanbook.py tiene inline import + try/except no bloqueante de upsert_cliente_desde_loanbook en register_entrega()
    - crm.py tiene AcuerdoCreate, EstadoAcuerdoUpdate, y los 3 endpoints POST/{id}/acuerdo, GET/{id}/acuerdos, PUT/acuerdos/{id}/estado
    - crm.py importa crear_acuerdo y actualizar_estado_acuerdo desde crm_service
    - python -c "from routers.crm import router" no lanza ImportError
  </done>
</task>

<task type="auto">
  <name>Task 4: Agregar GET /diagnostico + POST /arranque en radar.py</name>
  <files>backend/routers/radar.py</files>
  <action>
Agregar al final de backend/routers/radar.py los 2 nuevos endpoints. Los imports adicionales necesarios son: `uuid`, `datetime`, `BackgroundTasks` de fastapi.

1. Agregar al bloque de imports al inicio del archivo:
```python
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, BackgroundTasks, Depends
```
(BackgroundTasks ya esta en fastapi — solo agregar al import existente de fastapi)

2. Al final del archivo, agregar:

```python
@router.get("/diagnostico")
async def diagnostico_sistema(current_user=Depends(get_current_user)):
    """Estado del sistema: loanbooks con DPD + score_roddos + etapa_cobro + ultimo run schedulers."""
    # Loanbooks activos con campos de score
    loans = await db.loanbook.find(
        {"estado": {"$in": ["activo", "mora"]}},
        {"_id": 0, "id": 1, "codigo": 1, "cliente_nombre": 1,
         "dpd_actual": 1, "etapa_cobro": 1, "score_roddos": 1,
         "etiqueta_roddos": 1, "score_pago": 1, "estrella_nivel": 1,
         "updated_at": 1},
    ).to_list(5000)

    # Ultimo run de cada scheduler job desde roddos_events
    scheduler_jobs = ["calcular_dpd_todos", "calcular_scores", "generar_cola_radar"]
    ultimo_run: dict = {}
    for job in scheduler_jobs:
        evt = await db.roddos_events.find_one(
            {"payload.job": job},
            {"_id": 0, "created_at": 1, "payload": 1},
            sort=[("created_at", -1)],
        )
        ultimo_run[job] = evt.get("created_at") if evt else None

    # Estado Mercately API key
    settings = await db.user_settings.find_one({"tipo": "mercately"}, {"_id": 0, "api_key": 1})
    mercately_ok = bool(settings and settings.get("api_key"))

    total_activos = len(loans)
    con_score = sum(1 for l in loans if l.get("score_roddos") is not None)
    con_etapa = sum(1 for l in loans if l.get("etapa_cobro"))

    return {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "loanbooks": {
            "total_activos": total_activos,
            "con_score_roddos": con_score,
            "con_etapa_cobro": con_etapa,
            "detalle": loans,
        },
        "schedulers": {
            "ultimo_run": ultimo_run,
        },
        "mercately": {
            "api_key_configurada": mercately_ok,
        },
    }


@router.post("/arranque")
async def arranque_manual(
    background_tasks: BackgroundTasks,
    current_user=Depends(get_current_user),
):
    """Dispara calcular_dpd_todos + calcular_scores + generar_cola_radar sin esperar CRON 06:00."""
    job_id = str(uuid.uuid4())

    async def _run_jobs():
        from services.loanbook_scheduler import (
            calcular_dpd_todos, calcular_scores, generar_cola_radar,
        )
        try:
            await calcular_dpd_todos()
            await calcular_scores()
            await generar_cola_radar()
            await db.roddos_events.insert_one({
                "id": str(uuid.uuid4()),
                "event_type": "scheduler.arranque_manual",
                "job_id": job_id,
                "actor": current_user.get("username", "sistema"),
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "payload": {"job": "arranque_manual", "triggered_by": "POST /radar/arranque"},
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).error("[arranque] Error en jobs: %s", exc)
            await db.roddos_events.insert_one({
                "id": str(uuid.uuid4()),
                "event_type": "scheduler.arranque_manual",
                "job_id": job_id,
                "status": "error",
                "error": str(exc),
                "created_at": datetime.now(timezone.utc).isoformat(),
                "payload": {"job": "arranque_manual"},
            })

    background_tasks.add_task(_run_jobs)

    return {
        "job_id": job_id,
        "status": "enqueued",
        "message": "Jobs encolados: calcular_dpd_todos → calcular_scores → generar_cola_radar",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
```

NOTA: Si `generar_cola_radar` no existe en loanbook_scheduler.py, usar solo `calcular_dpd_todos` y `calcular_scores` en _run_jobs y documentarlo. Verificar con grep antes de asumir que existe.
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/backend && python -c "
import pathlib
src = pathlib.Path('routers/radar.py').read_text(encoding='utf-8')
assert 'diagnostico' in src, 'Falta endpoint diagnostico'
assert 'arranque' in src, 'Falta endpoint arranque'
assert 'job_id' in src, 'Falta job_id en arranque'
assert 'BackgroundTasks' in src, 'Falta BackgroundTasks'
print('OK — endpoints diagnostico y arranque presentes en radar.py')
"</automated>
  </verify>
  <done>
    - radar.py tiene GET /diagnostico que retorna loanbooks con dpd+score+etapa, ultimo run schedulers, estado mercately
    - radar.py tiene POST /arranque que retorna job_id inmediatamente y dispara los 3 jobs en background
    - python -c "from routers.radar import router" no lanza ImportError
  </done>
</task>

<!-- ═══════════════════════════════════════════════════════════════════
     WAVE 4 — TESTS: 10 tests T1-T10 todos GREEN
     (depende de los 3 archivos de servicio y 2 routers completos)
     ═══════════════════════════════════════════════════════════════════ -->

<task type="auto">
  <name>Task 5: 10 tests T1-T10 en test_fase8a_crm_robusto.py</name>
  <files>backend/tests/test_fase8a_crm_robusto.py</files>
  <behavior>
    - T1: score_roddos >= 85 y etiqueta "A+" para cliente con 10 cuotas pagadas a tiempo
    - T2: score_roddos < 25 y etiqueta "E" para cliente con dpd=22 y 3 PTPs incumplidos
    - T3: score_roddos == 70.0 para cliente nuevo sin historial (retorno de upsert_cliente_desde_loanbook)
    - T4: upsert_cliente_desde_loanbook() produce doc con telefono, nombre, cedula, loanbook_id
    - T5: _calcular_etapa_cobro(3, 0) == "gestion_activa"
    - T6: _calcular_etapa_cobro(22, 0) == "recuperacion"
    - T7: crear_acuerdo() retorna doc + "acuerdo_firmado" en RESULTADO_VALIDOS
    - T8: diagnostico endpoint estructura completa sin error 500 (test estatico de codigo)
    - T9: POST arranque retorna job_id en la respuesta (test estatico de codigo)
    - T10: calcular_scores() escribe score_roddos en update_one (test estatico de codigo fuente)
  </behavior>
  <action>
Crear backend/tests/test_fase8a_crm_robusto.py con los 10 tests. Usar patron mixto: estatico (Path().read_text()) para tests de estructura de codigo, AsyncMock para tests de logica pura sin MongoDB live.

```python
"""test_fase8a_crm_robusto.py — 10 tests FASE 8-A: CRM Robusto.

Patron mixto:
- Tests T1-T6: logica pura con AsyncMock (sin MongoDB live)
- Tests T7-T10: analisis estatico del codigo fuente (sin servidor activo)
"""
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, timedelta

# ── Rutas de fuentes ─────────────────────────────────────────────────────────
BACKEND = Path(__file__).parent.parent
CRM_SERVICE_SRC   = (BACKEND / "services" / "crm_service.py").read_text(encoding="utf-8")
SCHEDULER_SRC     = (BACKEND / "services" / "loanbook_scheduler.py").read_text(encoding="utf-8")
CRM_ROUTER_SRC    = (BACKEND / "routers" / "crm.py").read_text(encoding="utf-8")
RADAR_ROUTER_SRC  = (BACKEND / "routers" / "radar.py").read_text(encoding="utf-8")
LOANBOOK_SRC      = (BACKEND / "routers" / "loanbook.py").read_text(encoding="utf-8")


# ── T1: score A+ para cliente con 10 cuotas a tiempo ────────────────────────
@pytest.mark.asyncio
async def test_t1_score_cliente_excelente():
    """T1: Cliente con 10 cuotas pagadas a tiempo → score_roddos >= 85 → etiqueta A+."""
    from services.crm_service import calcular_score_roddos

    hoy = date.today()
    cuotas_a_tiempo = [
        {
            "estado": "pagada",
            "fecha_vencimiento": (hoy - timedelta(days=30 * (i + 1))).isoformat(),
            "fecha_pago":        (hoy - timedelta(days=30 * (i + 1))).isoformat(),  # pago exacto en fecha
            "valor": 150000,
        }
        for i in range(10)
    ]
    loan = {
        "id": "LB-TEST-01",
        "dpd_actual": 0,
        "dpd_maximo_historico": 0,
        "cuotas": cuotas_a_tiempo,
        "gestiones": [],
        "score_historial": [],
    }
    db_mock = AsyncMock()
    resultado = await calcular_score_roddos(db_mock, loan)
    assert resultado["score_roddos"] >= 85, f"Esperado >= 85, obtenido {resultado['score_roddos']}"
    assert resultado["etiqueta_roddos"] == "A+", f"Esperado A+, obtenido {resultado['etiqueta_roddos']}"


# ── T2: score E para DPD=22 y 3 PTPs incumplidos ────────────────────────────
@pytest.mark.asyncio
async def test_t2_score_cliente_critico():
    """T2: Cliente con dpd=22 y 3 PTPs incumplidos → score_roddos < 25 → etiqueta E."""
    from services.crm_service import calcular_score_roddos

    gestiones_incumplidas = [
        {"resultado": "contestó_prometió_fecha", "ptp_fue_cumplido": False}
        for _ in range(3)
    ]
    loan = {
        "id": "LB-TEST-02",
        "dpd_actual": 22,
        "dpd_maximo_historico": 22,
        "cuotas": [],
        "gestiones": gestiones_incumplidas,
        "score_historial": [],
    }
    db_mock = AsyncMock()
    resultado = await calcular_score_roddos(db_mock, loan)
    assert resultado["score_roddos"] < 25, f"Esperado < 25, obtenido {resultado['score_roddos']}"
    assert resultado["etiqueta_roddos"] == "E", f"Esperado E, obtenido {resultado['etiqueta_roddos']}"


# ── T3: cliente nuevo → score_roddos = 70 ────────────────────────────────────
@pytest.mark.asyncio
async def test_t3_score_cliente_nuevo():
    """T3: upsert_cliente_desde_loanbook inicializa score_roddos=70 exacto."""
    from services.crm_service import upsert_cliente_desde_loanbook

    loan = {
        "id": "LB-TEST-03",
        "cliente_nombre": "Juan Perez",
        "cliente_telefono": "3001234567",
        "cliente_cedula": "12345678",
    }

    # Mock db que simula que no existe el cliente (find_one retorna None)
    db_mock = AsyncMock()
    db_mock.crm_clientes.find_one = AsyncMock(return_value=None)
    db_mock.crm_clientes.insert_one = AsyncMock(return_value=MagicMock(inserted_id="fake"))
    db_mock.crm_clientes.update_one = AsyncMock()

    with patch("services.crm_service.upsert_cliente") as mock_upsert:
        mock_upsert.return_value = {"score_roddos": 70, "etapa_cobro": "preventivo"}
        resultado = await upsert_cliente_desde_loanbook(db_mock, loan)

    # Verificar que upsert_cliente fue llamado con score_roddos=70
    call_args = mock_upsert.call_args
    datos_pasados = call_args[0][2] if call_args[0] else call_args[1].get("datos", {})
    assert datos_pasados.get("score_roddos") == 70, f"score_roddos debe ser 70, fue {datos_pasados.get('score_roddos')}"


# ── T4: sync CRM produce doc con campos requeridos ──────────────────────────
@pytest.mark.asyncio
async def test_t4_sync_crm_campos_requeridos():
    """T4: upsert_cliente_desde_loanbook llama upsert_cliente con telefono, nombre, cedula, loanbook_id."""
    from services.crm_service import upsert_cliente_desde_loanbook

    loan = {
        "id": "LB-TEST-04",
        "cliente_nombre": "Maria Lopez",
        "cliente_telefono": "3109876543",
        "cliente_cedula": "87654321",
    }
    db_mock = AsyncMock()

    with patch("services.crm_service.upsert_cliente") as mock_upsert:
        mock_upsert.return_value = {}
        await upsert_cliente_desde_loanbook(db_mock, loan)

    assert mock_upsert.called, "upsert_cliente no fue llamado"
    call_args = mock_upsert.call_args
    datos = call_args[0][2] if len(call_args[0]) >= 3 else call_args[1].get("datos", {})
    assert datos.get("nombre_completo") == "Maria Lopez", "Nombre no propagado"
    assert datos.get("loanbook_id") == "LB-TEST-04", "loanbook_id no propagado"
    # cedula puede estar en diferentes campos segun el loanbook
    tiene_cedula = datos.get("cedula") or datos.get("cliente_cedula")
    assert tiene_cedula, "cedula no propagada"


# ── T5: etapa_cobro = gestion_activa cuando dpd=3 ────────────────────────────
def test_t5_etapa_cobro_gestion_activa():
    """T5: _calcular_etapa_cobro(dpd=3, dias=0) == 'gestion_activa'."""
    from services.loanbook_scheduler import _calcular_etapa_cobro
    resultado = _calcular_etapa_cobro(3, 0)
    assert resultado == "gestion_activa", f"Esperado 'gestion_activa', obtenido '{resultado}'"


# ── T6: etapa_cobro = recuperacion cuando dpd=22 ─────────────────────────────
def test_t6_etapa_cobro_recuperacion():
    """T6: _calcular_etapa_cobro(dpd=22, dias=0) == 'recuperacion'."""
    from services.loanbook_scheduler import _calcular_etapa_cobro
    resultado = _calcular_etapa_cobro(22, 0)
    assert resultado == "recuperacion", f"Esperado 'recuperacion', obtenido '{resultado}'"


# ── T7: crear_acuerdo + "acuerdo_firmado" en RESULTADO_VALIDOS ───────────────
@pytest.mark.asyncio
async def test_t7_crear_acuerdo_y_resultado_valido():
    """T7: crear_acuerdo() crea doc en acuerdos_pago + 'acuerdo_firmado' esta en RESULTADO_VALIDOS."""
    from services.crm_service import crear_acuerdo, RESULTADO_VALIDOS

    assert "acuerdo_firmado" in RESULTADO_VALIDOS, "'acuerdo_firmado' no esta en RESULTADO_VALIDOS"

    datos = {
        "loanbook_id": "LB-TEST-07",
        "cliente_nombre": "Carlos Test",
        "tipo": "pago_parcial",
        "condiciones": "Paga $100k ahora, saldo en 2 semanas",
        "monto_acordado": 100000.0,
        "fecha_inicio": "2026-04-05",
        "fecha_limite": "2026-04-19",
        "cuotas_acuerdo": [],
    }
    db_mock = AsyncMock()
    db_mock.acuerdos_pago.insert_one = AsyncMock(return_value=MagicMock(inserted_id="fake_id"))
    db_mock.acuerdos_pago.create_index = AsyncMock()

    resultado = await crear_acuerdo(db_mock, "LB-TEST-07", datos, "test_user")

    assert db_mock.acuerdos_pago.insert_one.called, "insert_one no fue llamado en acuerdos_pago"
    assert resultado.get("loanbook_id") == "LB-TEST-07", "loanbook_id no en resultado"
    assert resultado.get("estado") == "activo", "estado inicial debe ser 'activo'"


# ── T8: GET /diagnostico — estructura completa en codigo fuente ──────────────
def test_t8_diagnostico_endpoint_existe():
    """T8: radar.py tiene endpoint /diagnostico con campos requeridos."""
    assert "diagnostico" in RADAR_ROUTER_SRC, "Endpoint /diagnostico no encontrado en radar.py"
    assert "score_roddos" in RADAR_ROUTER_SRC, "score_roddos no en diagnostico"
    assert "etapa_cobro" in RADAR_ROUTER_SRC, "etapa_cobro no en diagnostico"
    assert "ultimo_run" in RADAR_ROUTER_SRC, "ultimo_run schedulers no en diagnostico"
    assert "mercately" in RADAR_ROUTER_SRC, "estado mercately no en diagnostico"


# ── T9: POST /arranque — retorna job_id ──────────────────────────────────────
def test_t9_arranque_retorna_job_id():
    """T9: radar.py tiene endpoint /arranque que retorna job_id."""
    assert "arranque" in RADAR_ROUTER_SRC, "Endpoint /arranque no encontrado en radar.py"
    assert "job_id" in RADAR_ROUTER_SRC, "job_id no retornado en /arranque"
    assert "BackgroundTasks" in RADAR_ROUTER_SRC, "BackgroundTasks no usado en /arranque"
    assert "calcular_dpd_todos" in RADAR_ROUTER_SRC, "calcular_dpd_todos no disparado en /arranque"


# ── T10: calcular_scores escribe score_roddos en loanbook ────────────────────
def test_t10_calcular_scores_escribe_score_roddos():
    """T10: loanbook_scheduler.py escribe score_roddos en update_one de calcular_scores."""
    assert "calcular_score_roddos" in SCHEDULER_SRC, "calcular_score_roddos no llamado en scheduler"
    assert "score_roddos" in SCHEDULER_SRC, "score_roddos no escrito en scheduler"
    assert "etiqueta_roddos" in SCHEDULER_SRC, "etiqueta_roddos no escrito en scheduler"
    # Verificar que score_pago no fue eliminado (compatibilidad)
    assert "score_pago" in SCHEDULER_SRC, "score_pago fue eliminado — rompe compatibilidad frontend"
```
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO && python -m pytest backend/tests/test_fase8a_crm_robusto.py -v 2>&1 | tail -20</automated>
  </verify>
  <done>
    - Los 10 tests existen en test_fase8a_crm_robusto.py
    - pytest backend/tests/test_fase8a_crm_robusto.py -v retorna 10 passed, 0 failed
    - T1-T6 prueban logica de negocio real via AsyncMock
    - T7-T10 verifican estructura del codigo fuente via analisis estatico
  </done>
</task>

</tasks>

<verification>
Verificacion completa de FASE 8-A:

```bash
# 1. Imports sin error (todos los archivos modificados)
cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/backend
python -c "import services.crm_service; import services.loanbook_scheduler; import routers.crm; import routers.radar"

# 2. RESULTADO_VALIDOS tiene los 6 nuevos
python -c "
from services.crm_service import RESULTADO_VALIDOS
nuevos = ['sin_respuesta_72h','bloqueo_detectado','numero_apagado','pago_parcial_reportado','acuerdo_firmado','disputa_deuda']
missing = [r for r in nuevos if r not in RESULTADO_VALIDOS]
print('FALTANTES:', missing) if missing else print('OK — 6 nuevos RESULTADO_VALIDOS')
"

# 3. Etapa cobro correcta
python -c "
from services.loanbook_scheduler import _calcular_etapa_cobro
casos = [(0,5,'preventivo'),(0,1,'vencimiento_proximo'),(3,0,'gestion_activa'),(10,0,'alerta_formal'),(18,0,'escalacion'),(22,0,'recuperacion')]
for dpd,dias,esperado in casos:
    r = _calcular_etapa_cobro(dpd,dias)
    assert r == esperado, f'dpd={dpd} dias={dias}: esperado {esperado} obtenido {r}'
print('OK — 6 etapas correctas')
"

# 4. Tests completos
cd C:/Users/AndresSanJuan/roddos-workspace/SISMO
python -m pytest backend/tests/test_fase8a_crm_robusto.py -v
```
</verification>

<success_criteria>
- [ ] crm_service.py: 6 nuevos RESULTADO_VALIDOS + 4 funciones nuevas (calcular_score_roddos, upsert_cliente_desde_loanbook, crear_acuerdo, actualizar_estado_acuerdo)
- [ ] loanbook_scheduler.py: _calcular_etapa_cobro con 6 etapas + etapa_cobro en calcular_dpd_todos() + score_roddos/etiqueta_roddos en calcular_scores() via inline import
- [ ] loanbook.py: sync CRM no bloqueante en register_entrega() via try/except + inline import
- [ ] crm.py: 3 endpoints nuevos (POST acuerdo, GET acuerdos, PUT acuerdo estado) + modelos Pydantic AcuerdoCreate y EstadoAcuerdoUpdate
- [ ] radar.py: GET /diagnostico con estado completo + POST /arranque con job_id via BackgroundTasks
- [ ] 10 tests T1-T10: pytest retorna 10 passed, 0 failed
- [ ] score_pago y estrella_nivel NO fueron eliminados (compatibilidad frontend)
- [ ] Ninguno de los archivos INAMOVIBLES fue modificado (shared_state.py, conciliacion.py, bank_reconciliation.py, database.py, dependencies.py, alegra_service.py)
</success_criteria>

<output>
Despues de completar todos los tasks, crear `.planning/phases/08a-crm-robusto/08a-01-SUMMARY.md` con:
- Archivos modificados y que se cambio en cada uno
- Funciones nuevas creadas y sus firmas
- Endpoints nuevos con URL y metodo
- Resultado del pytest (captura de los 10 tests)
- Decisiones tomadas en areas de Claude's Discretion (especialmente la estructura de calcular_score_roddos y como se manejo generar_cola_radar si no existia)
</output>
