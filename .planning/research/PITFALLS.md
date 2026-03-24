# Domain Pitfalls

**Domain:** Fintech lending operations automation — accounting (Alegra API), portfolio intelligence, WhatsApp collections, self-hosted infrastructure (Colombia)
**Researched:** 2026-03-24
**Confidence:** HIGH — derived primarily from live production codebase (BUILD 23) and existing CONCERNS.md audit, supplemented by domain knowledge of Colombian fintech/accounting integration patterns.

---

## Critical Pitfalls

Mistakes that cause rewrites, financial data corruption, or production outages.

---

### Pitfall 1: Alegra Idempotency Gaps Create Duplicate Financial Records

**What goes wrong:** When a network timeout or retry occurs during Alegra API calls (create invoice, create bill, register payment), the same financial entry lands twice in the accounting ledger. Because Alegra has no native idempotency key on most endpoints, the second call creates a new record with a new ID. SISMO's current 3-layer duplicate check (dian_facturas_procesadas, roddos_events, Alegra API query) is not atomic — a race condition between parallel requests or background task retries lets the same CUFE appear in multiple roddos_events records.

**Why it happens:** FastAPI BackgroundTasks retry on failure, APScheduler can fire overlapping jobs if a task takes longer than its interval, and Alegra API response latency varies (2-8 seconds). The window between "check if exists" and "insert if not" is exploitable under concurrent load.

**Consequences:** Double-counted revenue inflates P&L; duplicate bills overstate liabilities; duplicate cuota payments mark a loanbook as paid ahead of schedule; Alegra balance sheet diverges from MongoDB ground truth. Manual reconciliation required, which is exactly what this system is built to eliminate.

**Prevention:**
1. Wrap the 3-layer duplicate check + insert in a MongoDB session with `start_transaction()` / `commit_transaction()` so the check-and-insert is atomic.
2. Use a deterministic idempotency key for every Alegra write: `sha256(entity_type + entity_id + amount + date)`. Store in MongoDB before calling Alegra; if Alegra returns 409 or a duplicate, look up the previously stored Alegra ID and return it.
3. Add a 5-minute circuit breaker per CUFE: if the same CUFE appears in a second request within 5 minutes, reject it with a logged warning rather than a retry.
4. For APScheduler jobs, set `max_instances=1` per job to prevent overlapping executions.

**Detection:** Watch for `processed=False` events in roddos_events accumulating without manual resolution. Alegra bill/invoice counts diverging from MongoDB counts. Duplicate Alegra IDs appearing in loanbook cuota records.

**Phase:** Must be addressed in the accounting automation phase before any mass-sync operations are built.

---

### Pitfall 2: Webhook Event Loss With No Dead-Letter Queue

**What goes wrong:** The current Alegra webhook handler swallows exceptions — if `_nueva_factura()` or any handler throws, the event is stored in roddos_events with `processed=False` but there is no retry mechanism, no alert, and no way for the system to reprocess it later. Events pile up silently. The `processed=False` field exists as a flag but nothing reads it to retry.

**Why it happens:** The design correctly dispatches to background tasks (sub-5s response), but the background handler has no retry policy. Transient errors (Alegra 503, MongoDB timeout, LLM rate limit) permanently lose the event.

**Consequences:** Alegra changes (new factura, edited bill, deleted client) never propagate to MongoDB. Portfolio state drifts from Alegra state. Loanbooks may show incorrect balances. Since Alegra is the system of record, this creates an invisible split-brain condition.

**Prevention:**
1. Implement a dead-letter queue: after 3 failed attempts with exponential backoff (10s, 60s, 300s), move the event to a `roddos_events_dlq` collection with full error context.
2. Add an APScheduler job that scans `roddos_events` where `processed=False` and `timestamp < now - 5 minutes` and attempts reprocessing.
3. Add a Telegram alert (already integrated) when DLQ depth exceeds 5 unprocessed events.
4. Distinguish retriable errors (network, rate limits) from non-retriable (bad data, schema mismatch) so only the former are retried.

**Detection:** Monitor `db.roddos_events.count_documents({"processed": False})`. Any count above 0 for more than 10 minutes indicates an active failure. The existing `/api/webhooks/status` endpoint should expose this count.

**Phase:** Implement in parallel with any new Alegra integration expansion. The current volume (10 loanbooks) hides this problem; it becomes critical at 50+.

---

### Pitfall 3: Accounting Classification Silently Degrades When Proveedor Extraction Fails

