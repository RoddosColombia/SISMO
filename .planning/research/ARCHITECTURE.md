# Architecture Patterns

**Domain:** Fintech lending operations automation — motorcycle portfolio (Colombia)
**Researched:** 2026-03-24
**Confidence:** HIGH (derived from direct codebase analysis, not external sources)

---

## Recommended Architecture

### Current State (Build 23)

The system uses a **Layered Monolith with Event Bus** pattern:

```
┌─────────────────────────────────────────────────────────────────┐
│  Frontend (React 19 + TypeScript)                               │
│  AgentChatPage · Dashboard · Loanbook · CFO · CRM · Inventory   │
└──────────────────────────┬──────────────────────────────────────┘
                           │ HTTP / Axios
┌──────────────────────────▼──────────────────────────────────────┐
│  API Layer (FastAPI)                                             │
│  /chat · /loanbook · /cartera · /radar · /cfo · /conciliacion   │
│  /mercately · /telegram · /alegra_webhooks · /contabilidad      │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│  Agent Orchestration Layer (ai_chat.py — 5,217 lines)           │
│  Context Builder → LLM (Claude Sonnet) → Action Executor        │
└─────────┬────────────────┬────────────────┬────────────────────┘
          │                │                │
┌─────────▼──────┐ ┌───────▼────────┐ ┌────▼────────────────────┐
│ Contador Agent │ │   CFO Agent    │ │   RADAR Agent           │
│ accounting_    │ │ cfo_agent.py   │ │ loanbook_scheduler.py   │
│ engine.py      │ │ cfo_estrategico│ │ + mercately.py          │
│ bank_reconcil. │ │                │ │                         │
└─────────┬──────┘ └───────┬────────┘ └────┬────────────────────┘
          │                │               │
┌─────────▼────────────────▼───────────────▼────────────────────┐
│  Event Bus (append-only MongoDB: roddos_events)                │
│  emit_event() → stores event → modules_to_notify metadata      │
│  shared_state.py: emit_state_change() + TTL cache (30s)        │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│  Data Layer (MongoDB Atlas via Motor async)                     │
│  loanbook · inventario_motos · crm · roddos_events             │
│  accounting_entries · contabilidad_pendientes · shared_state   │
│  learning_outcomes · learning_patterns · cfo_informes          │
└─────────────────────────────┬──────────────────────────────────┘
                              │
┌─────────────────────────────▼──────────────────────────────────┐
│  External Integrations                                          │
│  Alegra API (accounting system of record)                      │
│  Mercately (WhatsApp delivery)                                 │
│  Telegram Bot (document ingestion)                             │
│  Anthropic API (Claude Sonnet LLM)                             │
└────────────────────────────────────────────────────────────────┘
```

### Target Architecture (Next Milestone)

The next milestone adds three vertical capability layers on top of the existing bus:

```
┌──────────────────────────────────────────────────────────────────┐
│  FASE 1: Accounting Automation Completion                        │
│  Contador Agent 8.5/10: smoke test 20/20                        │
│  bank_reconciliation → accounting_engine → Alegra journal       │
│  contabilidad_pendientes review UI                              │
└──────────────────────────┬───────────────────────────────────────┘
                           │ emits: asiento.contable.creado
┌──────────────────────────▼───────────────────────────────────────┐
│  FASE 2: Portfolio Intelligence (RADAR + Loanbook Agent)        │
│  DPD/bucket scoring · predictive risk (learning_engine)         │
│  smart collection queue · PTP follow-up orchestration           │
└──────────────────────────┬───────────────────────────────────────┘
                           │ emits: cliente.mora.detectada / pago.cuota.registrado
┌──────────────────────────▼───────────────────────────────────────┐
│  FASE 3: Digital Sovereignty (self-hosted infra)                │
│  Eliminate Render dependency · self-hosted LLM fallback         │
│  DIAN live integration · automated observability                │
└──────────────────────────────────────────────────────────────────┘
```

---

## Component Boundaries

### Existing Components (Build 23)

