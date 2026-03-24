# Codebase Concerns

**Analysis Date:** 2026-03-24

## Tech Debt

**Monolithic AI Chat Module:**
- Issue: `backend/ai_chat.py` is 5,217 lines, handling context building, prompt engineering, file processing, and complex extraction logic
- Files: `backend/ai_chat.py`
- Impact: Single point of failure for agent intelligence; changes to prompt logic affect all agent flows; difficult to test individual components; token usage optimization limited
- Fix approach: Break into smaller modules (`agent_prompts.py`, `file_parser.py`, `context_builder.py`); extract reusable patterns; reduce from 5K+ lines to <2K by delegating to services

**Provider Data Extraction Broken in Classification:**
- Issue: Bank reconciliation classifier always passes empty string for `proveedor` parameter, making 30+ provider-based rules inactive
- Files: `backend/services/bank_reconciliation.py` (line 357), `backend/services/accounting_engine.py` (extract_proveedor function only partially used)
- Impact: Socio expenses, merchant-specific rules (D1, Fontanar, Uber, Rappi) classified with low confidence (25-60%) instead of high (75-95%); expenses stuck in PENDIENTE status requiring manual confirmation; classification accuracy ~40% of potential
- Fix approach: `extract_proveedor()` in accounting_engine.py (lines 23-84) already exists but not called from bank_reconciliation.py; update line 357 to extract and pass actual provider value instead of empty string

**Untyped Payload Handling in Agent Chat:**
- Issue: Form payload structure varies by action type (journal entries, bill, invoice, tercero) but no type safety
- Files: `frontend/src/pages/AgentChatPage.tsx` (lines 43, 1016)
- Impact: Runtime errors when payload shape mismatches; generic key-value updater operates on any field without validation; form state mutations hard to trace
- Fix approach: Define discriminated union types for each action payload (`JournalPayload`, `BillPayload`, `InvoicePayload`, `TerceroPayload`); use type guards in form updater

**Bare Except in Inventory:**
- Issue: Bare `except: return 0.0` catches all exceptions without logging or recovery
- Files: `backend/routers/inventory.py` (line 532)
- Impact: Silent failures in numeric operations; debugging impossible; data corruption without visibility
- Fix approach: Replace with specific exception handling; log error with context; return None and handle upstream; validate numeric inputs earlier

**DIAN Integration Stubbed:**
- Issue: DIAN production mode stubbed with TODO comment; always returns empty list even in production environment
- Files: `backend/services/dian_service.py` (line 229)
- Impact: DIAN invoice integration non-functional for production; tax compliance at risk; automatic invoice causation blocked
- Fix approach: Implement SOAP or REST client for actual DIAN when provider/certificate available; current simulation mode works for development; document configuration for production switchover

## Known Bugs

**Missing Post-Action Cache Invalidation in Payments:**
- Symptoms: Payment registered in Alegra but CFO dashboard shows stale data; cache TTL=30s causes brief inconsistency; causados count may not update immediately
- Files: `backend/routers/loanbook.py` (around line 490)
- Trigger: User registers a payment via POST /api/loanbook/{id}/pagar then immediately views CFO dashboard
- Workaround: Refresh page or wait 30 seconds
- Root cause: Cache invalidation missing after payment sync; `post_action_sync()` called but CFO cache not explicitly cleared
- Fix: Add explicit `await invalidar_cache_cfo()` call after payment registration completes

**CSV File Upload Rejects Excel Files Without Help:**
- Symptoms: User uploads .xlsx file expecting it to load; form shows rejection but no guidance
- Files: `backend/routers/gastos.py`, `frontend/src/pages/AgentChatPage.tsx`
- Trigger: POST /api/gastos/cargar with multipart/form-data MIME type application/vnd.openxmlformats-officedocument.spreadsheetml.sheet
- Workaround: Convert .xlsx to .csv manually
- Root cause: System design enforces CSV-only for mass upload (documented in PRD as ESTANDARIZACIÓN CSV) but error message lacks conversion guidance
- Fix: Enhanced error response with "Please convert .xlsx to .csv using: File→Save As→CSV" instruction