**What goes wrong:** `extract_proveedor()` returns `descripcion[:30]` as a fallback when no pattern matches. This fallback value (e.g., "PAGO SERV DIGITALES GOOGLE") will never match any of the 30+ provider-based rules in the accounting engine, silently downgrading classification confidence from 75-95% to 25-60%. The transaction lands in `contabilidad_pendientes` requiring manual confirmation. There is no log entry distinguishing "proveedor extraction failed" from "legitimately ambiguous transaction."

**Why it happens:** The `extract_proveedor()` function covers 8 known Colombian banking description patterns but Colombian banks use inconsistent formats across time and account types. New merchant patterns emerge continuously (new PSE providers, new Nequi transaction formats). The function has no test coverage for ambiguous/edge-case descriptions.

**Consequences:** Over time, as new merchant patterns emerge, an increasing fraction of transactions accumulate in `contabilidad_pendientes`. The operator faces growing manual review load — the opposite of what the system promises. The failure is invisible: classification "works" but at low confidence.

**Prevention:**
1. Add a `extraction_succeeded: bool` flag to `ClasificacionResult` so callers can distinguish "classified correctly" from "classified with fallback."
2. Log every fallback case at WARNING level with the full original description. This creates a backlog of unmatched patterns to address.
3. Implement a learning loop: when operators manually confirm a `contabilidad_pendientes` transaction, record the `(description_pattern, proveedor, account_ids)` triple in a `clasificacion_aprendida` collection. The engine should consult this before falling through to the generic fallback.
4. Add parameterized tests for the top 50 actual transaction descriptions from the production extracto (one-time effort, high payoff).

**Detection:** Track `confianza` distribution in classified transactions. If more than 15% of monthly transactions are below 0.70 confidence, the extraction patterns need updating.

**Phase:** Must be addressed before building any auto-causation pipeline that bypasses human confirmation.

---

### Pitfall 4: In-Memory Cache Is Process-Local — Invisible on Multi-Worker Deployments

**What goes wrong:** `shared_state.py` uses a Python dict (`_cache`) as the TTL cache. This is single-process and lives in memory. On Render, if the app ever runs with more than one worker process (e.g., gunicorn with `--workers 2`), each process has its own cache. Worker A invalidates cache after a payment, but Worker B still serves stale data from its own cache. The operator sees inconsistent dashboards depending on which worker handles each request.

**Why it happens:** The TTL cache was implemented as the simplest correct solution for a single-process deployment. Render's free/starter tier typically runs single-process, masking this issue. But as load grows or if a production incident triggers a worker restart, inconsistency windows appear.

**Consequences:** CFO dashboard shows stale KPIs. Portfolio health metrics disagree between page refreshes. If two agents (Contador + CFO) run simultaneously on different workers, they operate on divergent state snapshots.

**Prevention:**
1. Before adding any new background workers or scaling the Render deployment, replace the in-memory dict with Redis-backed cache (Redis is already the natural next step when migrating to Celery for task queuing).
2. If staying single-process, enforce this with `gunicorn --workers 1 --worker-class uvicorn.workers.UvicornWorker` in render.yaml and document the constraint.
3. Implement event-driven invalidation via the event bus so all processes receive invalidation signals (requires Redis pub/sub or a shared store).

**Detection:** Run two concurrent browser sessions after a payment; if KPIs differ between sessions within the same 30-second window, the cache is split. Also check render.yaml for `--workers` configuration.

**Phase:** Critical to verify before the infrastructure sovereignty phase introduces self-hosted deployment (where multi-worker configs are common).

---

### Pitfall 5: Loanbook State Machine Has No Concurrency Guard

**What goes wrong:** The loanbook lifecycle (pendiente_entrega → activo → cancelado → liquidado) has no optimistic locking or mutex. If two simultaneous requests try to activate the same loanbook (e.g., operator double-clicks, or a scheduler job fires while operator is editing), both read `estado=pendiente_entrega`, both pass the state validation, and both execute the transition. The second write overwrites the first. Cuota dates may be calculated twice with different timestamps.

**Why it happens:** FastAPI's async handlers do not serialize access to MongoDB documents by default. The current `emit_state_change` function reads → validates → writes in three separate operations with no document lock.

**Consequences:** For a live $94M COP portfolio, a duplicated activation creates two sets of cuotas, double-counts cuota inicial payment, and potentially creates two Alegra invoices for the same motorcycle sale. This is a financial integrity failure.

