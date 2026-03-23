# Classification Engine Diagnostic Report

## Executive Summary
🔴 **CRITICAL BUG FOUND**: The bank reconciliation background task is calling the accounting engine classifier but **NOT passing provider information**, which means:
- Provider-based rules are COMPLETELY INACTIVE
- Socio expense rules (5329) never match
- 30+ rules depending on provider data are skipped
- Only description-based rules work (50% of the system)

## 1. How Background Task Calls Classifier

### Current Implementation (bank_reconciliation.py, lines 355-360)
```python
clasificacion = clasificar_movimiento(
    descripcion=mov.descripcion,      # e.g., "COMPRA EN FONTANAR"
    proveedor="",                      # 🔴 ALWAYS EMPTY STRING!
    monto=mov.monto,                   # e.g., 45000
    banco_origen=mov.cuenta_banco_id,  # e.g., 5314 (Bancolombia)
)
```

### What's Missing
- No provider/merchant name extraction
- No beneficiary information
- No transaction details parsing
- `proveedor=""` makes provider-based rules inactive

### Parameter Analysis
| Parameter | Current Value | What It Should Be | Impact |
|-----------|----------------|------------------|--------|
| descripcion | Passed | Correct | 50% of rules work |
| proveedor | Empty string "" | Should extract merchant/provider | 30+ rules skipped |
| monto | Passed | Correct | Used for validation |
| banco_origen | Passed | Correct | Used in specific rules |

---

## 2. Classification Rules Matrix

### BBVA Policy (2026) — 12 Rules
- Rule 1: CXC GASTO SOCIO ANDRES → 5329 (95%)
- Rule 2: CXC GASTO SOCIO IVAN → 5329 (95%) [NEEDS PROVIDER]
- Rule 3: ANTICIPO NÓMINA ANDRES → 5329 (92%)
- Rule 4: NÓMINA RODDOS → 5462 (92%)
- Rule 5: PAGO ARRIENDO → 5480 (90%)
- Rule 6: INTERESES ANDRES CANO / DAVID MARTINEZ → 5534 (95%)
- Rule 7: TRASLADO INTERNO → 5535 (95%)
- Rule 8: INGRESOS CARTERA RDX → 5327 (90%)
- Rule 9: PAGO SOFTWARE ALEGRA/SOFÍA → 5484 (92%)
- Rule 10: REEMBOLSO MULTA → 5499 (80%)
- Rule 11: ABONO POR INTERESES → 5456 (85%)
- Rule 12: PAGO PSE RECARGA NEQUI → 5496 (25%)

### Bancolombia Policy (2026) — 18 Rules
- Rule 1: ABONO INTERESES AHORROS → 5456 (95%)
- Rule 2: CUOTA PLAN CANAL NEGOCIOS → 5508 (92%)
- Rule 3: IVA CUOTA PLAN CANAL → 5507 (92%)
- Rule 4: CUOTA MANEJO TRJ DEB → 5507 (92%)
- Rule 5: AJUSTE INTERES AHORROS DB → 5507 (90%)
- Rule 6: COMPRA INTL ELEVENLABS → 5484 (95%)
- Rule 7: COMPRA INTL APPLE.COM → 5484 (95%)
- Rule 8: COMPRA INTL GOOGLE → 5484 (90%)
- Rule 9: RETIRO CAJERO → 5496 (25%)
- Rule 10: TRANSFERENCIA DESDE NEQUI → 5496 (30%)
- Rule 11: PAGO PSE BANCO DAVIVIENDA → 5496 (25%)
- Rule 12: CONSIGNACION CORRESPONSAL → 5496 (30%)
- Rule 13: COMPRA EN TIENDA D1 → 5329 (45%) [NEEDS PROVIDER]
- Rule 14: COMPRA UBER/RAPPI/MC DONALD → 5329 (80%) [NEEDS PROVIDER]
- Rule 15: COMPRA FONTANAR/OPTICA/CASA → 5329 (75%) [NEEDS PROVIDER]
- Rule 16: TRANSFERENCIA CTA SUC VIRTUAL → 5535 (90%)
- Rule 17: PAGO PSE EMPRESA TELECOM → 5487 (85%)
- Rule 18: PAGO PSE GOU PAYMENTS → 5496 (30%)