**Webhook Alegra Configuration Mismatch:**
- Symptoms: Manual webhook registration in Alegra UI works; programmatic registration via POST /api/webhooks/setup returns success but Alegra doesn't receive events
- Files: `backend/routers/alegra_webhooks.py` (line 26-31)
- Trigger: POST /api/webhooks/setup with APP_URL containing "https://"
- Workaround: Register manually in Alegra UI instead of using setup endpoint
- Root cause: Alegra API documented to reject HTTPS URLs in webhook registration requests (unconfirmed limitation, may be environment-specific)
- Fix: Test with both HTTP and HTTPS; add fallback to manual registration instructions if programmatic fails

**Duplicate Detection Uses Multiple Collections Without Coordination:**
- Symptoms: Same CUFE (Factura electrónica) appears in multiple roddos_events records; causadas event emitted multiple times
- Files: `backend/services/dian_service.py` (lines 125-133)
- Trigger: Network retry during factura.causada event insertion; background task retries duplicate check
- Workaround: Manual deduplication cleanup query
- Root cause: 3-layer anti-duplicate check (dian_facturas_procesadas, roddos_events, Alegra API) not atomic; race condition if parallel requests arrive
- Fix: Use MongoDB transactions to atomically check all 3 layers + insert processed record; add circuit breaker for duplicate CUFEs within 5-min window

## Security Considerations

**Webhook Secret Stored in Environment Variable:**
- Risk: ALEGRA_WEBHOOK_SECRET hardcoded in code comments and config; if .env leaked, all webhook signatures become forgeable
- Files: `backend/routers/alegra_webhooks.py` (line 30)
- Current mitigation: Environment variable loaded at startup; secret not logged; header validation on every webhook
- Recommendations: (1) Rotate secret quarterly; (2) Store in AWS Secrets Manager or HashiCorp Vault instead of .env; (3) Add rate limiting to /webhooks/alegra endpoint; (4) Log failed authentications to audit trail

**JWT Secret Never Rotated:**
- Risk: JWT_SECRET from .env is single signing key for 7-day tokens; if compromised, attacker can forge tokens for a week
- Files: `backend/auth.py`, `backend/server.py`
- Current mitigation: 7-day expiry is relatively short; 401 anti-storm guard in AuthContext
- Recommendations: (1) Implement key rotation (active + backup key); (2) Short-lived tokens (1 hour) with refresh token pattern; (3) Audit token validation on every protected endpoint; (4) Invalidate tokens on password change

**API Keys in Alegra Request Auth:**
- Risk: ALEGRA_EMAIL + ALEGRA_TOKEN used for HTTP Basic Auth in all Alegra requests; if proxied through insecure network, credentials visible
- Files: Multiple files use `auth=(ALEGRA_EMAIL, ALEGRA_TOKEN)` in httpx calls
- Current mitigation: HTTPS enforced in production
- Recommendations: (1) Use OAuth 2.0 if Alegra supports it; (2) Encrypt credentials at rest in database; (3) Audit all Alegra API calls for personally identifiable info leakage; (4) Implement request signing instead of Basic Auth

**Form Payload Mutation Without Validation:**
- Risk: Generic key-value updater in AgentChatPage accepts any form field name without schema validation; malicious payload could inject arbitrary database fields
- Files: `frontend/src/pages/AgentChatPage.tsx` (line 1016)
- Current mitigation: Backend validates against models; frontend validation missing
- Recommendations: (1) Define strict payload schema per action type; (2) Use TypeScript discriminated unions; (3) Sanitize field names on backend (whitelist only expected fields); (4) Log rejected payloads for security monitoring

## Performance Bottlenecks

**30-Second Cache TTL Causes Dashboard Staleness:**
- Problem: CFO semaphore, P&L, and portfolio health cached with fixed 30-second TTL; user registers payment and sees 0-30 second delay before update
- Files: `backend/services/shared_state.py` (line 21)
- Cause: Simple time-based eviction with monotonic timestamp; no event-driven cache invalidation
- Improvement path: (1) Implement event-driven cache invalidation (clear immediately on pago.cuota.registrado event); (2) Keep TTL as fallback for safety; (3) Add cache hit/miss metrics to logging

