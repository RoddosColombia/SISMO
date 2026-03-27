# Phase 5: GitHub Production-Ready - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-03-26
**Phase:** 05-github-production-ready
**Areas discussed:** pytest scope en CI, Smoke test en CI, README update depth

---

## pytest scope en CI

| Option | Description | Selected |
|--------|-------------|----------|
| Solo build24 suite | ~65 tests, 5 archivos BUILD 24, rápido, sin ruido de tests viejos | ✓ |
| Todos los tests | pytest backend/tests/ completo (~20+ archivos, BUILD 18-23 incluidos) | |
| Build24 + smoke regression | Build24 + tests estables de builds anteriores seleccionados | |

**User's choice:** Solo build24 suite

---

## Conexión MongoDB en CI

| Option | Description | Selected |
|--------|-------------|----------|
| Secrets en GitHub Actions | MONGO_URL como repository secret, tests se saltan si no existen | |
| Tests mock sin MongoDB | mongomock/mocks — tests pasan sin DB real | ✓ |
| Solo en main, no en PRs | pytest solo corre en push a main/develop | |

**User's choice:** Tests mock sin MongoDB — sin dependencia de secrets externos

---

## Smoke test en CI

| Option | Description | Selected |
|--------|-------------|----------|
| Pytest contra endpoint | Levantar servidor en CI, hit /api/health/smoke con httpx | |
| Solo pytest unit tests | Unit-testea la lógica del endpoint con mocks, sin servidor | |
| Ambos (arquitectura dual) | pytest unit EN el job principal + curl post-deploy en job separado | ✓ |

**User's choice:** Arquitectura dual — complementaria:
1. pytest unit (sin servidor): test_smoke_build24.py con mocks en job principal
2. curl post-deploy: job separado, solo push a main, sleep 90s, verifica https://sismo-backend-40ca.onrender.com/api/health/smoke con curl + jq

---

## Trigger curl post-deploy

| Option | Description | Selected |
|--------|-------------|----------|
| Solo en push a main | Deploy a Render solo desde main | ✓ |
| En push a main y develop | Si hay staging env en develop | |

**User's choice:** Solo en push a main

---

## README update depth

| Option | Description | Selected |
|--------|-------------|----------|
| Rewrite completo | Reescribir desde cero con identidad SISMO/RODDOS correcta | ✓ |
| Limpieza quirúrgica | Solo remover Emergent, BUILD 18, React 18 referencias | |

**User's choice:** Rewrite completo

---

## README secciones

| Option | Description | Selected |
|--------|-------------|----------|
| Qué es SISMO/RODDOS | Identidad: orquestador IA, fintech, $94M, Soberanía Digital | ✓ |
| Stack BUILD 24 | Tabla tecnologías correcta | ✓ |
| Los 4 agentes core | Contador, CFO, RADAR, Loanbook | ✓ |
| Cómo correr el proyecto | Setup local, env vars, comandos | ✓ |

---

## Claude's Discretion

- Estructura exacta de jobs en ci.yml
- Estrategia mongomock vs pytest-mock para test_smoke_build24.py
- Schedule dependabot.yml (weekly vs daily)
- Contenido exacto de errores documentados en CLAUDE.md
- Implementación del anti-pending-status check (patrón grep)

## Deferred Ideas

Ninguna — discusión se mantuvo dentro del scope de la fase.
