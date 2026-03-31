---
phase: quick
plan: 260331-9gd
subsystem: backend/ai_chat
tags: [wiring, classification, accounting, chat-transaccional, TDD]
dependency_graph:
  requires: [04-06-clasificar-gasto-chat]
  provides: [WIRE-01]
  affects: [backend/ai_chat.py, backend/tests/test_chat_transactional_phase4.py]
tech_stack:
  added: []
  patterns: [lazy-import, spy-pattern-patch, clasificar_gasto_chat wiring]
key_files:
  created: []
  modified:
    - backend/ai_chat.py
    - backend/tests/test_chat_transactional_phase4.py
decisions:
  - "Patch target for spy is services.accounting_engine.clasificar_gasto_chat (not ai_chat.clasificar_gasto_chat) because lazy import binds locally inside the handler — the function is looked up from the module at call time"
  - "Classification wiring placed BEFORE Spanish-to-Alegra key translation so desc/proveedor/nit/monto are still in Spanish keys when extracted"
  - "Internal keys _clasificacion and _clasificacion_hint stripped via payload.pop() before Alegra POST to avoid API rejection"
metrics:
  duration: "12 minutes"
  completed: "2026-03-31"
  tasks: 2
  files: 2
---

# Quick Task 260331-9gd: Wiring quirurgico — importar y usar clasificar_gasto_chat en crear_causacion Summary

**One-liner:** Lazy-import wiring of clasificar_gasto_chat() + calcular_retenciones() into the crear_causacion handler — high-confidence results (>= 0.7) inject deterministic _clasificacion dict before Alegra POST, internal keys stripped cleanly.

## What Was Built

### Task 1: Wire clasificar_gasto_chat into crear_causacion handler

Modified `backend/ai_chat.py` to add classification logic inside the `crear_causacion` special-case handler:

1. **Lazy import** inside handler: `from services.accounting_engine import clasificar_gasto_chat, calcular_retenciones`
2. **Extract Spanish-key fields** before translation block: `desc_clasif`, `prov_clasif`, `nit_clasif`, `monto_clasif`
3. **Call clasificar_gasto_chat()** with extracted fields
4. **High-confidence (>= 0.7)**: inject `_clasificacion` dict (cuenta_debito, tipo_gasto, retenciones, es_autoretenedor, etc.) + `_clasificacion_hint` string for LLM context
5. **Low-confidence (< 0.7)**: inject hint-only `_clasificacion` without retenciones, LLM decides
6. **Strip internal keys** via `payload.pop("_clasificacion", None)` and `payload.pop("_clasificacion_hint", None)` before the Alegra POST

Key constraints honored:
- Auteco NIT 860024781: `es_autoretenedor=True` detected, propagated to `calcular_retenciones(es_autoretenedor=True)` which yields `retefuente_valor=0`
- Fallback account: 5493 (NUNCA 5495)
- POST target: `/journals` (NUNCA `/journal-entries`)
- Existing translation logic (entradas->entries, fecha->date, descripcion->observations) unchanged

### Task 2: Add 2 integration tests for wiring

Added to `backend/tests/test_chat_transactional_phase4.py`:

- **test_wiring_arriendo_end_to_end**: Spy on `services.accounting_engine.clasificar_gasto_chat`, confirm it's called with arriendo payload, assert `tipo_gasto=arrendamiento`, `cuenta_debito=5480`, `confianza >= 0.7`
- **test_wiring_auteco_no_retefuente**: Same spy pattern with NIT 860024781 (Auteco), assert `es_autoretenedor=True` and `calcular_retenciones(es_autoretenedor=True)` returns `retefuente_valor=0`

## Test Results

```
12 passed in 0.96s (C1-C8 + V1 + reteica + 2 wiring)
29 passed in 1.07s (full verification suite: phase4 + alegra_service)
```

## Commits

| Task | Commit | Message |
|------|--------|---------|
| Task 1 | eed1249 | feat(260331-9gd): wire clasificar_gasto_chat into crear_causacion handler |
| Task 2 | 805c35c | test(260331-9gd): add wiring integration tests for clasificar_gasto_chat |

## Deviations from Plan

### Adjusted patch target (Rule 1 - technical accuracy)

**Found during:** Task 2
**Issue:** Plan's spy pattern proposed patching `ai_chat.clasificar_gasto_chat`, but since Task 1 uses a lazy import *inside* the handler function, the name is bound locally at call time from the source module — not stored at module level in `ai_chat`.
**Fix:** Changed patch target to `services.accounting_engine.clasificar_gasto_chat` which is where the function object lives. The `from services.accounting_engine import clasificar_gasto_chat` inside the handler resolves the reference at each call, so patching the source works correctly.
**Files modified:** backend/tests/test_chat_transactional_phase4.py

The plan explicitly anticipated this: "Adjust patch target to match the actual import pattern used in Task 1."

## Known Stubs

None. All classification data flows from real `clasificar_gasto_chat()` and `calcular_retenciones()` implementations.

## Self-Check: PASSED

- [x] backend/ai_chat.py modified with classification wiring
- [x] backend/tests/test_chat_transactional_phase4.py has 12 tests (was 10)
- [x] Commit eed1249 exists: `git log --oneline | grep eed1249`
- [x] Commit 805c35c exists: `git log --oneline | grep 805c35c`
- [x] No forbidden patterns: journal-entries (only in comments), app.alegra.com/api/r1 (0 results in code), 5495 as default (never — fallback is 5493)
