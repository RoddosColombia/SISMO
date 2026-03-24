# Project Research Summary

**Project:** SISMO — Sistema Inteligente de Soporte y Monitoreo Operativo (RODDOS S.A.S.)
**Domain:** Fintech lending operations automation — motorcycle portfolio, Colombia
**Researched:** 2026-03-24
**Confidence:** HIGH (architecture and pitfalls from direct codebase analysis; stack and features from codebase + domain knowledge)

## Executive Summary

SISMO is a production fintech system managing a $94M COP motorcycle loan portfolio for a 2-5 person Colombian operator. At BUILD 23, the system already has substantial capability: loanbook management, AI-assisted accounting classification, Alegra integration, WhatsApp collection via Mercately, and a CFO dashboard. The three active milestones do not build a new system — they complete, harden, and autonomize one that exists but has correctness gaps and tech debt that are preventing reliable operation. The recommended approach is sequential hardening: fix the known bugs that break accounting accuracy first, then build the portfolio intelligence layer on clean data, then pursue infrastructure sovereignty once the codebase is stable enough to safely containerize.

The critical insight across all research files is that SISMO has a structural accuracy problem, not a missing-feature problem. The bank reconciliation proveedor extraction bug silently disables 30+ classification rules. The loanbook state machine lacks concurrency guards. The ai_chat.py monolith (5,217 lines) is a single point of failure for all agent intelligence. Smoke test 20/20 (Agente Contador) is the forcing function that will reveal and prove resolution of these gaps before any new automation is added on top of broken foundations.

The primary risk vector is financial data corruption: duplicate Alegra entries from non-idempotent retries, stale cache after multi-worker deployment, and low-confidence classifications auto-posted to the accounting ledger. Every new capability added before these structural issues are resolved increases the blast radius of a financial integrity failure. The recommended mitigation is an explicit confidence gate (70% for auto-post, 90% for high-value transactions), MongoDB optimistic locking on FSM transitions, and a dead-letter queue for webhook event loss before any mass automation goes live.

## Key Findings

### Recommended Stack

The existing stack is locked in production and must not be replaced. New additions are minimal and precisely scoped: pytest 8.3 + pytest-asyncio + pytest-mock for the smoke test infrastructure in Phase 1; pandas (already installed) + numpy for portfolio analytics in Phase 2; Docker + Docker Compose + Nginx + Certbot + MongoDB Community 7.0 + Prometheus + Grafana for infrastructure sovereignty in Phase 3. No new application framework, no ORM migration, no queue system unless multi-process scaling requires Redis for cache coherence.

**Core technologies (existing — do not change):**
- FastAPI + Python 3.11: async API layer, all routers and agents
- MongoDB Atlas + Motor: document store and event bus (roddos_events append-only collection)
- Claude Sonnet via Anthropic SDK: AI classification and agent orchestration
- Alegra API: accounting system of record — every journal entry must post here, not just to MongoDB
- APScheduler 3.10.4: 12 CRON jobs including daily DPD calculation at 06:00 Bogota time
- Mercately: WhatsApp delivery for collection workflows

**Phase 1 additions:**
- pytest 8.3 + pytest-asyncio 0.23 + pytest-mock 3.14: smoke test runner — canonical async FastAPI testing stack, no alternative considered

**Phase 2 additions:**
- numpy 1.26: numerical operations for IRR/NPV and risk metrics — pandas dependency, likely already present
- scipy 1.13: optional statistical modeling — defer until Phase 2 design is concrete; pandas alone may suffice

**Phase 3 additions:**
- Docker 27 + Docker Compose 2: containerization for self-hosted deployment
- Nginx 1.26 + Certbot 3: reverse proxy and TLS — battle-tested, Nginx preferred over Caddy for Spanish-language documentation availability
- MongoDB Community 7.0: drop-in Atlas replacement via connection string swap
- Prometheus 2.53 + Grafana 11 + prometheus-fastapi-instrumentator 0.6: self-hosted observability
- GlitchTip 4: self-hosted error tracking (Sentry-compatible) — MEDIUM confidence, verify stability before committing

### Expected Features

