---
phase: quick
plan: 260324-kaq
type: execute
wave: 1
depends_on: []
files_modified:
  - frontend/src/pages/Loanbook.tsx
  - backend/routers/loanbook.py
autonomous: true
requirements: [RETOMA-EDIT, CUOTA-INICIAL-LEGACY]
must_haves:
  truths:
    - "EditLoanModal muestra seccion Retoma con toggle Si/No, pre-cargada si retoma_valor > 0"
    - "Al guardar con retoma activa, PUT /api/loanbook/{id} persiste campos retoma en MongoDB"
    - "LoanDetail muestra boton 'Registrar cuota inicial' si no existe cuota numero 0 en cuotas[]"
    - "Modal de cuota inicial inserta cuota 0 como pagada en el array cuotas[] del loanbook"
  artifacts:
    - path: "frontend/src/pages/Loanbook.tsx"
      provides: "EditLoanModal con seccion Retoma + CuotaInicialModal"
    - path: "backend/routers/loanbook.py"
      provides: "PUT /{loan_id} acepta campos retoma + POST /{loan_id}/cuota-inicial"
  key_links:
    - from: "EditLoanModal retoma state"
      to: "PUT /api/loanbook/{id}"
      via: "axios.put con campos retoma en body"
      pattern: "retoma_valor|retoma_marca_modelo|retoma_vin|retoma_placa"
    - from: "CuotaInicialModal"
      to: "POST /api/loanbook/{id}/cuota-inicial"
      via: "axios.post inserta cuota 0"
      pattern: "cuota-inicial"
---

<objective>
Agregar seccion RETOMA en EditLoanModal y modal de cuota inicial para loanbooks legacy (LB-2026-0001 a LB-2026-0010 que no tienen cuota numero 0).

Purpose: Los loanbooks existentes necesitan poder agregar/editar informacion de retoma despues de creados, y los legacy necesitan registrar cuota inicial que no fue creada en su momento.
Output: EditLoanModal con toggle Retoma + CuotaInicialModal + endpoints backend actualizados.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@frontend/src/pages/Loanbook.tsx
@backend/routers/loanbook.py

<interfaces>
<!-- Key types and contracts the executor needs -->

From frontend/src/pages/Loanbook.tsx:
```typescript
interface Loan {
  id: string;
  codigo: string;
  moto_descripcion?: string;
  moto_chasis?: string;
  motor?: string;
  cliente_nombre: string;
  cliente_nit?: string;
  tipo_identificacion?: string;
  cliente_telefono?: string;
  plan: string;
  fecha_factura?: string;
  fecha_entrega?: string | null;
  precio_venta?: number;
  cuota_inicial?: number;
  valor_cuota?: number;
  num_cuotas: number;
  cuotas: Cuota[];
  estado: string;
  num_cuotas_pagadas: number;
  total_cobrado?: number;
  saldo_pendiente?: number;
  modo_pago?: string;
  placa?: string;
  // NOTE: retoma fields NOT in Loan interface yet — must add
}

interface Cuota {
  numero: number;
  tipo: string;
  fecha_vencimiento: string;
  valor: number;
  estado: string;
  fecha_pago: string | null;
  valor_pagado?: number;
  comprobante?: string | null;
  notas?: string;
  canal_pago?: string;
  dpd_al_pagar?: number;
}
```

From backend/routers/loanbook.py:
```python
class LoanEdit(BaseModel):
    """Fields editable on an existing loanbook (all optional)."""
    cliente_nombre: Optional[str] = None
    cliente_nit: Optional[str] = None
    tipo_identificacion: Optional[str] = None
    cliente_telefono: Optional[str] = None
    moto_descripcion: Optional[str] = None
    moto_chasis: Optional[str] = None
    motor: Optional[str] = None
    placa: Optional[str] = None
    plan: Optional[str] = None
    modo_pago: Optional[str] = None
    valor_cuota: Optional[float] = None
    fecha_factura: Optional[str] = None
    # NOTE: No retoma fields yet — must add

# PUT /{loan_id} uses raw dict body with EDITABLE whitelist:
EDITABLE = {
    "cliente_nombre", "cliente_nit", "tipo_identificacion", "cliente_telefono",
    "moto_descripcion", "moto_chasis", "motor", "placa",
    "plan", "modo_pago", "valor_cuota", "fecha_factura",
    "numero_factura_alegra",
}
```