**Banco Reconciliation Processes All Transactions Sequentially:**
- Problem: Background task `sync_facturas_dian()` iterates through all facturas and checks duplicates 3 layers; scales O(n) with transaction count
- Files: `backend/services/dian_service.py` (lines 237-275)
- Cause: No parallelization; triple-checks each transaction (dian_facturas_procesadas, roddos_events, Alegra API query)
- Improvement path: (1) Batch duplicate checks with MongoDB `$in` operator instead of loop; (2) Cache Alegra bill list for 5 minutes instead of querying per transaction; (3) Use asyncio.gather() for parallel Alegra bill creations; (4) Expected speedup: 5-10x for large bank files (100+ transactions)

**Accounting Engine Classification Runs Full Rule Evaluation:**
- Problem: `clasificar_movimiento()` evaluates all 50+ rules per transaction even after match; scales O(n*m) where n=transactions, m=rules
- Files: `backend/services/accounting_engine.py` (lines 400+)
- Cause: No early exit after high-confidence match; regex patterns re-compiled per call
- Improvement path: (1) Order rules by priority (socio > tech > interest > gmf > generic); (2) Early exit on >90% confidence; (3) Pre-compile regex patterns as module constants; (4) Cache proveedor extraction results; (5) Expected speedup: 3-4x for 100+ transactions per file

**Frontend Polling Requests Every 3 Seconds Unconditionally:**
- Problem: AgentChatPage polls /api/chat/tarea every 3 seconds regardless of whether user is viewing page; burns API quota and battery on mobile
- Files: `frontend/src/pages/AgentChatPage.tsx` (polling logic)
- Cause: No visibility detection; no exponential backoff when no active task
- Improvement path: (1) Use Page Visibility API to pause polling when tab inactive; (2) Exponential backoff from 3s → 30s when task hasn't changed for >5 minutes; (3) Use WebSocket or Server-Sent Events for push instead of poll; (4) Expected reduction: 90% fewer requests in inactive tabs

## Fragile Areas

**Async/Await Context Loss in Chat Processing:**
- Files: `backend/ai_chat.py` (process_chat function and async context)
- Why fragile: Large async function with database operations, file uploads, LLM calls, and side effects; context can be lost if middleware catches exceptions incorrectly
- Safe modification: (1) Break into smaller async functions with single responsibility; (2) Wrap each database operation in try/except with typed errors; (3) Validate all inputs at function entry; (4) Use asyncio context managers for resource cleanup
- Test coverage: No unit tests for individual context-building steps; integration tests only test happy path

**State Machine for Loanbook Lifecycle:**
- Files: `backend/routers/loanbook.py` (line 436-490 for register_pago), `backend/services/shared_state.py` (emit_state_change)
- Why fragile: Estado transitions (pendiente_entrega → activo → cancelado) not validated against current state; can register payment for not-yet-active loanbook
- Safe modification: (1) Define explicit FSM with allowed transitions in shared_state.py; (2) Validate target_state is valid from current_state before executing; (3) Block invalid transitions with HTTPException; (4) Test matrix: 10 start states × 5 actions = 50 combinations
- Test coverage: Basic smoke tests only; no FSM edge cases tested

**Loanbook Cuota Date Calculation Dependent on Delivery Date:**
- Files: `backend/routers/loanbook.py` (register_entrega function), `backend/services/loanbook_scheduler.py`
- Why fragile: Cuota dates calculated when entrega registered, assuming delivery is immediate; if delivery postponed after registro, cuota dates are stale
- Safe modification: (1) Add fecha_entrega_real field; (2) Allow cuota regeneration with PATCH /api/loanbook/{id}/regenerar-cuotas; (3) Emit evento loanbook.cuota.regenerado; (4) Validate all future cuotas exist before marking activo
- Test coverage: Test with immediate delivery; missing tests for delivery date changes