**Must have (table stakes) — most already exist but need hardening:**
- Cuota schedule generation with accurate delivery-date edge cases
- Payment registration with reliable Alegra sync (cache invalidation bug present)
- DPD tracking surfaced cleanly (concept exists; needs clean exposure)
- Overdue detection and collection queue (RADAR partial; needs completion)
- WhatsApp payment reminders with suppression window for manual contacts
- Loan state machine with FSM enforcement and concurrency guards
- Bank extract reconciliation at 90%+ match rate (currently ~60% due to proveedor bug)
- P&L statement reliability (CFO estrategico exists; correctness gaps remain)
- Cuota recalculation after partial payment or grace period (BUILD 23 adds endpoint; needs validation)

**Should have (differentiators per active milestone):**

Phase 1 — Complete Financial System:
- Smoke test 20/20 with real Alegra IDs (validates accounting completeness end-to-end)
- Expense causation from Telegram photo (closes most common daily operation loop)
- Bank extract auto-reconciliation at 95%+ match (eliminates manual matching)
- Accounting classification learning loop from operator corrections

Phase 2 — Portfolio Intelligence:
- Portfolio health dashboard with DPD buckets (0/1-30/31-60/61-90/90+)
- WhatsApp auto-response with balance and next cuota (saldo + proxima cuota)
- Collection prioritization queue with next-best-action recommendation
- Early warning semaforo based on behavioral patterns

Phase 3 — Digital Sovereignty:
- Self-hosted Docker Compose deployment (removes Render dependency)
- Encrypted secrets management (removes .env credential exposure)
- Audit trail export in immutable format (legal protection)
- Circuit breaker for Mercately outages (resilience without full migration)

**Defer (v2+):**
- DIAN auto-causation: correct decision to stub until habilitacion certificate acquired
- Predictive credit scoring at origination: SISMO is operations, not origination
- Self-hosted LLM (Ollama): evaluate only after Contador reaches 95%+ accuracy baseline
- Customer-facing portal: WhatsApp IS the customer channel in Colombia
- Full Mercately replacement: only migrate with evidence of risk; working system
- Cohort recovery analysis: requires 6+ months of clean data accumulation

### Architecture Approach

SISMO uses a Layered Monolith with Event Bus pattern. The FastAPI router layer delegates to an Agent Orchestration layer (currently the 5,217-line ai_chat.py) which dispatches actions to specialized agents (Contador, CFO, RADAR, Loanbook). All state changes emit events to the append-only roddos_events MongoDB collection, which serves as the audit trail. External integrations (Alegra, Mercately, Anthropic) are downstream of this bus. The target architecture for the next milestone adds three vertical capability layers on top of the existing bus without changing the fundamental pattern — this is the right call, as the bus architecture is sound and the issues are in correctness, not structure.

**Major components (existing):**
1. `ai_chat.py` (5,217 lines): LLM orchestration, context building, action execution — must be split before adding new agent capabilities
2. `accounting_engine.py`: 50+ rule-based classification with confidence scoring — proveedor bug currently disabling 30+ rules
3. `bank_reconciliation.py`: multi-bank extract parsing and Alegra journal creation — blocked by proveedor extraction call missing at line 357
4. `loanbook_scheduler.py`: 12 CRON jobs for DPD, alerts, ML patterns — correct pattern but lacks concurrency guards
5. `shared_state.py`: TTL cache (30s) + event-driven invalidation — process-local, breaks under multi-worker
6. `learning_engine.py`: behavioral pattern scoring per client — feeds RADAR collection intelligence
7. `event_bus.py`: append-only event emission — no retry or dead-letter queue currently

**Components needed for next milestone:**
1. `agent_prompts.py`: extracted system prompts from ai_chat.py
2. `context_builder.py`: financial context injection layer, split from ai_chat.py
3. `file_parser.py`: isolated tabular/PDF parsing from ai_chat.py
4. `portfolio_analytics.py`: DPD cohort analysis, bucket distribution, collection rate by model
5. `collection_intelligence.py`: PTP success prediction and next-best-action using learning_patterns
6. Infrastructure layer: Docker Compose + Nginx replacing render.yaml

### Critical Pitfalls

1. **Alegra idempotency gaps create duplicate financial records** — Wrap duplicate check and insert in MongoDB transactions; implement deterministic idempotency key (sha256 of entity_type + entity_id + amount + date) stored before every Alegra write; set APScheduler `max_instances=1` per job. Must be addressed before any mass-sync operation.

