---
phase: 04-agents-router-scheduler
plan: 06
subsystem: accounting
tags: [accounting_engine, clasificar_gasto_chat, crear_causacion, request_with_verify, retenciones, chat-transaccional]

# Dependency graph
requires:
  - phase: 04-agents-router-scheduler
    plan: 05
    provides: "RED phase TDD test suite for clasificar_gasto_chat and crear_causacion (test_chat_transactional_phase4.py)"
  - phase: 02-consolidacion-capa-alegra
    provides: "AlegraService.request_with_verify() — POST+GET verification contract"

provides:
  - "clasificar_gasto_chat() — clasifica gastos en lenguaje natural usando REGLAS_CLASIFICACION matrix"
  - "AUTORETENEDORES_NIT and SOCIOS_CC constants — Auteco, Andres, Ivan"
  - "crear_causacion: traduce entradas/fecha/descripcion -> entries/date/observations y llama request_with_verify"
  - "Fix: reteica_pct inicializado en calcular_retenciones (NameError preexistente eliminado)"

affects:
  - 04-agents-router-scheduler
  - 05-facturacion
  - 08-smoke-test

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "clasificar_gasto_chat() reutiliza REGLAS_CLASIFICACION matrix — no heuristica manual (CHAT-01)"
    - "Spanish-to-Alegra key translation en crear_causacion: entradas->entries, fecha->date, descripcion->observations"
    - "Socio detection por NIT (SOCIOS_CC) tiene mayor prioridad que clasificacion de gasto"
    - "Fallback cuenta_debito: 5493 (Gastos Generales), NUNCA 5495 — regla inamovible CLAUDE.md"

key-files:
  created: []
  modified:
    - "backend/services/accounting_engine.py"
    - "backend/ai_chat.py"

key-decisions:
  - "clasificar_gasto_chat() agregada al FINAL de accounting_engine.py (despues de formatear_retenciones_para_prompt)"
  - "Socios detectados por NIT en SOCIOS_CC O por nombre en REGLAS_CLASIFICACION['gasto_socio']['proveedores']"
  - "Honorarios PJ detectados por sufijos empresariales (sas, ltda, inversiones, etc.) O NIT que empieza con 8/9"
  - "crear_causacion traduce payload espanol (entradas/fecha/descripcion) a Alegra API (entries/date/observations) ANTES de validacion"
  - "Fix Rule 1: reteica_pct inicializado a 0 antes del bloque if aplica_reteica para evitar NameError"

patterns-established:
  - "Pattern: Deteccion de socio (SOCIOS_CC) antes que cualquier clasificacion de gasto — prioridad maxima"
  - "Pattern: AUTORETENEDORES_NIT como constante de set para O(1) lookup"
  - "Pattern: Traduccion de claves espanol->Alegra en el primer handler especial de la accion"

requirements-completed: [CHAT-01, CHAT-02, CHAT-03, CHAT-04, CHAT-05]

# Metrics
duration: 25min
completed: 2026-03-31
---

# Phase 04 Plan 06: Chat Transaccional Real (GREEN) Summary

**clasificar_gasto_chat() implementada con REGLAS_CLASIFICACION matrix, deteccion Auteco/socios, y crear_causacion traduciendo payload espanol para garantizar request_with_verify — 10/10 tests GREEN**

## Performance

- **Duration:** 25 min
- **Started:** 2026-03-31T03:10:00Z
- **Completed:** 2026-03-31T03:35:00Z
- **Tasks:** 2
- **Files modified:** 2

## Accomplishments

- Implementada `clasificar_gasto_chat()` en `accounting_engine.py` usando la matriz `REGLAS_CLASIFICACION` existente (no heuristica manual — CHAT-01 satisfecho)
- Detecta Auteco NIT 860024781 como autoretenedor (es_autoretenedor=True, retefuente=0) — CHAT-05
- Detecta socios CC 80075452 (Andres) y CC 80086601 (Ivan) -> cuenta 5329 CXC socios, NUNCA gasto operativo — CHAT-05
- `crear_causacion` en `ai_chat.py` ahora traduce `entradas/fecha/descripcion` a `entries/date/observations` antes de validacion, garantizando que el handler existente con `request_with_verify` sea alcanzado — CHAT-04
- Fixed bug: `reteica_pct` no inicializado en `calcular_retenciones` (NameError cuando `aplica_reteica=False`)