| Component | Responsibility | Communicates With |
|-----------|---------------|-------------------|
| `ai_chat.py` | LLM orchestration, context building, action execution for Contador agent | Alegra API, MongoDB, event_bus |
| `accounting_engine.py` | Rule-based transaction classification (50+ rules, priority algorithm) | Called from bank_reconciliation, ai_chat |
| `bank_reconciliation.py` | Parse bank extracts (4 banks), classify, create Alegra journals | accounting_engine, Alegra API, MongoDB |
| `cfo_agent.py` | Financial KPI aggregation, CFO report generation via LLM | MongoDB, Anthropic LLM |
| `loanbook_scheduler.py` | 12 CRON jobs: DPD calc, alerts, scores, ML patterns, CEO summary | Mercately, event_bus, MongoDB |
| `shared_state.py` | Central TTL cache (30s) + event-driven invalidation + state machine | MongoDB (roddos_events), all routers |
| `learning_engine.py` | Behavioral patterns per client, template optimization, risk scores | MongoDB (learning_outcomes, learning_patterns) |
| `event_bus.py` | Append-only event emission to roddos_events collection | MongoDB only |
| `alegra_service.py` | Alegra REST API client with caching for accounts and settings | Alegra API (httpx) |
| `mercately.py` (router) | WhatsApp webhook intake, intent classification, outbound messages | Mercately API, ai_chat, MongoDB |

### Components Needed for Next Milestone

| Component | Responsibility | Depends On |
|-----------|---------------|------------|
| `agent_prompts.py` | Extracted system prompts for Contador — replaces embedded strings in ai_chat.py | Nothing (pure data) |
| `context_builder.py` | Builds financial context dicts injected into LLM calls — split from ai_chat.py | MongoDB, alegra_service |
| `file_parser.py` | Tabular/PDF parsing isolated — replaces `_tabular_to_text()` in ai_chat.py | openpyxl, pdfplumber |
| `smoke_test_runner.py` | Automated 20-action smoke test against real Alegra IDs | ai_chat, Alegra API |
| `collection_intelligence.py` | PTP success prediction, next-best-action recommendation | learning_engine, loanbook data |
| `portfolio_analytics.py` | Aggregated cartera KPIs: by bucket, by modelo, by cohort | MongoDB (loanbook collection) |
| Infrastructure layer | Self-hosted deployment config (Docker Compose + reverse proxy) | Render.yaml replacement |

---

## Data Flow

### Flow 1: Accounting Automation (Contador Agent)

```
User/Scheduler
     │
     ▼
POST /api/conciliacion/cargar-extracto
     │  (bank Excel/CSV uploaded)
     ▼
BankReconciliationEngine.procesar_extracto()
     │
     ├── extract_proveedor(descripcion)    ← accounting_engine
     ├── clasificar_movimiento()           ← accounting_engine (50+ rules)
     │       ├── confidence >= 0.7 → create Alegra journal immediately
     │       └── confidence < 0.7  → insert into contabilidad_pendientes
     │
     ├── emit_event(db, "conciliacion", "asiento.contable.creado", payload)
     │         └── stored in roddos_events (append-only)
     │
     └── POST /api/alegra/journal  → Alegra API
              └── response logged to audit_logs
```

**Key constraint:** Alegra is the system of record. Every journal entry MUST be created in Alegra. MongoDB stores a reference/mirror, never the authoritative record.

### Flow 2: Collection Intelligence (RADAR Agent)

```
APScheduler (06:00 AM daily, America/Bogota)
     │
     ▼
calcular_dpd_todos()
     │  reads loanbook collection, calculates DPD per cuota
     ├── updates dpd_bucket field in loanbook
     ├── emits cliente.mora.detectada if DPD crosses threshold
     │
     ▼
alertar_buckets_criticos()
     │  reads clients with DPD 8, 15, 22+
     ├── generates WhatsApp message from learning_patterns template
     ├── enviar_whatsapp() → Mercately API
     │
     ▼
calcular_scores()
     │  learning_engine.calcular_score_cliente()
     ├── updates client risk score (A+ through E)
     │
     ▼
alertas_predictivas()
     │  learning_engine.detectar_patrones()
     └── proactive alert if client trending toward deterioration
```