2. **Webhook event loss with no dead-letter queue** — Add `roddos_events_dlq` collection; APScheduler job to retry `processed=False` events older than 5 minutes with exponential backoff; Telegram alert when DLQ depth exceeds 5. Current volume (10 loanbooks) hides this problem but it becomes critical at 50+.

3. **Proveedor extraction failure silently degrades classification accuracy** — Add `extraction_succeeded: bool` flag to `ClasificacionResult`; log every fallback at WARNING; implement learning loop where operator confirmations of pending transactions populate `clasificacion_aprendida` collection; add parameterized tests for top 50 production description patterns. Must be resolved before building any auto-causation pipeline.

4. **In-memory cache breaks with multi-worker deployment** — Enforce single-worker constraint in render.yaml and docker-compose.yml, or add Redis-backed cache before any multi-process deployment. Critical to verify before Phase 3 self-hosted rollout.

5. **Loanbook state machine has no concurrency guard** — Use MongoDB `find_one_and_update` with current-state filter; add version counter for optimistic locking; test 5x5 concurrent transition matrix. Must be hardened before RADAR agent automates loanbook state changes.

## Implications for Roadmap

Based on combined research, the phase structure is already established by the three active milestones. The research confirms the ordering and surfaces the specific sequencing within each phase.

### Phase 1: Complete Financial System (Accounting Automation)

**Rationale:** Everything downstream — portfolio intelligence, digital sovereignty, automated collection — depends on correct accounting data. The bank reconciliation proveedor bug and classification accuracy gaps mean the foundation is currently unreliable. This must be stabilized before adding intelligence on top. Smoke test 20/20 is the explicit exit criterion that proves the foundation is solid.

**Delivers:** Validated accounting classification pipeline with 8.5/10 Contador accuracy, smoke test 20/20 passing against real Alegra IDs, bank extract auto-reconciliation at 90%+ match rate, expense causation via Telegram operational end-to-end.

**Addresses from FEATURES.md:** Bank extract reconciliation, accounting entries with correct chart-of-accounts mapping, cuota recalculation validation, expense causation from Telegram photo.

**Avoids from PITFALLS.md:** Pitfall 1 (Alegra idempotency), Pitfall 3 (silent classification degradation), Pitfall 8 (amount-blind confidence threshold), Pitfall 9 (ai_chat.py monolith regression).

**Build order within phase:**
1. Fix proveedor extraction call (one-line bug — highest ROI in codebase)
2. Extract `file_parser.py` and `context_builder.py` from ai_chat.py
3. Implement idempotency keys for all Alegra writes
4. Implement dead-letter queue for webhook event loss
5. Run smoke test 20/20 against real Alegra IDs
6. Risk-weighted confidence thresholds (90% for transactions above $1M COP)

### Phase 2: Portfolio Intelligence (RADAR + Loanbook Agent)

**Rationale:** Portfolio intelligence requires accurate loanbook state (which requires the Phase 1 loan FSM hardening) and accurate DPD data (which requires the proveedor fix to be in production producing clean data). The RADAR agent automating collection outreach requires loanbook concurrency guards and WhatsApp suppression windows to be in place first, or it risks compliance violations under Ley 1480.

**Delivers:** DPD dashboard with 5-bucket visualization, WhatsApp auto-response for saldo + proxima cuota, daily collection prioritization queue with next-best-action scoring, early warning semaforo based on behavioral patterns from learning_engine.

**Addresses from FEATURES.md:** Portfolio health dashboard, collection queue, WhatsApp auto-response, early warning system, collection workflow tracking (gestiones).

**Uses from STACK.md:** pandas (already installed) for portfolio_analytics.py, python-dateutil (already installed) for payment schedule projections.

**Implements from ARCHITECTURE.md:** `portfolio_analytics.py` and `collection_intelligence.py` as new components; RADAR queue upgrade using collection_intelligence recommendations.

**Avoids from PITFALLS.md:** Pitfall 5 (loanbook FSM concurrency), Pitfall 7 (WhatsApp automation without suppression window), Pitfall 4 (stale cache under load).