**Prevention:**
1. Use MongoDB's `find_one_and_update` with a filter on the current state: `{id: loan_id, estado: "pendiente_entrega"}`. If the update returns None, the transition was already performed by another request. Return a 409 Conflict.
2. Add a `version` counter to each loanbook document and implement optimistic locking: the update filter includes `{version: read_version}` and increments it atomically.
3. Add a test matrix covering concurrent state transitions: 5 start states × 5 actions = 25 combinations, with at least the concurrent-same-transition case covered.

**Detection:** Loanbooks with duplicate cuota numbers, or with two cuotas marked `numero=0`. Alegra showing two invoices with the same VIN/client.

**Phase:** Must be hardened before any collection automation that triggers state changes programmatically (RADAR agent automating loanbook updates).

---

## Moderate Pitfalls

### Pitfall 6: Alegra API Rate Limit Causes Cascading Delays During Mass Operations

**What goes wrong:** Alegra enforces a rate limit (documented at approximately 450 requests/minute but in practice lower for some account tiers). During bulk bank reconciliation of a monthly extracto with 200+ transactions, the system fires one Alegra journal create per transaction sequentially. With Alegra averaging 2-3 seconds per call, a 200-transaction upload takes 7-10 minutes. If a 429 is returned mid-batch, the retry backoff stalls the entire upload.

**Why it happens:** The current reconciliation pipeline processes transactions in a `for` loop, creating one Alegra journal per iteration. There is no request batching, no adaptive rate limiting, and no progress persistence — if the batch fails at transaction 150, the operator must restart from scratch.

**Prevention:**
1. Implement checkpoint persistence: save successfully processed transaction indices to MongoDB so a restart continues from where it left off.
2. Use `asyncio.gather()` with a semaphore (max 5 concurrent) for parallel journal creation instead of sequential processing.
3. Monitor `X-RateLimit-Remaining` response headers; add a circuit breaker that pauses batch processing when below 20% of limit.
4. Consider batching journals into grouped entries by date to reduce total API call count.

**Detection:** User-facing batch upload completing in >5 minutes. Logs showing `429 Too Many Requests` from Alegra. Background task queue backing up in APScheduler.

**Phase:** Must be addressed before building any month-end auto-closing or bulk backfill features.

---

### Pitfall 7: WhatsApp Collection Automation Triggers Without Customer Consent Context

**What goes wrong:** The RADAR agent triggers WhatsApp messages based on DPD buckets and loanbook state. If a customer has already spoken with the operator via a different channel (phone call, in-person), or has an active payment arrangement, the automated message arrives as contradictory or harassing. Colombia's consumer protection law (Ley 1480) and SIC regulations impose strict requirements on automated collection contacts.

**Why it happens:** The collection trigger logic reads `dpd_bucket` and `estado` but has no awareness of manual operator notes, recent human interactions, or active payment arrangements (acuerdos de pago). The event bus records events but there is no "suppression window" after a human interaction.

**Prevention:**
1. Implement a `contacto_reciente` flag on each loanbook with a timestamp: set it when any manual contact is logged, reset it after 72 hours. RADAR checks this before sending.
2. Create an `acuerdo_pago` state on the loanbook FSM: while in this state, automated DPD messages are suppressed.
3. Add a WhatsApp opt-out mechanism: if a customer replies "STOP" or equivalent, mark a `whatsapp_optout=True` field and never send automated messages.
4. Log every automated message sent with: recipient, template used, timestamp, loanbook state at send time. This creates an audit trail for regulatory compliance.

**Detection:** Customer complaints about repeated messages after arranging payment. Operator reports of contradictory messages arriving during active negotiations.

**Phase:** Must be implemented before RADAR sends any production collection messages autonomously.

---

### Pitfall 8: LLM Classification Confidence Is Not Calibrated to Accounting Risk

**What goes wrong:** The accounting engine uses LLM-assisted classification for ambiguous transactions. The system currently treats a 70% confidence threshold as the line between auto-causation and manual review. But a 70% confident misclassification of a $5M COP transaction (e.g., a loan disbursement classified as an operating expense) causes a larger accounting error than a 100% certain classification of a $50,000 COP coffee purchase.

**Why it happens:** The confidence threshold is uniform regardless of transaction amount. The LLM outputs a single confidence score without considering financial materiality.

**Prevention:**
1. Implement risk-weighted thresholds: transactions above $1M COP require ≥90% confidence or human confirmation regardless of rule match.
2. Add a mandatory human-in-the-loop confirmation for any transaction that would affect: (a) capital accounts, (b) loan disbursements/receipts, (c) transactions with no prior transaction history for that proveedor.
3. The `requiere_confirmacion` flag should incorporate amount tiers, not just classification confidence.

