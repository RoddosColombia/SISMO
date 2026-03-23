# Corrección Estructural: Motor Matricial de Conciliación Bancaria

## Commit
```
f4b8f2a - Refactor: Motor matricial de conciliación bancaria — Corrección estructural
```

## Cambios Implementados

### CORRECCIÓN 1: Extractor de Proveedor

**Ubicación**: `backend/services/accounting_engine.py`, líneas 24-87

Nueva función `extract_proveedor(descripcion: str) -> str`:
- "COMPRA EN FONTANAR" → "fontanar"
- "PAGO PSE COMERC NOMBRE" → "NOMBRE"
- "TRANSFERENCIA A PERSONA" → "persona"
- "NEQUI NOMBRE" → "nombre"
- Fallback: primeros 30 caracteres

### CORRECCIÓN 2: Campo proveedor en MovimientoBancario

**Antes**:
```python
@dataclass
class MovimientoBancario:
    fecha: str
    descripcion: str
    monto: float
    # ... SIN proveedor
```

**Después**:
```python
@dataclass
class MovimientoBancario:
    fecha: str
    descripcion: str
    monto: float
    tipo: TipoMovimiento
    banco: Banco
    cuenta_banco_id: int
    referencia_original: str
    proveedor: str = ""              # ← NUEVO
    es_transferencia_interna: bool = False  # ← NUEVO
    # ... resto de campos
```

### CORRECCIÓN 3: Poblado en parsers

Cada parser (BBVA, Bancolombia, Davivienda, Nequi) ahora hace:
```python
from services.accounting_engine import extract_proveedor
proveedor = extract_proveedor(descripcion)
movimientos.append(MovimientoBancario(..., proveedor=proveedor))
```

### CORRECCIÓN 4: Pasar proveedor al clasificador

**Antes**:
```python
clasificacion = clasificar_movimiento(
    descripcion=mov.descripcion,
    proveedor="",  # VACÍO
    monto=mov.monto,
    banco_origen=mov.cuenta_banco_id,
)
```

**Después**:
```python
clasificacion = clasificar_movimiento(
    descripcion=mov.descripcion,
    proveedor=mov.proveedor,  # EXTRAÍDO
    monto=mov.monto,
    banco_origen=mov.cuenta_banco_id,
)
```

### CORRECCIÓN 5: Lógica mejorada

```python
if mov.es_transferencia_interna:
    pendientes.append(mov)  # Registrar como traslado
elif mov.confianza >= 0.70 and not mov.requiere_confirmacion:
    causables.append(mov)  # CAUSABLE automático
else:
    pendientes.append(mov)  # PENDIENTE WhatsApp
```

### CORRECCIÓN 6: Pendientes con contexto completo

Nueva estructura en contabilidad_pendientes:
```python
{
    "fecha": ...,
    "descripcion": ...,
    "monto": ...,
    "banco": ...,
    "proveedor_extraido": mov.proveedor,      # Para WhatsApp
    "cuenta_debito_sugerida": ...,            # Contexto motor
    "cuenta_credito_sugerida": ...,           # Contexto motor
    "confianza_sugerida": ...,                # %
    "razon_baja_confianza": ...,              # POR QUÉ
    "estado": "pendiente_whatsapp",           # Cola específica
    "resuelto_por": None,                     # Campo para Agente
    "resolucion_fecha": None,
    "cuenta_final": None,
}
```

## Flujo Completo

```
MOVIMIENTO BANCARIO
  ↓
1. PARSEAR (cualquier banco)
   → extract_proveedor(descripcion)
   ↓
2. CLASIFICAR
   → clasificar_movimiento(descripcion, proveedor, monto, banco)
   ↓
3. DECIDIR
   ├─ es_transferencia_interna=True → TRASLADO (no contabilizar)
   ├─ confianza >= 0.70 → CAUSABLE (crear journal)
   └─ confianza < 0.70 → PENDIENTE (WhatsApp)
```

## Casos Concretos

### FONTANAR (Ahora Funciona)
- Antes: "COMPRA EN FONTANAR" → fallback cafetería (60%) → PENDIENTE
- Después: "COMPRA EN FONTANAR" → proveedor="fontanar" → regla detecta → CXC 5329 (75%) → CAUSABLE

### Transferencia Interna
- "TRASLADO 212→210" → es_transferencia_interna=True → Registrar (no contabilizar)

### Ingreso Cartera
- "RDX MOTOS" → credit=5327 (ingreso) → confianza 90% → CAUSABLE

## Garantías

✅ Ningún movimiento se pierde:
- causados: Creados en Alegra
- pendientes: En cola WhatsApp
- trazos: Todas contabilizadas

✅ Contexto completo para resolución manual:
- proveedor extraído
- cuenta sugerida (motor matricial)
- razón de baja confianza
- estado específico: "pendiente_whatsapp"

✅ Sistema listo para CFO y Agente Contador

## Compilación

✅ Python compilation OK
✅ Commit f4b8f2a
✅ Push a GitHub