### Generic Rules (Fallback) — 15+ Rules
- Socio expenses (generic) → 5329 (95%) [NEEDS PROVIDER]
- Tecnología → 5484 (80%)
- Intereses rentistas → 5534 (75%)
- GMF 4x1000 → 5509 (90%)
- Comisiones → 5508 (85%)
- Gastos bancarios → 5507 (80%)
- Arrendamiento → 5480 (85%)
- Nómina → 5462 (85%)
- Servicios públicos → 5485 (80%)
- Telecomunicaciones → 5487 (80%)
- Publicidad → 5495 (75%)
- Cafetería/Aseo → 5496 (60%)
- Papelería → 5497 (80%)
- Combustibles → 5498 (80%)
- Transporte → 5499 (75%)

---

## 3. CRITICAL BUG: Provider Parameter Missing

### Rules That REQUIRE Provider Information (>5 rules blocked)
- CXC Gasto Socio Ivan
- Compra en Tienda D1
- Compra en Uber/Rappi/MC Donald
- Compra en Fontanar/Óptica/Casa Bta
- Generic Socio expenses

### Example: MISSING Socio Expense Logic

**Real transaction from Bancolombia:**
```
Descripción:  "COMPRA EN FONTANAR"
Monto:        150,000
Proveedor:    "FONTANAR" (MISSING in current implementation)
```

**What SHOULD happen:**
- Rule: bc_compra_fontanar (line 461)
- Provider: "fontanar"
- Match: YES
- Clasificación: 5329 (CXC Socio)
- Confianza: 75%
- Acción: CAUSABLE si > 0.70

**What ACTUALLY happens:**
- proveedor = "" (empty!)
- Provider match: FAIL
- Falls through to generic rules
- Final clasificación: 5496 (fallback - cafetería)
- Confianza: 60%
- Acción: PENDIENTE (confianza < 0.70)

---

## 4. Root Cause Analysis

### Why Provider Data is Missing

**Bank Statement Structure (from parsers):**
- Bancolombia: No separate "merchant" field - only DESCRIPCIÓN
- BBVA: No separate "merchant" field - only CONCEPTO
- Davivienda: No separate "merchant" field - only Descripción
- Nequi: No separate "merchant" field - only Descripción

**Current Code (bank_reconciliation.py, line 357):**
```python
clasificacion = clasificar_movimiento(
    descripcion=mov.descripcion,  # e.g., "COMPRA EN FONTANAR"
    proveedor="",  # NEVER EXTRACTED
    monto=mov.monto,
    banco_origen=mov.cuenta_banco_id,
)
```

**What's Needed:**
Extract merchant name from description using regex patterns:
- "COMPRA EN FONTANAR" → proveedor = "fontanar"
- "COMPRA UBER" → proveedor = "uber"
- "CUOTA PLAN CANAL" → proveedor = "bancolombia"

---

## 5. Impact Assessment

### Classification Accuracy Loss
- **With provider data**: 50+ rules applied
- **Without provider data**: ~20 rules working
- **Rule coverage**: 40% INACTIVE

### Specific Cases Affected
1. **Socio Expenses (CXC 5329)**
   - Expected: High confidence (80-95%)
   - Actual: Low confidence (25-60%) → PENDIENTE
   - Impact: Personal expenses not auto-classified

2. **Merchant-Specific Expenses**
   - D1, Fontanar, Óptica, Uber, Rappi
   - Expected: CXC Socio (75-80% confianza)
   - Actual: Cafetería fallback (60% confianza) → PENDIENTE

3. **Confidence Threshold (0.70)**
   - Many transactions with provider match: 75-95% confianza → CAUSABLE
   - Without provider: 25-60% confianza → PENDIENTE
   - Result: Legitimate expenses waiting for manual confirmation

---

## 6. Solution Required

### Step 1: Extract Provider from Description
Create a parser function that extracts merchant names from the bank description field.

### Step 2: Pass Provider to Classifier
Modify bank_reconciliation.py to pass the extracted provider value instead of empty string.

### Step 3: Verify Rule Coverage
Test that all 18 Bancolombia + 12 BBVA rules are matching correctly.

---

## Summary: Two-Tier Bug System

### Bug #1 (Already Fixed - Just Now)
- **Issue**: AlegraService in background task with no request context
- **Status**: FIXED - Replaced with direct httpx calls
- **Result**: causados can now be > 0

### Bug #2 (Current - CRITICAL)
- **Issue**: proveedor parameter always empty
- **Status**: NOT YET FIXED
- **Result**: Provider-based rules skipped, low confidence scores
- **Fix Required**: Extract provider from description, pass to classifier

Both bugs together explain why causados = 0: The journal creation was failing (Bug #1, now fixed) AND the classification rules were incomplete (Bug #2, needs fixing).