**Detection:** Review auto-causados transactions monthly for the top 10 by amount. If any large transactions were auto-classified incorrectly, the threshold logic needs revision.

**Phase:** Before any auto-causation pipeline is promoted to production.

---

### Pitfall 9: ai_chat.py Monolith Is a Single Point of Failure for All Agent Intelligence

**What goes wrong:** At 5,217 lines, `ai_chat.py` handles context building, prompt engineering, file processing, LLM calls, and complex extraction logic for all four agents (Contador, CFO, RADAR, Loanbook). A syntax error, import failure, or unhandled exception anywhere in this file takes down all agent functionality simultaneously. The monolith also makes it impossible to test individual agent flows in isolation.

**Why it happens:** Iterative growth — each new agent feature was added to the same file for speed. The file now has too many responsibilities to safely modify.

**Consequences for new development:** Any new feature that touches agent intelligence requires reading and understanding 5K+ lines. Probability of regression on unrelated agents is high. Performance optimizations (prompt caching, streaming) cannot be applied selectively per agent.

**Prevention:**
1. Before adding any new agent capability, extract the relevant sections from `ai_chat.py` into focused modules: `agent_prompts.py`, `file_parser.py`, `context_builder.py`, `action_executor.py`.
2. Establish a size limit: no single file in the `services/` layer should exceed 500 lines. Enforce this in code review.
3. Write characterization tests for each agent's current behavior before refactoring, so regressions are caught immediately.

**Detection:** PR diffs that touch `ai_chat.py` for more than one agent's feature. Any test failure that takes down the entire agent test suite due to a single import error.

**Phase:** Refactoring should precede any significant new agent capability addition to reduce blast radius.

---

### Pitfall 10: DIAN Stub in Production Blocks Tax Compliance Silently

**What goes wrong:** `dian_service.py` line 229 returns an empty list in production mode with a TODO comment. DIAN electronic invoice receivables are never causadas. This means purchase invoices from suppliers (gastos deducibles) are not reflected in Alegra, understating liabilities and overstating net income. The system appears functional but is tax-non-compliant.

**Why it happens:** DIAN integration requires a software provider certificate (Alanube, MATIAS, etc.) that was not available at build time. The stub was the correct temporary decision, but there is no runtime warning or operator alert indicating that this critical feature is disabled.

