---
phase: quick
plan: 260401-d5z
subsystem: knowledge-base
tags: [rag, mongodb, ai_chat, admin-api, retenciones, knowledge-base]
dependency_graph:
  requires: [sismo_knowledge collection, ai_chat.process_chat]
  provides: [KB-SERVICE, KB-SEED, KB-INTEGRATION, KB-ADMIN]
  affects: [backend/ai_chat.py, backend/services/, backend/routers/, init_mongodb_sismo.py]
tech_stack:
  added: [knowledge_base_service.py, admin_kb.py router]
  patterns: [async MongoDB find with $in, OPERATION_TAG_MAP, try/except lazy import guard]
key_files:
  created:
    - backend/services/knowledge_base_service.py
    - backend/routers/admin_kb.py
    - backend/tests/test_knowledge_base.py
  modified:
    - init_mongodb_sismo.py
    - backend/server.py
    - backend/ai_chat.py
decisions:
  - "OPERATION_TAG_MAP: mapeo estatico operacion->tags en el service (no en MongoDB) — mas rapido, no requiere lectura adicional para determinar que buscar"
  - "_kb_get_context importado con try/except al top-level de ai_chat.py — si el modulo falla en CI no rompe el chat"
  - "Tags index agregado en sismo_knowledge — mejora performance del $in query en produccion"
  - "12 nuevas reglas NO reemplazan las 10 existentes — coexisten, los tags granulares permiten busqueda especifica"
metrics:
  duration_minutes: 45
  completed_date: "2026-04-01"
  tasks_completed: 3
  files_created: 3
  files_modified: 3
  tests_written: 11
  tests_passing: 11
---

# Quick Task 260401-d5z: Knowledge Base Service RAG para Agentes — Summary

**One-liner:** Service RAG con MongoDB sismo_knowledge (22 reglas) + intent detection en process_chat() + admin API protegida con require_admin.

## What Was Built

### Task 1: KnowledgeBaseService + Seed Ampliado + TDD

**`backend/services/knowledge_base_service.py`** — Capa RAG con 3 funciones async:
- `get_context_for_operation(operation_type, db)` — Busca reglas via `$in` tags, retorna bloque formateado "== REGLAS APLICABLES =="
- `get_all_rules_by_category(categoria, db)` — Lista reglas por categoria (sin `_id`)
- `upsert_rule(rule_dict, db)` — Crea/actualiza regla con `update_one(upsert=True)`

**`OPERATION_TAG_MAP`** define 6 tipos de operacion:
- `registrar_arriendo` → tags: retenciones, retefuente, arrendamiento, reteica, autoretenedores
- `crear_factura_moto` → tags: VIN, factura, moto, motor
- `registrar_pago_cartera` → tags: cartera, duplicado, pago, mora, cobranza
- `registrar_nomina` → tags: nomina, retefuente, nomina (accent variant)
- `registrar_gasto` → tags: retenciones, autoretenedores, retefuente
- `conciliacion` → tags: bancos, endpoints_alegra, contabilidad

**`init_mongodb_sismo.py`** — SISMO_KNOWLEDGE expandido de 10 a 22 reglas:
| rule_id | categoria | tags principales |
|---------|-----------|-----------------|
| auteco_autoretenedor | impuestos | autoretenedores, auteco |
| endpoint_journals | contabilidad | endpoints_alegra, journals |
| endpoint_categories | contabilidad | endpoints_alegra, categories |
| fechas_alegra | contabilidad | endpoints_alegra, fechas |
| socios_cxc | contabilidad | socios, cxc |
| retefuente_arriendo | impuestos | retefuente, arrendamiento |
| retefuente_servicios | impuestos | retefuente, servicios |
| retefuente_compras | impuestos | retefuente, compras |
| reteica_bogota | impuestos | reteica, retenciones |
| global66_alegra | contabilidad | bancos, global66 |
| vin_motor_factura | contabilidad | VIN, motor, factura |
| mora_diaria | cartera | mora, cartera, cobranza |

Index nuevo: `sismo_knowledge_tags` en campo `tags` (ASC) para optimizar `$in` queries.

### Task 2: Admin API + Integracion process_chat()

**`backend/routers/admin_kb.py`** — 2 endpoints protegidos con `require_admin`:
- `POST /api/admin/knowledge-base/upsert` — crea o actualiza regla
- `GET /api/admin/knowledge-base/{categoria}` — lista reglas de una categoria

**`backend/server.py`** — `admin_kb_router` registrado con patron `try/except` existente.

**`backend/ai_chat.py`** — Integracion en `process_chat()`:
- Import top-level con guard: `try: from services.knowledge_base_service import ... except ImportError: _kb_get_context = None`
- MODULE KB insertado despues del system_prompt assembly, antes de MODULE 4
- Intent detection basado en keywords del mensaje del usuario
- Si hay contexto relevante, se agrega al final del `system_prompt`
- Errores son non-blocking (try/except con `logger.warning`)

### Task 3: Tests E2E de integracion

**`backend/tests/test_knowledge_base.py`** — 11 tests, todos pasan:
- `test_arriendo_produces_retefuente_and_reteica_context` — confirma "3.5%" y "0.414%" en contexto
- `test_factura_moto_produces_vin_context` — confirma "VIN" y "motor" en contexto
- `test_unknown_operation_returns_empty` — operacion desconocida retorna ""
- `test_seed_knowledge_count` — SISMO_KNOWLEDGE >= 22 reglas
- 7 tests adicionales para get_context_for_operation, get_all_rules_by_category, upsert_rule

## Commits

| Hash | Tipo | Descripcion |
|------|------|-------------|
| 675b6ec | test | RED — 11 failing tests for knowledge_base_service RAG |
| 826209a | feat | Task 1 — KnowledgeBaseService + 12 reglas nuevas + tags index |
| 78f2764 | feat | Task 2 — Admin KB router + process_chat() integration |

## Success Criteria — VERIFICADO

- [x] `knowledge_base_service.py` con 3 metodos async funcionales
- [x] 22 reglas en SISMO_KNOWLEDGE (10 existentes + 12 nuevas)
- [x] `process_chat()` inyecta reglas relevantes en `system_prompt` basado en intent
- [x] Admin API funcional (2 endpoints protegidos con `require_admin`)
- [x] Test E2E: `get_context_for_operation("registrar_arriendo")` retorna "3.5%" y "0.414%"
- [x] 11/11 tests pasan

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test test_seed_knowledge_count fallaba por ruta hardcodeada**
- **Found during:** Task 1 GREEN phase
- **Issue:** El test usaba `sys.path.insert(0, "/c/Users/.../agent-ac734c83")` — ruta absoluta no portable
- **Fix:** Calculo dinamico de `_project_root = os.path.dirname(os.path.dirname(_here))`
- **Files modified:** `backend/tests/test_knowledge_base.py`

**2. [Rule 2 - Missing guard] Import `_kb_get_context` con try/except en ai_chat.py**
- **Found during:** Task 2 — ai_chat.py puede ejecutarse en entornos donde el service no esta disponible
- **Fix:** Guard de importacion top-level con fallback `None`, MODULE KB verifica `if _kb_get_context is not None`

None mas — plan ejecutado correctamente.

## Known Stubs

Ninguno. Todos los metodos retornan datos reales desde MongoDB o mocks correctos en tests.

## Self-Check: PASSED