From backend/routers/loanbook.py (CreateLoanRequest already has retoma fields):
```python
class CreateLoanRequest(BaseModel):
    tiene_retoma: bool = False
    retoma_marca_modelo: Optional[str] = None
    retoma_vin: Optional[str] = None
    retoma_placa: Optional[str] = None
    retoma_valor: Optional[float] = None
```

Metodos de pago options (from PagoModal):
```
efectivo | transferencia_bancolombia | transferencia_bbva | transferencia_davivienda | transferencia_bogota | nequi | daviplata
```
Plus "retoma" for cuota inicial modal.
</interfaces>
</context>

<tasks>

<task type="auto">
  <name>Task 1: Backend — Retoma en PUT y POST cuota-inicial</name>
  <files>backend/routers/loanbook.py</files>
  <action>
  **1A. Agregar campos retoma al EDITABLE set del PUT /{loan_id} endpoint (linea ~789):**

  Add these keys to the EDITABLE set:
  ```
  "tiene_retoma", "retoma_marca_modelo", "retoma_vin", "retoma_placa", "retoma_valor", "retoma_descripcion"
  ```

  In the PUT handler (after `update_fields` is built, around line 797), add logic:
  - If `tiene_retoma` is in body and is False, also set `retoma_valor: 0, retoma_marca_modelo: None, retoma_vin: None, retoma_placa: None, retoma_descripcion: None` to clean up.
  - If `retoma_marca_modelo` is provided, also set `retoma_descripcion` to the same value (for consistency with Create flow).

  **1B. Create new POST endpoint `/{loan_id}/cuota-inicial`:**

  Add a new Pydantic model:
  ```python
  class CuotaInicialRequest(BaseModel):
      valor: float
      metodo_pago: str = "efectivo"  # efectivo | transferencia_bancolombia | ... | retoma
      fecha: str  # ISO date string
      valor_retoma: Optional[float] = None  # Only if metodo_pago == "retoma"
      notas: Optional[str] = ""
  ```

  Add endpoint:
  ```python
  @router.post("/{loan_id}/cuota-inicial")
  async def registrar_cuota_inicial(loan_id: str, req: CuotaInicialRequest, current_user=Depends(get_current_user)):
  ```

  Logic:
  1. Find loanbook by id. 404 if not found.
  2. Check if cuota numero 0 already exists in cuotas[]: `any(c.get("numero") == 0 for c in loan.get("cuotas", []))`. If exists, raise HTTPException 400 "Este loanbook ya tiene cuota inicial".
  3. Build cuota_0 dict:
     ```python
     cuota_0 = {
         "numero": 0,
         "tipo": "inicial",
         "fecha_vencimiento": req.fecha,
         "valor": req.valor,
         "estado": "pagada",
         "fecha_pago": req.fecha,
         "valor_pagado": req.valor,
         "canal_pago": req.metodo_pago,
         "notas": req.notas or "",
     }
     ```
  4. If `req.metodo_pago == "retoma"` and `req.valor_retoma`:
     - `cuota_0["valor_retoma"] = req.valor_retoma`
     - `cuota_0["notas"] = f"Retoma: ${req.valor_retoma:,.0f}"`
     - Also update loanbook: `retoma_valor = req.valor_retoma`
  5. Insert cuota_0 at position 0 of cuotas array:
     ```python
     await db.loanbook.update_one(
         {"id": loan_id},
         {
             "$push": {"cuotas": {"$each": [cuota_0], "$position": 0}},
             "$set": {"cuota_inicial": req.valor, "updated_at": datetime.now(timezone.utc).isoformat()},
             "$inc": {"num_cuotas_pagadas": 1},
         }
     )
     ```
     If retoma, also `$set` retoma_valor.
  6. Log action and return updated loanbook.
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO && python -c "import ast; ast.parse(open('backend/routers/loanbook.py').read()); print('SYNTAX OK')"</automated>
  </verify>
  <done>PUT /{loan_id} accepts retoma fields. POST /{loan_id}/cuota-inicial creates cuota 0 as paid. Both endpoints parse without syntax errors.</done>