**Prevention:**
1. Add a startup health check that logs a prominently visible WARNING if `DIAN_PRODUCTION_MODE=true` but the DIAN service is still in simulation mode.
2. Add a `/api/diagnostico` endpoint flag: `"dian_activo": false` with a human-readable explanation visible in the dashboard.
3. Document the specific provider (Alanube is the recommended path for companies of RODDOS's size in Colombia) and the certificate procurement process in the ops runbook.

**Detection:** Alegra balance sheet shows zero gastos deducibles from supplier invoices. Monthly P&L does not reflect purchase invoices. Operator manually entering DIAN invoices into Alegra.

**Phase:** Must be activated before any automated month-end close feature is built, or the closed books will be incomplete.

---

## Minor Pitfalls

### Pitfall 11: Webhook Programmatic Registration Fails Silently Due to URL Format

**What goes wrong:** `POST /api/webhooks/setup` registers Alegra webhooks programmatically but returns success even when Alegra does not accept the registration. The known issue is that Alegra's API may reject HTTPS URLs in the registration body. The workaround (manual UI registration) is not documented for onboarding new operators.

**Prevention:** Add a verification step after registration: immediately call `GET /api/webhooks/status` and confirm the newly registered webhooks appear in the Alegra subscription list. If they do not, return a 500 with explicit manual registration instructions.

**Detection:** Alegra events not arriving at `/api/webhooks/alegra` after programmatic setup. Check the `/api/webhooks/status` response for subscription count.

**Phase:** Minor — workaround exists. Fix during infrastructure phase when self-hosting may change the APP_URL format.

---

### Pitfall 12: Frontend 3-Second Polling Burns API Quota and Degrades Mobile UX

**What goes wrong:** AgentChatPage polls `/api/chat/tarea` every 3 seconds unconditionally — including when the tab is in the background or no task is running. With 5 concurrent users, this generates 100 requests/minute to the backend before any real work happens.

**Prevention:** Implement Page Visibility API (`document.addEventListener('visibilitychange')`) to pause polling when the tab is hidden. Add exponential backoff from 3s → 30s when the last 10 polls returned no state change.

**Detection:** Backend access logs showing polling requests accounting for >30% of total request volume. High CPU on Render from idle connections.

**Phase:** Low priority on small team (2-5 users), but address before adding multiple concurrent agent sessions.

---

### Pitfall 13: Bare Except in Inventory Hides Data Corruption

**What goes wrong:** `inventory.py` line 532 uses `except: return 0.0` with no logging. Numeric calculation failures (division by zero, None values) are swallowed. The inventory value displayed on the dashboard may be silently wrong.

**Prevention:** Replace with `except (TypeError, ValueError, ZeroDivisionError) as e: logger.error(...)` and return `None` so callers can distinguish "calculated zero" from "calculation failed."

**Detection:** Inventory totals that are exactly 0.0 when there are known motos in stock. No error logs corresponding to inventory queries.

**Phase:** Quick fix — can be addressed in any upcoming build as a housekeeping item.

---

### Pitfall 14: JWT Secret Never Rotated — Long-Lived Tokens Are a Liability

**What goes wrong:** A single JWT_SECRET signs all tokens with 7-day expiry. If the secret is exposed (leaked `.env`, compromised Render environment variable), an attacker can forge tokens for up to 7 days with no revocation mechanism.

**Prevention:** Implement key rotation with an active key + one backup key. Validate tokens against both; signed with active only. Rotate monthly. Short-lived tokens (1 hour) with a refresh token pattern eliminate the 7-day exposure window.

**Detection:** Unauthorized API calls from unexpected IP ranges. No current detection mechanism exists — this is a gap.

**Phase:** Address during the infrastructure sovereignty phase when self-hosting moves security responsibility in-house.

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Accounting automation (auto-causation) | Duplicate Alegra entries from retries (Pitfall 1) | Implement idempotency keys before first auto-causation |
| Accounting automation (auto-causation) | Silent classification degradation (Pitfall 3) | Add learning loop + test coverage on proveedor extraction |
| Accounting automation (auto-causation) | Amount-blind confidence threshold (Pitfall 8) | Risk-weighted thresholds before going live |
| Portfolio intelligence / analytics | Stale cache on multi-process deployment (Pitfall 4) | Verify Render single-worker constraint or add Redis |
| Portfolio intelligence / analytics | N+1 queries at 500+ loanbooks (see CONCERNS.md) | Add denormalized `portfolio_health` summary collection |
| WhatsApp collections (RADAR) | Automated messages ignoring manual contacts (Pitfall 7) | Suppression window + acuerdo_pago state before first autonomous send |
| WhatsApp collections (RADAR) | Loanbook concurrent state corruption (Pitfall 5) | Optimistic locking on FSM transitions |
| WhatsApp collections (RADAR) | Webhook event loss (Pitfall 2) | Dead-letter queue before RADAR depends on webhook state |
| Self-hosted infrastructure | In-memory cache breaks with multi-worker (Pitfall 4) | Redis cache required for any multi-process setup |
| Self-hosted infrastructure | JWT single key exposure (Pitfall 14) | Key rotation before moving off Render's managed secrets |
| Any new agent capability | ai_chat.py monolith regression risk (Pitfall 9) | Characterization tests + module extraction first |
| Month-end auto-close | DIAN stub means incomplete books (Pitfall 10) | Activate DIAN integration before building auto-close |
| Bulk bank reconciliation | Alegra rate limit cascading failure (Pitfall 6) | Checkpoint persistence + semaphore-limited concurrency |

---

## Sources

- Live codebase: `backend/services/accounting_engine.py`, `backend/services/bank_reconciliation.py`, `backend/routers/alegra_webhooks.py`, `backend/routers/loanbook.py`, `backend/services/shared_state.py`, `backend/post_action_sync.py` — HIGH confidence (direct code inspection)
- `.planning/codebase/CONCERNS.md` (2026-03-24 audit) — HIGH confidence (first-party tech debt audit)
- `.planning/PROJECT.md` (current project context) — HIGH confidence (first-party project spec)
- Colombian regulatory context (Ley 1480, SIC collection regulations, DIAN electronic invoicing mandate) — MEDIUM confidence (domain knowledge, not verified against current regulations in this session)
- Alegra API rate limit specifics — MEDIUM confidence (documented in CONCERNS.md as "450 req/min", not independently verified against current Alegra documentation in this session)