## Task Commits

1. **Task 1: implementar clasificar_gasto_chat()** - `588053d` (feat)
2. **Task 2: fix crear_causacion para request_with_verify** - `6377e6d` (fix)

## Files Created/Modified

- `backend/services/accounting_engine.py` — AUTORETENEDORES_NIT, SOCIOS_CC constantes + clasificar_gasto_chat() + fix reteica_pct
- `backend/ai_chat.py` — traduccion entradas/fecha/descripcion en crear_causacion handler

## Decisions Made

- `clasificar_gasto_chat()` prioriza: socio > honorarios > compras > REGLAS_CLASIFICACION keywords > servicios generico > fallback 5493
- Honorarios PJ: detectados por sufijos en nombre del proveedor (sas, ltda, inversiones...) O NIT que empieza con '8' o '9'
- Fix en Task 2 se implemento en el primer handler especial de `crear_causacion` (linea ~3987), NO en la linea 5345 del plan, porque ese era el punto de retorno temprano que impedia llamar `request_with_verify`

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fix reteica_pct NameError en calcular_retenciones**
- **Found during:** Task 1 (verificando tests de clasificar_gasto_chat)
- **Issue:** `reteica_pct` solo se asignaba dentro del bloque `if aplica_reteica:` pero se retornaba incondicionalmente en el dict. Causa: NameError si `aplica_reteica=False`
- **Fix:** Inicializado `reteica_pct = 0` junto con las otras variables al inicio de la funcion
- **Files modified:** backend/services/accounting_engine.py
- **Verification:** test_reteica_siempre_aplica_bogota pasa; calcular_retenciones con aplica_reteica=False no lanza excepcion
- **Committed in:** 588053d (Task 1 commit)

**2. [Rule 1 - Bug] Fix location del payload translation en crear_causacion**
- **Found during:** Task 2 (test_v1_crear_causacion_uses_request_with_verify)
- **Issue:** El plan indicaba cambiar linea 5345 (service.request -> request_with_verify), pero el handler especial de crear_causacion en linea ~3987 ya llama request_with_verify internamente — pero retorna early porque el payload del test usa claves espanolas (entradas/fecha/descripcion) en lugar de las claves Alegra API (entries/date/observations). La funcion jamas llegaba al punto donde se llamaria request_with_verify.
- **Fix:** Traduccion de claves espanol->Alegra agregada AL INICIO del handler especial de crear_causacion (antes de la validacion de entries), permitiendo que el payload del chat agent fluya correctamente al request_with_verify existente
- **Files modified:** backend/ai_chat.py
- **Verification:** test_v1 PASA, request_with_verify_mock.called=True
- **Committed in:** 6377e6d (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug fix reteica_pct, 1 bug fix location de la traduccion de payload)
**Impact on plan:** Ambos fixes necesarios para correccion. El fix en Task 2 fue una interpretacion mas precisa del objetivo del plan (garantizar request_with_verify para crear_causacion) que la solucion literal indicada en el plan (linea 5345 ya estaba cubierta por el handler especial).

## Issues Encountered

- El test `test_build23_f2_chat_transactional.py::test_t2_crear_journal_retorna_id_alegra` falla por `ModuleNotFoundError: No module named 'qrcode'` — problema preexistente en Python 3.14 del worktree, no relacionado con este plan. Los 22 otros tests de ese archivo pasan.

## Next Phase Readiness

- `clasificar_gasto_chat()` lista para ser usada por el CFO agent en el chat para clasificar gastos en lenguaje natural
- `crear_causacion` acepta payload en espanol (formato del chat agent) y garantiza verificacion HTTP 200 via request_with_verify
- Phase 5 (Facturacion) puede continuar sin dependencia de este plan

---
*Phase: 04-agents-router-scheduler*
*Completed: 2026-03-31*