</task>

<task type="auto">
  <name>Task 2: Frontend — Retoma en EditLoanModal + CuotaInicialModal en LoanDetail</name>
  <files>frontend/src/pages/Loanbook.tsx</files>
  <action>
  **2A. Add retoma fields to Loan interface (around line 46):**
  ```typescript
  retoma_valor?: number;
  retoma_descripcion?: string;
  retoma_marca_modelo?: string;
  retoma_vin?: string;
  retoma_placa?: string;
  tiene_retoma?: boolean;
  ```

  **2B. Add Retoma section to EditLoanModal (after "Plan y pago" section, before Actions, around line 748):**

  Add retoma state to EditLoanModal:
  ```typescript
  const [retoma, setRetoma] = useState({
    activo: (loan.retoma_valor && loan.retoma_valor > 0) || loan.tiene_retoma || false,
    marca_modelo: loan.retoma_descripcion || loan.retoma_marca_modelo || "",
    vin: loan.retoma_vin || "",
    placa: loan.retoma_placa || "",
    valor: String(loan.retoma_valor || ""),
  });
  ```

  In handleSave, after existing field comparisons (before the "no changes" check), add:
  ```typescript
  // Retoma fields
  const origRetoma = (loan.retoma_valor && loan.retoma_valor > 0) || loan.tiene_retoma || false;
  if (retoma.activo !== origRetoma) body.tiene_retoma = retoma.activo;
  if (retoma.activo) {
    if (retoma.marca_modelo !== (loan.retoma_descripcion || loan.retoma_marca_modelo || "")) body.retoma_marca_modelo = retoma.marca_modelo;
    if (retoma.vin !== (loan.retoma_vin || "")) body.retoma_vin = retoma.vin;
    if (retoma.placa !== (loan.retoma_placa || "")) body.retoma_placa = retoma.placa;
    const newVal = parseFloat(retoma.valor) || 0;
    if (newVal !== (loan.retoma_valor || 0)) body.retoma_valor = newVal;
  } else if (origRetoma && !retoma.activo) {
    // Clearing retoma
    body.tiene_retoma = false;
  }
  ```

  JSX for Retoma section — follow EXACT same pattern as CreateLoanModal retoma section (lines 1230-1270). Place after "Plan y pago" section, before Actions:
  ```
  {/* Retoma */}
  <p class="text-xs font-semibold text-slate-500 uppercase tracking-wide mt-2">Retoma</p>
  ```
  - Toggle button Si/No (same style as CreateLoanModal lines 1232-1238)
  - If active: Marca/Modelo input, VIN + Placa grid (2 cols), Valor retoma input
  - Use same Tailwind classes as CreateLoanModal retoma section

  **2C. Create CuotaInicialModal component (new component, place before LoanDetail):**

  ```typescript
  const CuotaInicialModal: React.FC<{
    loan: Loan; onClose: () => void; onSuccess: () => void;
  }> = ({ loan, onClose, onSuccess }) => {
  ```

  State:
  ```typescript
  const { token } = useAuth();
  const [loading, setLoading] = useState(false);
  const [form, setForm] = useState({
    valor: String(loan.cuota_inicial || ""),
    metodo_pago: "efectivo",
    fecha: new Date().toISOString().slice(0, 10),
    valor_retoma: "",
    notas: "",
  });
  ```

  Form fields:
  1. Info banner: "Registrar cuota inicial para {loan.codigo} — {loan.cliente_nombre}"
  2. Valor editable (pre-filled with loan.cuota_inicial if exists)
  3. Metodo de pago select: Efectivo, Transferencia Bancolombia, BBVA, Davivienda, Banco Bogota, Nequi, Daviplata, Retoma
  4. Fecha input (type="date", default today)
  5. If metodo_pago === "retoma": show "Valor retoma" number input
  6. Notas (optional)

  Submit handler:
  ```typescript
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const val = parseFloat(form.valor);
    if (!val || val <= 0) { toast.error("Ingresa un valor valido"); return; }
    setLoading(true);
    try {
      const payload: any = { valor: val, metodo_pago: form.metodo_pago, fecha: form.fecha, notas: form.notas };
      if (form.metodo_pago === "retoma" && form.valor_retoma) {
        payload.valor_retoma = parseFloat(form.valor_retoma);
      }
      await axios.post(`${API}/api/loanbook/${loan.id}/cuota-inicial`, payload,
        { headers: { Authorization: `Bearer ${token}` } });
      toast.success("Cuota inicial registrada");
      onSuccess();
    } catch (err: any) {
      toast.error(err.response?.data?.detail || "Error registrando cuota inicial");
    } finally { setLoading(false); }
  };
  ```

  UI: Same modal styling as PagoModal (fixed inset-0 bg-black/50 z-50, white rounded-2xl card, max-w-md). Same button styling (bg-[#00A9E0] for confirm, border for cancel).

  **2D. Add "Registrar cuota inicial" button in LoanDetail:**

  In LoanDetail component, add state:
  ```typescript
  const [showCuotaInicial, setShowCuotaInicial] = useState(false);
  ```

  Detect if cuota 0 is missing: `const hasCuotaInicial = cuotas.some(c => c.numero === 0 || c.tipo === "inicial");`

  In the "Cronograma de cuotas" section (around line 927), BEFORE the cuotas.map, add:
  ```jsx
  {!hasCuotaInicial && loan.plan !== "Contado" && (
    <button onClick={() => setShowCuotaInicial(true)}
      className="w-full mb-3 flex items-center justify-center gap-2 px-4 py-2.5 bg-amber-50 border border-amber-200 text-amber-700 rounded-lg text-sm font-medium hover:bg-amber-100 transition-colors">
      <DollarSign size={14} />
      Registrar cuota inicial
    </button>
  )}
  ```

  At the end of LoanDetail return (where selectedCuota and showEdit modals are rendered), add:
  ```jsx
  {showCuotaInicial && (
    <CuotaInicialModal loan={loan} onClose={() => setShowCuotaInicial(false)}
      onSuccess={() => { setShowCuotaInicial(false); onRefresh(); }} />
  )}
  ```
  </action>
  <verify>
    <automated>cd C:/Users/AndresSanJuan/roddos-workspace/SISMO/frontend && npx tsc --noEmit --pretty 2>&1 | head -30</automated>
  </verify>
  <done>
  - EditLoanModal shows Retoma toggle with Marca/Modelo, VIN, Placa, Valor fields. Pre-loaded if loan already has retoma_valor > 0.
  - LoanDetail shows "Registrar cuota inicial" button when cuota 0 is missing.
  - CuotaInicialModal opens with valor, metodo_pago (including Retoma option), fecha. Submits to POST /api/loanbook/{id}/cuota-inicial.
  - TypeScript compiles without errors.
  </done>
</task>

</tasks>

<verification>
1. Backend syntax: `python -c "import ast; ast.parse(open('backend/routers/loanbook.py').read())"`
2. Frontend types: `cd frontend && npx tsc --noEmit`
3. Manual smoke test:
   - Open loanbook detail for any active loanbook
   - Click edit (pencil icon) -> scroll down -> Retoma toggle visible
   - Toggle "Activo" -> Marca/Modelo, VIN, Placa, Valor fields appear
   - Save -> PUT sends retoma fields
   - Open a legacy loanbook (LB-2026-0001 to 0010) without cuota 0
   - "Registrar cuota inicial" button visible in cuotas section
   - Click -> modal opens with valor, metodo, fecha
   - Select "Retoma" -> valor_retoma field appears
   - Submit -> cuota 0 appears as pagada in timeline
</verification>

<success_criteria>
- EditLoanModal has functional Retoma section with toggle and 4 fields
- Retoma pre-loads from existing loanbook data (retoma_valor > 0)
- PUT /api/loanbook/{id} persists retoma fields to MongoDB
- LoanDetail shows "Registrar cuota inicial" only when cuota 0 is missing
- CuotaInicialModal submits to POST endpoint and inserts cuota 0 as pagada
- Retoma payment method in cuota inicial modal triggers valor_retoma field
- No TypeScript compilation errors, no Python syntax errors
</success_criteria>

<output>
After completion, create `.planning/quick/260324-kaq-agregar-retoma-en-editloanmodal-y-modal-/260324-kaq-SUMMARY.md`
</output>