**Build order within phase:**
1. Loanbook FSM concurrency guard (optimistic locking — prerequisite for RADAR automation)
2. `portfolio_analytics.py`: DPD bucket aggregation, cohort KPIs
3. WhatsApp suppression window + acuerdo_pago FSM state
4. `collection_intelligence.py`: next-best-action scoring from learning_patterns
5. RADAR queue upgrade incorporating collection_intelligence
6. WhatsApp auto-response close-loop (intent → loanbook query → Mercately send)

### Phase 3: Digital Sovereignty (Self-Hosted Infrastructure)

**Rationale:** Infrastructure migration is safest when the application code is stable and well-tested. Containerizing a codebase with active bugs embeds those bugs into deployment artifacts. Phase 3 follows Phases 1-2 precisely because the smoke test suite from Phase 1 becomes the deployment validation suite in Phase 3. The DIAN integration unblock also belongs here — it requires a business decision (certificate acquisition) that operates on a separate timeline.

**Delivers:** Docker Compose deployment removing Render dependency, MongoDB Community 7.0 replacing Atlas (connection-string swap), Prometheus + Grafana observability, encrypted secrets management, immutable audit trail export, circuit breaker for Mercately outages.

**Addresses from FEATURES.md:** On-premise deployment option, local backup + restore, encrypted secrets management, audit trail export, API key rotation without downtime.

**Uses from STACK.md:** Docker 27 + Compose 2, Nginx 1.26 + Certbot 3, MongoDB Community 7.0, Prometheus 2.53 + Grafana 11 + prometheus-fastapi-instrumentator 0.6, GlitchTip 4 (MEDIUM confidence — verify stability), GitHub Actions + GHCR for CI/CD.

**Avoids from PITFALLS.md:** Pitfall 4 (in-memory cache breaks multi-worker — must enforce single-worker or add Redis), Pitfall 14 (JWT single key — rotate before moving off Render managed secrets), Pitfall 11 (webhook registration URL format changes with new domain).

**Build order within phase:**
1. Docker Compose + Nginx + Certbot for FastAPI + React (base containerization)
2. MongoDB Community 7.0 connection-string swap with mongodump backup cron
3. Prometheus + Grafana + prometheus-fastapi-instrumentator (observability)
4. GitHub Actions CI/CD pipeline (test → build → deploy via SSH)
5. Encrypted secrets management (replace .env)
6. Immutable audit trail export endpoint
7. DIAN live integration (blocked on certificate — activate when certificate acquired)

### Phase Ordering Rationale

- **Foundation before intelligence:** Portfolio intelligence accuracy is directly proportional to loanbook data accuracy. Building RADAR before fixing the state machine would produce a collection system that fires on incorrect DPD data.
- **Intelligence before sovereignty:** Containerizing broken code creates portable broken code. The smoke test suite from Phase 1 is the deployment validation gate for Phase 3.
- **Bug fixes before features:** The proveedor extraction bug, the missing cache invalidation call sites, and the loanbook concurrency gaps are not tech debt to schedule for later — they are correctness failures that corrupt real financial data today.
- **Human-in-loop before full automation:** The confidence-gated architecture (auto-post at 70%, human confirmation below) must be validated working correctly before any batch auto-causation runs. Confidence bypass is the highest-impact anti-pattern in this codebase.

### Research Flags

Phases likely needing deeper research during planning:

- **Phase 1 — DIAN integration:** Provider certificate procurement process (Alanube vs MATIAS) is a regulatory and business decision with a timeline outside engineering control. Needs a dedicated research spike when the decision to proceed is made.
- **Phase 2 — Collection compliance:** Automated WhatsApp collection messaging under Colombia Ley 1480 and SIC regulations. Research confidence is MEDIUM on specific regulatory requirements; validate with legal before RADAR sends autonomous production messages.
- **Phase 3 — GlitchTip stability:** Verify current release stability at glitchtip.com before committing. MEDIUM confidence — may need to fall back to self-hosted Sentry or a cloud error tracker.
- **Phase 3 — MinIO:** Verify current release at minio.io before committing to object storage. MEDIUM confidence. Only needed if moving away from MongoDB GridFS or Render ephemeral storage.

Phases with standard patterns (skip research-phase):

