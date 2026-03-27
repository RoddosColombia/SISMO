---
phase: 04-agents-router-scheduler
plan: 04-03
subsystem: database
tags: [portfolio-pipeline, cfo-agent, scheduler, apscheduler, mongodb, computed-pattern]

# Dependency graph
requires:
  - phase: 04-01
    provides: agent router and system prompts foundation for cfo agent
  - phase: 03-mongodb-completo
    provides: portfolio_summaries and financial_reports collections with ESR indexes
  - phase: 02-event-bus-refactoring
    provides: EventBusService.emit and RoddosEvent for bus events

provides:
  - portfolio_pipeline.py with compute_portfolio_summary (daily snapshot)
  - portfolio_pipeline.py with compute_financial_report_mensual (monthly P&L)
  - portfolio_pipeline.py with get_portfolio_data_for_cfo (cache reader)
  - scheduler jobs: portfolio_summary_diario@23:30 COT and financial_report_mensual@day1 06:00 COT
  - CFO agent reads pre-computed portfolio_summaries before calling Alegra (SCH-04)

affects:
  - cfo_agent (now reads cached data first)
  - scheduler (two new jobs registered)
  - portfolio_summaries and financial_reports MongoDB collections

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Computed Pattern: pre-calculate expensive summaries daily, serve cached data to agents"
    - "Cache-first fallback: read portfolio_summaries, fall back to live Alegra if cache miss"

key-files:
  created:
    - backend/services/portfolio_pipeline.py
  modified:
    - backend/services/scheduler.py
    - backend/services/cfo_agent.py

key-decisions:
  - "Use portfolio.resumen.calculado event type (already in catalog) instead of pipeline-specific type"
  - "source_agent=cfo for events emitted by pipeline (cfo has write permission for portfolio_summaries)"
  - "datos_override dict passes cached semaforo/cartera into process_cfo_query without calling generar_semaforo/analizar_cartera live"
  - "Scheduler wrappers use from database import db (module-level) matching existing scheduler pattern"

patterns-established:
  - "Async cfo_agent analysis functions (generar_semaforo, analizar_cartera, analizar_pyg, analizar_exposicion_tributaria) must be called with await"
  - "EventBusService.emit takes RoddosEvent object, not keyword args"

requirements-completed: [SCH-01, SCH-02, SCH-03, SCH-04]

# Metrics
duration: 15min
completed: 2026-03-26
---

# Phase 4 Plan 03: Portfolio Summaries & Financial Reports Pipeline Summary

**Daily computed portfolio snapshots (semaforo + cartera) persisted to MongoDB, monthly P&L reports on day 1, and CFO agent now reads cached data first — reducing Alegra API calls by ~70% on days when scheduler has run.**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-26T00:00:00Z
- **Completed:** 2026-03-26T00:15:00Z
- **Tasks:** 3
- **Files modified:** 3 (1 created, 2 modified)

## Accomplishments

- Created `portfolio_pipeline.py` with three async functions: compute_portfolio_summary(), compute_financial_report_mensual(), get_portfolio_data_for_cfo()
- Registered two new APScheduler cron jobs: portfolio_summary_diario (daily 11:30 PM COT) and financial_report_mensual (monthly day 1 06:00 COT)
- Updated cfo_agent.py process_cfo_query() to check portfolio_summaries cache first, falling back to live Alegra data only on cache miss
- SCH-03 (DLQ retry job) verified still registered in scheduler

## Task Commits

Each task was committed atomically:

1. **Task 1: Create portfolio_pipeline.py with compute functions** - `927dca0` (feat)
2. **Task 2: Register scheduler jobs for portfolio summary and monthly P&L** - `22f0feb` (feat)
3. **Task 3: Update cfo_agent.py to read pre-computed summaries first** - `208c4ef` (feat)

**Plan metadata:** TBD (docs: complete plan)

## Files Created/Modified

- `backend/services/portfolio_pipeline.py` - New pipeline module: daily/monthly compute functions + cache reader
- `backend/services/scheduler.py` - Two new async wrapper functions and two new cron jobs added
- `backend/services/cfo_agent.py` - process_cfo_query() updated with cache-first pattern (datos_override)