**Cache Invalidation Spread Across Multiple Modules:**
- Files: `backend/routers/loanbook.py`, `backend/routers/gastos.py`, `backend/routers/cfo.py`, `backend/services/shared_state.py`
- Why fragile: invalidar_cache_cfo() called from 10+ locations; easy to forget after adding new operation; cache inconsistency if one path misses invalidation
- Safe modification: (1) Create @invalidates_cfo_cache decorator for functions that modify state; (2) Centralize all cache keys in enum; (3) Add logging every time cache is invalidated; (4) Test: verify cache timestamp changes after each write operation
- Test coverage: No cache invalidation tests; cache bugs only caught by manual testing

**Webhook Event Handlers Swallow Exceptions Silently:**
- Files: `backend/routers/alegra_webhooks.py` (lines 78-83)
- Why fragile: Handler exceptions logged but event still marked processed=False; no retry mechanism; duplicates silently marked processed without side effects
- Safe modification: (1) Distinguish between retriable errors (network) and non-retriable (bad data); (2) Implement exponential backoff for retriable; (3) Dead-letter queue for non-retriable; (4) Alert operator if processed=False events accumulate
- Test coverage: No error simulation tests for webhook handlers

## Scaling Limits

**MongoDB Indexes on Roddos_events Collection:**
- Current capacity: roddos_events append-only collection growing ~500 docs/week; no pagination or archival strategy
- Limit: Query performance degrades after 50,000 documents; index on (event_type, timestamp) becomes ineffective
- Scaling path: (1) Implement document TTL index (30 days auto-delete); (2) Archive old events to separate collection monthly; (3) Denormalize hot queries to summary collections; (4) Expected timeline: Issue visible at ~3 months of production use

**CFO Dashboard Aggregation Queries:**
- Current capacity: Semaphore + P&L queries run in <200ms with <100 loanbooks active
- Limit: At 500+ loanbooks (18 months growth), aggregation pipeline will timeout; N+1 queries still present in CFO._get_portfolio_health
- Scaling path: (1) Implement document-level denormalization for portfolio_health; (2) Run aggregation as scheduled job (every 30s), cache result; (3) Use MongoDB Atlas analytics for query profiling; (4) Add indexes on (estado, dpd_bucket, created_at)

**Async Task Queue (BackgroundTasks):**
- Current capacity: FastAPI BackgroundTasks executor (thread pool) handles ~10 concurrent background operations
- Limit: If scheduler spawns >20 async tasks per minute, queue backs up; tasks risk timeout before execution
- Scaling path: (1) Move to Celery + Redis for distributed task queue; (2) Add task priorities; (3) Implement SLA monitoring (task age); (4) Estimated need: When concurrent agents reach 5+

**File Upload Processing (CSV/Excel):**
- Current capacity: `_tabular_to_text()` reads entire file into memory (base64 decode + openpyxl load)
- Limit: Files >50MB will cause OOM on shared Render instance; current limit not enforced in frontend/backend
- Scaling path: (1) Add 10MB max file size validation; (2) Stream large files through chunked processing; (3) Use temporary storage (S3) for intermediate processing; (4) Clean up temp files on error

**Alegra API Rate Limit (450 req/min):**
- Current capacity: ~50-100 requests per day across all operations (invoices, bills, journals, items, payments)
- Limit: At 20+ users executing simultaneously, rate limit hit; 429 responses spike; retry backoff creates cascading delays
- Scaling path: (1) Implement request batching (bulk invoice creation); (2) Queue requests with priority; (3) Monitor rate limit headers; (4) Add circuit breaker (fail gracefully at 80% of limit); (5) Negotiate higher rate limit with Alegra

## Dependencies at Risk

**Openpyxl Dynamic Import:**
- Risk: `import openpyxl` happens inside `_tabular_to_text()` function (ai_chat.py line 61); if package missing, entire chat fails when Excel uploaded
- Impact: Breaks agent chat if requirements.txt not properly installed; production deployment could fail silently
- Migration plan: (1) Move to top-level import; (2) Add explicit version constraint (==3.1.2 already in requirements); (3) Add startup validation in server.py: attempt to import all optional dependencies; fail fast with helpful error