**Key constraint:** If `mercately_config.api_key` is empty, scheduler only logs — never crashes. WhatsApp delivery is best-effort, not transactional.

### Flow 3: Portfolio Health Cache

```
Any write operation (payment, mora, loanbook creation)
     │
     ├── emit_state_change(db, event_type, entity_id, new_state)
     │       └── inserts roddos_events(estado='processed')
     │       └── _invalidate_keys([affected cache keys])
     │
     ▼
shared_state._cache is cleared for affected keys

Next read (GET /radar/portfolio-health)
     │
     ├── _cache_get("portfolio_health") → miss (just invalidated)
     ├── query MongoDB loanbook collection
     ├── compute health metrics
     └── _cache_set("portfolio_health", result)  ← TTL 30s restarts
```

**Key constraint:** Cache invalidation is dispersed across 10+ call sites (known debt). New writes must explicitly call `emit_state_change()` or `invalidar_cache_cfo()` or stale data leaks into dashboards.

### Flow 4: WhatsApp Intent Processing

```
Mercately webhook → POST /api/mercately/webhook  (public, no auth)
     │
     ├── classify sender: CLIENTE | INTERNO | DESCONOCIDO
     │
     ├── CLIENTE:
     │       ├── saldo/deuda intent → query loanbook, respond with balance
     │       ├── pago intent → start payment verification flow
     │       │       └── if photo attached → process_document_chat() → Telegram-style AI
     │       └── dificultad intent → PTP negotiation flow → learning_engine.crear_outcome()
     │
     ├── INTERNO:
     │       └── factura proveedor → execute_chat_action("crear_bill", payload)
     │
     └── DESCONOCIDO:
             └── process_chat() → Contador agent for context-free analysis
```

---

## Patterns to Follow

### Pattern 1: Event-First State Changes

**What:** Any operation that changes financial state MUST emit an event via `emit_event()` or `emit_state_change()` before returning.

**When:** Every write that changes loanbook status, creates accounting entries, registers payments, or modifies inventory.

**Why:** The append-only `roddos_events` collection is the audit trail. Operations without events are invisible to the bus and break downstream agents.

```python
# In any router that modifies financial state:
result = await do_financial_operation(db, payload)
await emit_event(
    db,
    source="loanbook",
    event_type="pago.cuota.registrado",
    payload={"loanbook_id": id, "monto": monto, "cuota_num": num},
    alegra_synced=True,
)
return result
```

### Pattern 2: Confidence-Gated Automation

**What:** Use a confidence threshold (default 0.70) to decide between fully automated and human-in-the-loop.

**When:** Any AI classification where incorrect automation causes financial errors.

**Why:** Low-confidence entries silently pushed to Alegra accumulate into unrecoverable accounting errors. The `contabilidad_pendientes` queue is the safety valve.

```python
result = accounting_engine.clasificar_movimiento(movimiento)
if result.confianza >= 0.70:
    await alegra_service.crear_journal(result)
    await emit_event(db, "contador", "asiento.contable.creado", {...}, alegra_synced=True)
else:
    await db.contabilidad_pendientes.insert_one({**result.__dict__, "estado": "pendiente"})
```

### Pattern 3: Scheduler-Safe WhatsApp Dispatch

**What:** Always check `mercately_config.api_key` before attempting WhatsApp delivery. Never let missing config crash the scheduler.

**When:** Any scheduled task that sends WhatsApp messages.

**Why:** WhatsApp API key may be unconfigured in staging/dev. A crash in the scheduler stops ALL 12 CRON jobs.

```python
cfg = await _get_mercately_config()
if not cfg.get("api_key"):
    logger.info("WA sin config — solo log")
    return False
ok = await enviar_whatsapp(telefono, mensaje)
# Always log regardless of delivery result
await emit_event(db, "scheduler", "wa.sent" if ok else "wa.failed", {...})
```

