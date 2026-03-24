---
phase: quick
plan: 260324-kaq
subsystem: loanbook
tags: [retoma, cuota-inicial, editloanmodal, frontend, backend]
dependency_graph:
  requires: []
  provides: [EditLoanModal con seccion Retoma, CuotaInicialModal, PUT retoma fields, POST cuota-inicial]
  affects: [frontend/src/pages/Loanbook.tsx, backend/routers/loanbook.py]
tech_stack:
  added: []
  patterns: [toggle state pattern, axios.post con payload condicional, $push $position MongoDB]
key_files:
  created: []
  modified:
    - frontend/src/pages/Loanbook.tsx
    - backend/routers/loanbook.py
decisions:
  - "Toggle retoma en EditLoanModal sigue mismo patron visual que CreateLoanModal para consistencia"
  - "CuotaInicialModal inserta cuota 0 con tipo=inicial para distinguirla de cuotas regulares"
  - "PUT endpoint limpia todos los campos retoma cuando tiene_retoma=False para evitar datos huerfanos"
metrics:
  duration: 8min
  completed: 2026-03-24
  tasks_completed: 2
  files_modified: 2
---

# Quick Task 260324-kaq: Retoma en EditLoanModal + Modal Cuota Inicial

**One-liner:** Toggle retoma en EditLoanModal con 4 campos (Marca/Modelo, VIN, Placa, Valor) + CuotaInicialModal que inserta cuota 0 como pagada via POST /api/loanbook/{id}/cuota-inicial.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Backend — Retoma en PUT y POST cuota-inicial | c49f2bb | backend/routers/loanbook.py |
| 2 | Frontend — Retoma en EditLoanModal + CuotaInicialModal | 24dfbd6 | frontend/src/pages/Loanbook.tsx |

## What Was Built

### Backend (c49f2bb)

**PUT /{loan_id} — retoma fields:**
- Agrego 6 campos al EDITABLE set: `tiene_retoma`, `retoma_marca_modelo`, `retoma_vin`, `retoma_placa`, `retoma_valor`, `retoma_descripcion`
- Manejo especial para `tiene_retoma=False` (booleano falsy no pasa el filtro `v is not None`)
- Cleanup automatico: si `tiene_retoma=False`, limpia todos los campos retoma en MongoDB
- Sincroniza `retoma_descripcion` con `retoma_marca_modelo` para consistencia con flujo Create

**Nueva clase CuotaInicialRequest:**
```python
class CuotaInicialRequest(BaseModel):
    valor: float
    metodo_pago: str = "efectivo"
    fecha: str
    valor_retoma: Optional[float] = None
    notas: Optional[str] = ""
```

**Nuevo endpoint POST /{loan_id}/cuota-inicial:**
- Verifica que cuota 0 no exista (400 si ya existe)
- Inserta cuota_0 en posicion 0 del array cuotas con `$push $each $position`
- Si metodo_pago=retoma: guarda valor_retoma en cuota y actualiza retoma_valor del loanbook
- Incrementa num_cuotas_pagadas con `$inc`
- Retorna loanbook actualizado con stats recalculadas

### Frontend (24dfbd6)

**Interfaces actualizadas:**
- `Cuota`: agrego `dias_mora`, `mora_total`, `valor_retoma` (corrigio 4 errores TypeScript preexistentes)
- `Loan`: agrego 6 campos retoma + `numero_factura_alegra` + `total_mora`

**EditLoanModal — estado retoma:**
```typescript
const [retoma, setRetoma] = useState({
  activo: (loan.retoma_valor != null && loan.retoma_valor > 0) || loan.tiene_retoma || false,
  marca_modelo: loan.retoma_descripcion || loan.retoma_marca_modelo || "",
  ...
});
```

**EditLoanModal — seccion Retoma (JSX):** Toggle Si/No + campos condicionales Marca/Modelo, VIN, Placa, Valor.

**CuotaInicialModal:** Modal completo con valor, metodo_pago (8 opciones inc. Retoma), campo valor_retoma condicional, fecha, notas.

**LoanDetail:**
- `hasCuotaInicial = cuotas.some(c => c.numero === 0 || c.tipo === "inicial")`
- Boton amber "Registrar cuota inicial" visible solo cuando `!hasCuotaInicial && loan.plan !== "Contado"`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 2 - Missing Types] Campos faltantes en Cuota interface causaban 4 errores TypeScript**
- **Found during:** Task 2 verification (tsc --noEmit)
- **Issue:** `dias_mora`, `mora_total` usados en JSX de LoanDetail pero no declarados en Cuota interface
- **Fix:** Agrego `dias_mora?: number`, `mora_total?: number`, `valor_retoma?: number` a Cuota interface
- **Files modified:** frontend/src/pages/Loanbook.tsx
- **Commit:** 24dfbd6 (incluido en mismo commit de tarea)

## Known Stubs

None — todos los campos estan conectados a endpoints reales.

## Self-Check: PASSED

- `c49f2bb` backend commit: FOUND
- `24dfbd6` frontend commit: FOUND
- `backend/routers/loanbook.py` — EDITABLE set expandido, CuotaInicialRequest model, POST endpoint: VERIFIED (python -c ast.parse)
- `frontend/src/pages/Loanbook.tsx` — TypeScript compiles without errors: VERIFIED (tsc --noEmit)