**Anthropic SDK Version Pinning:**
- Risk: Version not pinned in requirements.txt; major version updates could break prompt formatting or token counting
- Impact: Uncontrolled API behavior changes during deployment
- Migration plan: (1) Pin version to specific release (e.g., `anthropic==0.21.0`); (2) Add test for prompt structure on version upgrade; (3) Maintain changelog of API compatibility per version

**Mercately API Stability:**
- Risk: WhatsApp integration depends on Mercately API; no fallback for outages
- Impact: Automated collection messages fail silently; customers don't receive payment reminders
- Migration plan: (1) Add circuit breaker pattern (fail gracefully after 3 consecutive 5xx); (2) Queue failed messages for manual retry; (3) Implement SMS fallback for critical alerts; (4) Add service health check endpoint

## Missing Critical Features

**DIAN Electronic Invoice Integration Disabled:**
- Problem: Tax compliance requires DIAN invoice receivables; currently stubbed in simulation mode only
- Blocks: Automatic causation of purchase invoices from DIAN; cannot reconcile tax credits until invoices manually entered
- Resolution: Implement provider integration (Alanube, MATIAS, or direct SOAP); configure certificate; test with real DIAN in habilitación environment; migrate to producción

**Payment Verification Webhook from Banco/Nequi:**
- Problem: Payment registration requires manual entry; no automatic detection when customer transfers money
- Blocks: Collection workflow 100% manual; cash application requires human verification
- Resolution: Integrate with bank webhook (Nequi, Bancolombia, BBVA) to detect transfers automatically; match to loanbook by reference; auto-register payment

**Multi-Currency Support for International Socios:**
- Problem: All amounts hardcoded to COP; if RODDOS expands to foreign markets, currency conversion missing
- Blocks: International operations; FX risk exposure invisible
- Resolution: Add currency field to loanbook + transactions; use real-time FX rates (OpenExchangeRates API); implement Alegra multi-currency account mapping

## Test Coverage Gaps

**Webhook Event Handlers Not Unit Tested:**
- What's not tested: Individual alegra_webhooks.py handlers (_nueva_factura, _editar_factura, etc.) executed in isolation
- Files: `backend/routers/alegra_webhooks.py` (lines 97-180+)
- Risk: Handler bugs only caught when full webhook flow runs; no regression detection; silent failures possible if exception handling changes
- Priority: High — webhooks are event backbone of system; one broken handler blocks entire feature

**Classification Engine Proveedor Extraction Edge Cases:**
- What's not tested: Proveedor extraction with ambiguous descriptions ("PAGO PSE COMERC" followed by garbage text, misspelled merchant names, special characters)
- Files: `backend/services/accounting_engine.py` (extract_proveedor function, lines 23-84)
- Risk: Extraction succeeds with wrong value (e.g., extracts "COMERC" instead of actual merchant); rule never matches
- Priority: High — affects classification accuracy; 30+ rules depend on correct proveedor extraction

**Cache Invalidation Verification:**
- What's not tested: That cache keys are actually cleared after operations; that subsequent queries don't return stale data
- Files: `backend/services/shared_state.py` (cache invalidation), test coverage in general missing
- Risk: Cache inconsistency not caught until production; users see stale KPIs; leads to wrong business decisions
- Priority: Medium — affects data freshness; doesn't break functionality but reduces trust

**Async State Machine Transitions:**
- What's not tested: Concurrent requests attempting invalid state transitions (e.g., two requests simultaneously trying to activate same pending loanbook)
- Files: `backend/services/shared_state.py` (emit_state_change), `backend/routers/loanbook.py`
- Risk: Race condition allows invalid state; loanbook could be marked activo twice with different cuota dates
- Priority: High — financial impact if state corruption occurs

**Error Recovery in Mass Upload:**
- What's not tested: Partial upload failure (e.g., CSV row 50 of 100 fails); system state after rollback
- Files: `backend/routers/gastos.py` (line 200+ for POST /cargar), `backend/tests/test_build23_*.py`
- Risk: Incomplete upload leaves database in inconsistent state; no clear way for user to resume
- Priority: Medium — affects operational efficiency; not critical but causes data integrity concerns

---

*Concerns audit: 2026-03-24*