### Pattern 4: Alegra-as-Record, MongoDB-as-Cache

**What:** Alegra holds the authoritative financial record. MongoDB mirrors for speed. Never let MongoDB diverge as the source of truth for accounting data.

**When:** Creating journals, invoices, bills, payments.

**Why:** RODDOS uses Alegra for tax compliance (Colombia DIAN integration). If MongoDB is ever inconsistent with Alegra, the accounting is legally wrong.

```python
# Correct order: Alegra first, then local mirror
alegra_id = await alegra_service.crear_journal(entry)
await db.accounting_entries.insert_one({**entry, "alegra_id": alegra_id, "synced": True})
```

---

## Anti-Patterns to Avoid

### Anti-Pattern 1: Agent-to-Agent Direct Calls

**What:** One agent importing and directly calling another agent's functions.

**Why bad:** Breaks the core bus principle. Creates hidden coupling. The Contador calling RADAR directly means a Contador failure kills RADAR.

**Instead:** Emit an event. Let the subscriber handle it asynchronously.

```python
# BAD: Direct coupling
from services.cfo_agent import generar_semaforo
result = await generar_semaforo(db)  # Contador should never do this

# GOOD: Event-driven
await emit_event(db, "contador", "asiento.contable.creado", payload)
# CFO agent reacts to this event independently
```

### Anti-Pattern 2: Confidence Bypass for Speed

**What:** Routing low-confidence classifications directly to Alegra to reduce the pendientes queue.

**Why bad:** Creates ghost entries in the accounting books. Reversals in Alegra require manual journal entries and create audit trail pollution that makes DIAN reconciliation impossible.

**Instead:** Invest in improving the classification rules or LLM prompt before removing the confidence gate.

### Anti-Pattern 3: Scheduler Logic in Routers

**What:** Moving DPD calculation or scoring logic into HTTP router handlers (e.g., triggered on payment registration).

**Why bad:** Router latency bloat (DPD calc is O(n) across all loanbooks). Duplicate execution risk if payment retried. APScheduler already runs this at 06:00 AM.

**Instead:** Register payment via router, emit event, let scheduler pick up on next cycle. If realtime DPD is needed, add a narrow endpoint that recalculates a single loanbook.

### Anti-Pattern 4: Expanding ai_chat.py Further

**What:** Adding new agent logic (RADAR chat, Loanbook agent conversation) inside `ai_chat.py`.

**Why bad:** Already 5,217 lines — the most-cited tech debt in CONCERNS.md. Any new agent logic added here becomes untestable. The file is a single point of failure for all agent intelligence.

**Instead:** Create `services/agent_[name].py` files that expose a `process_query(message, db, session_id)` interface. Router selects the agent by intent before delegating.

### Anti-Pattern 5: Polling Instead of Cache Invalidation

**What:** Reducing the TTL cache from 30s to 5s to solve staleness problems.

**Why bad:** Each Dashboard load hits 4+ aggregation endpoints. A 5s TTL means 12 aggregation queries per minute per user during active work sessions. Mongo Atlas free tier chokes.

**Instead:** Event-driven invalidation is already implemented in `shared_state.emit_state_change()`. Any write that modifies financial state must call this. Fix the missing invalidation call sites (identified in CONCERNS.md) rather than shrinking TTL.

---

## Scalability Considerations

| Concern | At 10 loanbooks (now) | At 100 loanbooks | At 500 loanbooks |
|---------|----------------------|------------------|------------------|
| DPD CRON job | <1s, single query | ~5s, acceptable | >30s, needs aggregation pipeline |
| roddos_events collection | ~500 docs/week, fast | ~5K docs/week, needs TTL index | ~25K docs/week, needs archival strategy |
| Alegra API rate limit | ~50 req/day, fine | ~500 req/day, monitor | ~2,500 req/day, batch required |
| CFO dashboard aggregation | <200ms | ~800ms, add index | timeout risk, denormalize |
| WhatsApp daily dispatch | 10 messages/day | 100 messages/day, batch | 500/day, rate limit concern |
| BackgroundTasks queue | ~5 concurrent | ~20 concurrent, fine | >50 concurrent, move to Celery |

