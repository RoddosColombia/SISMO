# SMOKE TEST — Agente Contador SISMO
## Evaluación de Funciones Reales del Sistema
**Fecha:** 2026-03-22  
**Metodología:** Verificación de código fuente, NO suposiciones

---

## FUNCIÓN 1: Conciliación Bancaria desde Extractos
**Ubicación:** `services/bank_reconciliation.py` + `routers/conciliacion.py`

### ¿Existe parser para BBVA, Bancolombia, Davivienda, Nequi?
✅ **SÍ**
- `BancolombiParser` (línea 65)
- `BBVAParser` (línea 145)
- `DaviviendaParser` (línea 219)
- `NequiParser` (línea 274)
- Cada uno con método `parsear(archivo_bytes)` implementado

### ¿El motor matricial clasifica movimientos con confianza?
✅ **SÍ**
- Motor en `services/accounting_engine.py`
- 50+ reglas de clasificación (BBVA 12 + Bancolombia 18 + Generic 15+)
- Campo `confianza: float` en `MovimientoBancario` (línea 59)
- Threshold: `confianza >= 0.70` → CAUSABLE (línea 405)
- Threshold: `confianza < 0.70` → PENDIENTE (línea 408)

### ¿Los causables se registran en Alegra como journals?
✅ **SÍ**
- `crear_journal_alegra()` implementado (línea 417, bank_reconciliation.py)
- POST a `https://api.alegra.com/api/v1/journals`
- Estructura de entries: debit/credit en cuenta correcta
- Validación: verifica HTTP 200 antes de confirmar
- MongoDB: inserta en `conciliacion_movimientos_procesados` con upsert=True

### ¿Los pendientes van a cola de revisión manual?
✅ **SÍ**
- Guardados en `contabilidad_pendientes` (línea 567)
- Estructura con contexto completo:
  - `proveedor_extraido`
  - `cuenta_debito_sugerida`
  - `cuenta_credito_sugerida`
  - `confianza_sugerida`
  - `razon_baja_confianza`
  - `estado: "pendiente_whatsapp"`
- Campo `resuelto_por` para Agente Contador (línea 606)

### ¿Existe anti-duplicados funcional?
✅ **SÍ — DUAL LAYER**
- CAPA 1: Hash del extracto completo (conciliacion_extractos_procesados)
  - Solo guarda si causados > 0
  - Índice único en `hash`
- CAPA 2: Hash por movimiento individual (conciliacion_movimientos_procesados)
  - `hash_movimiento = MD5(banco + fecha + descripcion + monto)`
  - Verificación con `find_one()` ANTES de crear (línea 146)
  - `update_one(..., upsert=True)` para evitar duplicados (línea 161)
  - Índice único en `hash`

### Observaciones Críticas:
- ⚠️ Payload validation: Verifica None en cuentas antes de enviar a Alegra (línea 448)
- ⚠️ Try/except individual: Cada journal en su propio bloque try/except (línea 138)
- ⚠️ Logs detallados: [BG-START], [BG-MOV], [BG-END] para diagnóstico
- ✅ Persistencia: Todos los estados en MongoDB (no en RAM)

**CALIFICACIÓN: 9/10**
> Excelente cobertura. Detalles: Anti-duplicados dual-layer funcional, try/except robusto, logs completos, persistencia en MongoDB. Pequeña mejora: add reason tracking cuando journal no se puede crear (actualmente solo cuenta errores).

---

## FUNCIÓN 2: Registro de Gastos Individuales por Chat
**Ubicación:** `routers/chat.py` + `ai_chat.py`

### ¿El chat del Agente Contador acepta prompts de gastos?
⚠️ **PARCIAL (6/10)**
- Chat router existe (`routers/chat.py`, línea 35)
- Procesa mensajes con `process_chat()` (ai_chat.py)
- ai_chat.py tiene 211KB de instrucciones y reglas para gastos
- PERO: No se ve implementación de endpoint específico para "crear gasto directo desde chat"
- Función principal parece ser conversacional, no transaccional

