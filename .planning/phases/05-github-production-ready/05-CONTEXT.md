# Phase 5: GitHub Production-Ready - Context

**Gathered:** 2026-03-26
**Status:** Ready for planning

<domain>
## Phase Boundary

Expand CI/CD with pytest (BUILD 24 suite only), smoke test (unit + curl post-deploy), Dependabot, improve /api/health/smoke endpoint, and fully rewrite README + update CLAUDE.md to reflect BUILD 24.

</domain>

<decisions>
## Implementation Decisions

### pytest in CI
- **D-01:** CI runs only the BUILD 24 test suite — 5 files: `test_permissions.py`, `test_event_bus.py`, `test_mongodb_init.py`, `test_phase4_agents.py`, `test_smoke_build24.py` (~65 tests total). No legacy tests from BUILD 18–23.
- **D-02:** Tests use mocks/mongomock — no live MongoDB Atlas connection required in CI. test_smoke_build24.py unit-tests the endpoint logic directly (imports the function, calls it with mocks). No secrets needed.

### Smoke Test Architecture
- **D-03:** Two complementary smoke test mechanisms:
  1. **pytest unit (job principal):** `test_smoke_build24.py` mocks the DB/bus and tests `/api/health/smoke` logic. Runs alongside all other BUILD 24 tests in the main pytest job.
  2. **curl post-deploy (job separado):** Waits 90s after Render deploy, then hits the real endpoint with curl + jq. Verifies: `status="ok"`, `collections_count>=30`, `bus_status="ok"`.
- **D-04:** curl post-deploy job activates only on `push: branches: [main]`. Not triggered on PRs or push to develop.
- **D-05:** Render backend URL: `https://sismo-backend-40ca.onrender.com/api/health/smoke`

### /api/health/smoke Endpoint
- **D-06:** Improve to return structured checks (per GIT-04): collections presence, bus health, indices validation, catalogo_planes presence. Must return `collections_count`, `bus_status`, `status` fields at minimum (needed by D-03 curl check).

### README Rewrite
- **D-07:** Full rewrite — not a surgical cleanup. The current README has wrong identity ("concesionario de motos Auteco", "BUILD 18", "Emergent LLM Key", "React 18"). All must be replaced.
- **D-08:** Required sections in new README:
  1. **Qué es SISMO/RODDOS** — SISMO como orquestador de agentes IA para RODDOS fintech de movilidad sostenible. Cartera $94M COP, 34 motos TVS, cobro 100% remoto. Principio: Soberanía Digital.
  2. **Stack BUILD 24** — Tabla correcta: FastAPI + React 19 + MongoDB Atlas + Claude Sonnet + Mercately + Render.
  3. **Los 4 agentes core** — Contador (Alegra), CFO (análisis financiero), RADAR (cobranza WhatsApp), Loanbook (ciclo de crédito). Breve descripción de cada uno.
  4. **Cómo correr el proyecto** — Setup local, variables de entorno necesarias, comando de inicio.

### CLAUDE.md Update
- **D-09:** Document new bus protocol: use `bus.emit()` not `emit_event()` or `emit_state_change()` (per GIT-06). Document worktrees workflow. Document known errors and solutions.

### Dependabot
- **D-10:** Create `.github/dependabot.yml` monitoring pip (backend/) and npm (frontend/) per GIT-03. Weekly update schedule.

### Claude's Discretion
- Exact ci.yml job structure and step names
- mongomock vs pytest-mock strategy for test_smoke_build24.py
- dependabot.yml schedule (weekly vs daily) and target branches
- CLAUDE.md exact error documentation content
- anti-pending-status check implementation (grep pattern)

</decisions>

<canonical_refs>
## Canonical References

**Downstream agents MUST read these before planning or implementing.**

### Current CI (to expand)
- `.github/workflows/ci.yml` — Existing pipeline: backend syntax check + anti-emergent + frontend TypeScript check. Add pytest job + curl post-deploy job.

### Health endpoint (to improve)
- `backend/routers/health.py` — Current /api/health/smoke implementation. Add collections_count, bus_status, indices check, catalogo_planes check.

### README (to rewrite)
- `README.md` — Current content: wrong identity, BUILD 18, Emergent. Full rewrite required.

### Test files (BUILD 24 suite — what CI must run)
- `backend/tests/test_permissions.py` — 8 tests (Phase 1)
- `backend/tests/test_event_bus.py` — 11 tests (Phase 2)
- `backend/tests/test_mongodb_init.py` — 13 tests (Phase 3)
- `backend/tests/test_phase4_agents.py` — 28 tests (Phase 4)
- `backend/tests/test_smoke_build24.py` — 6 tests (to create this phase, TST-05)

### Requirements
- `.planning/REQUIREMENTS.md` §GitHub CI/CD (GIT-01 to GIT-06) + §Tests TST-05

</canonical_refs>

<code_context>
## Existing Code Insights

### Reusable Assets
- `.github/workflows/ci.yml`: Existing anti-emergent check pattern (`grep -r "emergentintegrations"`) — reuse same pattern for anti-pending-status check
- `backend/tests/test_smoke_20.py`: Existing smoke test from prior build — reference for pattern but do NOT run in CI
- `backend/routers/health.py`: Existing /api/health/smoke to extend with new checks

### Established Patterns
- CI jobs use `cd backend && python -m py_compile` pattern — reuse for syntax check
- Anti-emergent check uses `grep -r + exit 1` — same pattern for anti-pending check
- Tests in `backend/tests/` directory

### Integration Points
- ci.yml: Add `pytest-job` after existing checks, add `smoke-post-deploy` job with `if: github.ref == 'refs/heads/main'`
- health.py: Extend existing `/api/health/smoke` route with additional MongoDB checks
- `.github/dependabot.yml`: New file alongside ci.yml

</code_context>

<specifics>
## Specific Ideas

- curl post-deploy: `curl https://sismo-backend-40ca.onrender.com/api/health/smoke` with 90s sleep after deploy trigger
- curl check fields: `status == "ok"`, `collections_count >= 30`, `bus_status == "ok"`
- README must explicitly NOT contain: "Emergent", "BUILD 18", "concesionario", "Auteco", "React 18"

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>

---

*Phase: 05-github-production-ready*
*Context gathered: 2026-03-26*