---

## Suggested Build Order for Next Milestone

The component dependencies create a clear build sequence:

### Stage 1 — Stabilize Contador Foundation (prerequisite for everything)

1. **Fix provider extraction bug** (bank_reconciliation.py line 357, known bug in CONCERNS.md)
   — Unblocks 30+ classification rules from inactive to active
   — Zero other dependencies, highest ROI fix in the codebase

2. **Extract `file_parser.py` from ai_chat.py**
   — Required before smoke test can run cleanly (file processing is current failure mode)
   — No consumers except ai_chat.py itself

3. **Extract `context_builder.py` from ai_chat.py**
   — Required for clean Contador agent isolation
   — Blocked by: nothing; blocks smoke test authoring

4. **Smoke test: 20 actions, real Alegra IDs**
   — Validates Contador agent at 8.5/10
   — Blocked by: steps 1-3 above

### Stage 2 — Portfolio Intelligence Layer

5. **`portfolio_analytics.py`**: DPD cohort analysis, bucket distribution, collection rate by model
   — Reads loanbook collection only, no external dependencies
   — Blocked by: nothing; unblocks RADAR dashboard upgrade

6. **`collection_intelligence.py`**: next-best-action engine using learning_patterns
   — Reads learning_patterns, loanbook, CRM collections
   — Blocked by: step 5 (needs portfolio data as input)

7. **RADAR queue upgrade**: incorporate collection_intelligence recommendations into daily queue
   — Blocked by: steps 5-6

### Stage 3 — Digital Sovereignty

8. **Docker Compose deployment** replacing Render dependency
   — Blocked by: stable codebase from stages 1-2 (dangerous to containerize unstable code)

9. **DIAN live integration** (requires provider certificate — external dependency)
   — Blocked by: DIAN certificate acquisition (business decision, not technical)

10. **Observability layer** (structured logging, health endpoint)
    — Can start anytime but logical to do after major feature work settles

---

## Known Architecture Debt Relevant to Next Milestone

| Debt Item | Source | Impact on Milestone | Resolution Approach |
|-----------|--------|---------------------|---------------------|
| `ai_chat.py` monolith (5,217 lines) | CONCERNS.md | Blocks clean Contador smoke test isolation | Extract to `agent_prompts.py`, `context_builder.py`, `file_parser.py` |
| Provider extraction not called in bank_reconciliation | CONCERNS.md | 30+ classification rules inactive, 40% accuracy | One-line fix: call `extract_proveedor()` at line 357 |
| Cache invalidation at 10+ call sites | CONCERNS.md | Stale CFO dashboard after new writes | Add `@invalidates_cfo_cache` decorator pattern |
| No health endpoint | CONCERNS.md | Render restarts silently; no observability | Add `GET /health` with dependency checks |
| Event bus has no retry/dead-letter | CONCERNS.md | Failed events silently lost | Add `estado: failed` + retry count field to roddos_events |
| Frontend polling every 3s in AgentChatPage | CONCERNS.md | Unnecessary API load during inactive sessions | Page Visibility API + exponential backoff |

---

## Sources

- Direct codebase analysis: `.planning/codebase/ARCHITECTURE.md` (2026-03-24)
- Integration audit: `.planning/codebase/INTEGRATIONS.md` (2026-03-24)
- Tech debt inventory: `.planning/codebase/CONCERNS.md` (2026-03-24)
- Source files analyzed: `event_bus.py`, `services/shared_state.py`, `services/accounting_engine.py`, `services/bank_reconciliation.py`, `services/cfo_agent.py`, `services/loanbook_scheduler.py`, `services/learning_engine.py`, `routers/chat.py`, `routers/radar.py`, `routers/cartera.py`, `routers/conciliacion.py`, `routers/contabilidad_pendientes.py`, `routers/mercately.py`, `routers/cfo_estrategico.py`
- Confidence: HIGH — all findings derived from live production code, not external sources