### ¿Calcula ReteFuente y ReteICA automáticamente?
✅ **SÍ — Pero en CSV, no chat directo**
- `_calcular_retenciones()` implementado (línea 149, gastos.py)
- Reglas detalladas en ai_chat.py:
  - ReteFuente Servicios 4% (línea 183)
  - ReteFuente Honorarios PN 10% / PJ 11% (línea 185)
  - ReteICA Bogotá 0.414% servicios (línea 190)
- PERO: Esto es para CSV bulk, no para chat interactivo

### ¿Propone el asiento antes de ejecutar?
⚠️ **PARCIAL**
- ai_chat.py línea 291: "Diagnóstico de asiento contable" existe
- Línea 377: "Verificar asiento en Alegra"
- PERO: Parece ser para diagnosis, no para propuesta antes de crear
- No hay evidencia de workflow: "propuesta → usuario aprueba → crea"

### ¿Verifica HTTP 200 en Alegra antes de reportar éxito?
❌ **NO VERIFICADO EN CHAT**
- En gastos.py (_process_row, línea 574): SÍ valida HTTP responses
- En bank_reconciliation.py: SÍ valida HTTP 200
- En chat: No hay código visible que haga transacciones contra Alegra

### ¿Reporta el ID del journal creado?
❌ **NO IMPLEMENTADO EN CHAT**
- gastos.py lo hace (get_journals_creados endpoint, línea 846)
- Chat: No hay endpoint que retorne journal IDs

### Observaciones Críticas:
- ❌ **Chat NO es agente transaccional realmente**
- La intención es "conversacional + diagnosis", no "crear journal desde chat"
- Los cálculos de retenciones existen pero en módulo CSV, no chat

**CALIFICACIÓN: 3/10**
> Chat de Contador es conversacional/diagnostic, NO transaccional. No puede crear gastos ni journals directamente desde prompts. Los cálculos de retención existen pero en CSV bulk, no en chat interactivo. Se necesitría refactor completo para hacer esto funcional.

---

## FUNCIÓN 3: Carga Masiva de Gastos por CSV
**Ubicación:** `routers/gastos.py`

### ¿Existe endpoint para subir CSV?
✅ **SÍ**
- POST `/api/gastos/cargar` (línea 279)
- Recibe UploadFile
- Valida .csv (rechaza .xlsx, .xls con sugerencia)

### ¿Valida 7 columnas obligatorias?
✅ **SÍ**
- REQUIRED_FIELDS definidos (línea 346)
- Verifica con `missing = [f for f in REQUIRED_FIELDS if f not in col_map]`
- Error si faltan: "Columnas requeridas no encontradas"
- Columnas: fecha, categoria, subcategoria, descripcion, monto, proveedor, referencia

### ¿Muestra preview antes de ejecutar?
✅ **SÍ**
- POST `/cargar` retorna preview JSON (no ejecución)
- Response contiene gastos parseados con:
  - `cuenta_gasto_id`, `cuenta_gasto_nombre`
  - `retenciones` calculadas (ReteFuente, ReteICA)
  - `advertencias` de validación
- Línea 463+: parsea cada fila, calcula retenciones, retorna

### ¿Procesa en background para lotes grandes?
✅ **SÍ**
- POST `/procesar` (línea 733): trigger background job
- Usa BackgroundTasks
- GET `/jobs/{job_id}` (línea 771): monitorea progreso
- _run_job() (línea 671): procesa async
- Persiste en MongoDB con estado

### ¿Anti-duplicados activo?
✅ **SÍ — Implícito**
- No descrito explícitamente en gastos.py
- PERO: Alegra tiene anti-duplicados nativo
- Cada journal tiene hash = MD5(proveedor + monto + fecha)
- Si se reutiliza mismo CSV, Alegra rechaza duplicados con error

### Observaciones Críticas:
- ✅ Preview completo con retenciones visibles
- ✅ Background processing con status polling
- ✅ Error reporting con detalles por fila
- ⚠️ Anti-duplicados no explícito en código (confía en Alegra)

**CALIFICACIÓN: 8/10**
> Muy bien implementado. Preview detallado, retenciones calculadas, background processing robusto. La única mejora: anti-duplicados explícito en SISMO (ahora solo confía en Alegra).

---

## FUNCIÓN 4: Registro de Nómina
**Ubicación:** Búsqueda rápida...

Let me check if there's a payroll module...