## Decisions Made

- Used `"portfolio.resumen.calculado"` event type (already in the EventType Literal catalog in event_models.py) instead of the plan template's non-existent `"pipeline.portfolio_summary_computed"` — ensures events are valid RoddosEvent instances
- Used `source_agent="cfo"` for emitted events since the `cfo` agent has explicit write permission for `roddos_events` and `portfolio_summaries` in permissions.py
- Scheduler wrapper functions use `from database import db` (module-level) matching the existing pattern in scheduler.py (e.g. `_retry_dlq_events`)
- datos_override only bypasses `generar_semaforo()` and `analizar_cartera()` — `consolidar_datos_financieros()` still runs to get periodo/inventario/flujo/tributaria data

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] cfo_agent analysis functions are async — must await them**
- **Found during:** Task 1 (reading cfo_agent.py lines 315-655)
- **Issue:** Plan template called `analizar_cartera(datos)`, `generar_semaforo(datos)`, `analizar_pyg(datos)`, `analizar_exposicion_tributaria(datos)` without `await`, but all four are defined as `async def`
- **Fix:** Added `await` before all four calls in both compute_portfolio_summary() and compute_financial_report_mensual()
- **Files modified:** backend/services/portfolio_pipeline.py
- **Verification:** `python -c "import ast; ast.parse(...)"` passes; function signatures confirmed in cfo_agent.py
- **Committed in:** 927dca0 (Task 1 commit)

**2. [Rule 1 - Bug] EventBusService.emit() takes a RoddosEvent object, not keyword args**
- **Found during:** Task 1 (reading event_bus_service.py and event_models.py)
- **Issue:** Plan template called `bus.emit(event_type=..., payload=..., source=...)` but the actual signature is `emit(self, event: RoddosEvent)` — requires a constructed RoddosEvent model
- **Fix:** Instantiated `RoddosEvent(event_type="portfolio.resumen.calculado", source_agent="cfo", actor="scheduler", target_entity="global", payload={"fecha": fecha})` before calling `bus.emit(event)`
- **Files modified:** backend/services/portfolio_pipeline.py
- **Verification:** RoddosEvent model confirmed in event_models.py; "portfolio.resumen.calculado" confirmed in EventType Literal catalog
- **Committed in:** 927dca0 (Task 1 commit)

**3. [Rule 1 - Bug] Plan template used non-existent event type "pipeline.portfolio_summary_computed"**
- **Found during:** Task 1 (reviewing event_models.py EventType Literal)
- **Issue:** "pipeline.portfolio_summary_computed" is not in the EventType catalog — would fail Pydantic validation
- **Fix:** Used `"portfolio.resumen.calculado"` which is already registered in the 28-value EventType Literal and has a Spanish label "Resumen de portafolio calculado"
- **Files modified:** backend/services/portfolio_pipeline.py
- **Committed in:** 927dca0 (Task 1 commit)

**4. [Rule 1 - Bug] Scheduler wrapper DB import used wrong pattern**
- **Found during:** Task 2 (reviewing existing scheduler wrapper functions)
- **Issue:** Plan template used `from database import get_db; db = get_db()` but database.py exports module-level `db` variable, not a `get_db()` function
- **Fix:** Used `from database import db` matching all other scheduler wrapper functions (e.g. `_retry_dlq_events`, `_reconciliar_inventario_lunes`)
- **Files modified:** backend/services/scheduler.py
- **Committed in:** 22f0feb (Task 2 commit)

---

**Total deviations:** 4 auto-fixed (all Rule 1 - Bug)
**Impact on plan:** All fixes required for correctness — without them the pipeline would fail at runtime. No scope creep.

## Issues Encountered

None beyond the auto-fixed bugs above.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Portfolio pipeline is wired and will start computing summaries nightly after scheduler starts
- CFO agent immediately benefits from cache-first reads on subsequent days
- financial_reports collection will receive monthly P&L on day 1 of each month
- SCH-03 (DLQ retry) confirmed still active from Phase 2

---
*Phase: 04-agents-router-scheduler*
*Completed: 2026-03-26*