- **Phase 1 — Smoke test infrastructure:** pytest + pytest-asyncio + pytest-mock is canonical. No research needed.
- **Phase 1 — Proveedor bug fix:** Location is documented (bank_reconciliation.py line 357). One-line call addition, no research needed.
- **Phase 3 — Docker + Nginx + Certbot:** Battle-tested self-hosting pattern. No research needed.
- **Phase 3 — MongoDB Community 7.0:** Connection-string drop-in for Atlas. Motor driver works identically. No research needed.
- **Phase 3 — Prometheus + Grafana:** Industry-standard stack with prometheus-fastapi-instrumentator for zero-config FastAPI instrumentation. No research needed.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Existing stack is production-locked. Phase 1-2 additions are minimal, well-documented. Phase 3 infrastructure is canonical. Only MEDIUM items: GlitchTip stability, MinIO version pinning, scipy scope |
| Features | MEDIUM | Derived from codebase analysis + Colombian fintech domain knowledge. No live market research. Feature list accurately reflects what CONCERNS.md identifies as missing; specific regulatory requirements for WhatsApp collection need legal validation |
| Architecture | HIGH | Derived from direct analysis of 13 production source files. Component boundaries, data flows, and anti-patterns are documented from live code, not inference |
| Pitfalls | HIGH | Critical pitfalls (Pitfalls 1-5) are derived from direct code inspection with line-number references. Moderate pitfalls (6-10) are code-verified with MEDIUM confidence on regulatory specifics. Colombian regulatory context is domain knowledge only |

**Overall confidence:** HIGH

### Gaps to Address

- **Alegra rate limit specifics:** Documented in CONCERNS.md as approximately 450 req/min but not independently verified against current Alegra API documentation. Implement checkpoint persistence and semaphore limiting defensively regardless.
- **DIAN certificate timeline:** External business dependency with no engineering resolution path. Track as a milestone blocker for the DIAN integration sub-feature in Phase 1/3. All other Phase 1 features can complete without it.
- **scipy scope for Phase 2:** Only add if credit scoring model is explicitly in scope. If portfolio intelligence means dashboards and KPI trends, pandas alone is sufficient. Validate this during Phase 2 requirements definition.
- **WhatsApp regulatory compliance:** The specific SIC regulations governing automated collection messages need validation with legal counsel before RADAR sends autonomous outbound messages. The suppression window and opt-out mechanism in Pitfall 7 are minimum mitigations, not a compliance guarantee.
- **Self-hosted LLM quality bar:** Defer Ollama evaluation until Contador smoke test 20/20 establishes a measurable accuracy baseline. Without that baseline, there is no way to evaluate whether a self-hosted LLM meets the bar.

## Sources

### Primary (HIGH confidence)
- `.planning/codebase/ARCHITECTURE.md` (2026-03-24) — system structure, component boundaries, data flows
- `.planning/codebase/CONCERNS.md` (2026-03-24) — tech debt inventory, known bugs, identified gaps
- `.planning/codebase/INTEGRATIONS.md` (2026-03-24) — current integration capabilities and limitations
- `.planning/PROJECT.md` — validated requirements, out-of-scope constraints, active milestones
- Live source files: `event_bus.py`, `services/shared_state.py`, `services/accounting_engine.py`, `services/bank_reconciliation.py`, `services/cfo_agent.py`, `services/loanbook_scheduler.py`, `services/learning_engine.py`, `routers/chat.py`, `routers/radar.py`, `routers/alegra_webhooks.py`, `routers/loanbook.py`

### Secondary (MEDIUM confidence)
- Python ecosystem knowledge (training cutoff August 2025) — pytest, Docker, Nginx, Prometheus/Grafana stack selection
- FastAPI official documentation patterns for async testing — httpx ASGITransport approach
- MongoDB Community 7.0 LTS status — stable release since 2023
- Colombian fintech lending domain knowledge — WhatsApp collection workflows, DIAN electronic invoicing, PAR ratio conventions

### Tertiary (MEDIUM — verify before committing)
- GlitchTip 4.x stability — verify at glitchtip.com before Phase 3 implementation
- MinIO current release version — verify at minio.io before Phase 3 implementation
- Alegra API rate limit (450 req/min) — verify against current Alegra API documentation
- Colombia Ley 1480 / SIC automated collection regulations — validate with legal counsel before RADAR goes autonomous

---
*Research completed: 2026-03-24*
*Ready for roadmap: yes*
