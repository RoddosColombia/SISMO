# Feature Landscape

**Domain:** Fintech lending operations platform — motorcycle financing, Colombia
**Project:** SISMO (Sistema Inteligente de Soporte y Monitoreo Operativo) for RODDOS S.A.S.
**Researched:** 2026-03-24
**Confidence:** MEDIUM — Domain knowledge from training data + deep codebase analysis. No live web search available.

---

## Context: What Already Exists

SISMO at BUILD 23 already has:

- Dashboard KPIs (ventas, caja, cartera)
- Loanbook management with 4 plan types (Contado/P39S/P52S/P78S)
- AI agent (Contador) for accounting operations via chat
- Alegra integration (invoices, bills, contacts, payments)
- WhatsApp webhook via Mercately (intent detection: saldo, pago, dificultad)
- Telegram webhook for document upload + AI analysis
- CRM with client management
- Inventory with real VINs (34 TVS motos)
- Append-only event bus in MongoDB
- JWT auth with roles
- CFO operational + strategic dashboards
- Accounting engine with 50+ classification rules
- Bank reconciliation (partial — proveedor bug)
- APScheduler for background tasks

The three active milestones add: **complete financial system (FASE 1)**, **portfolio intelligence (FASE 2)**, and **digital sovereignty / self-hosted infra (FASE 3)**.

---

## Table Stakes

Features operators of a motorcycle fintech in Colombia expect as baseline. Missing = users reject the system or regulatory issues arise.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Cuota schedule generation with dates | Every lender needs a payment calendar | Low | Already exists; fragile on delivery-date edge cases |
| Payment registration with Alegra sync | Financial truth must be in accounting system | Low | Exists but cache invalidation bug |
| Days-past-due (DPD) tracking per loan | Credit health measurement; required for portfolio decisions | Low | Exists as dpd_bucket concept; needs to be surfaced cleanly |
| Overdue detection + collection queue | Without this, losses mount silently | Medium | Loanbook scheduler partially does this; RADAR agent stub |
| WhatsApp payment reminders (cobranza) | 100% remote collection means WhatsApp IS the collection channel | Medium | Intent detection exists; outbound messaging not confirmed as complete |
| Manual payment recording with receipt | Evidence trail for cada pago; audit requirement | Low | Exists via modal + Alegra |
| Loan state machine (pendiente → activo → cancelado) | Prevents ghost loans and double-counting | Medium | Fragile; no FSM enforcement currently |
| Bank extract reconciliation | Manual cash matching is unscalable; 10 loanbooks need automated matching | High | Partial — proveedor bug breaks 40% of rule accuracy |
| P&L statement view | Operator needs to know if business is profitable | Medium | CFO estrategico has this; needs to be reliable |
| Inventory lifecycle (disponible → vendida → entregada) | Cannot sell the same moto twice | Low | Exists; fragile on state transitions |
| Client deduplication in CRM | Duplicate clients corrupt portfolio math | Low | CRM exists; dedup logic unclear |
| Accounting entries with correct chart-of-accounts mapping | RODDOS must file taxes; needs clean libros | High | accounting_engine exists; 50+ rules, but ~40% accuracy today |
| Role-based access (admin vs operador) | Small team but sensitive financial data | Low | JWT + roles exist |
| PDF/Excel export of payment history | Clients ask for paz y salvo; Colombian regulatory norm | Medium | Export exists for some reports |
| Cuota recalculation after partial payment or grace period | Customers miss payments; schedule must auto-adjust | High | recalcular endpoint exists (BUILD 23); needs validation |

---

## Differentiators

Features that RODDOS could use to outperform manual spreadsheet operations or basic accounting software. Not expected by default, but create real competitive and operational value.

### Complete Financial System (FASE 1 — Active)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Automated accounting classification (no human touch) | 2-5 person team cannot manually classify every transaction; automated = scale | High | Core goal of Agente Contador; 8.5/10 target |
| Full-cycle accounting smoke test (20/20) | Confidence that accounting is correct end-to-end; compliance safety net | High | Active requirement; smoke test 20 scenarios with real Alegra IDs |
| Expense causation from Telegram photos | Photo → accounting entry in Alegra without typing; saves hours weekly | Medium | Telegram webhook + Claude analysis exists; full execution path needs verification |
| DIAN factura auto-causation | Tax compliance without manual entry; required for compras with CUFE | High | Currently stubbed; needs Alanube/MATIAS provider + certificate |
| Bank extract auto-reconciliation (95%+ match rate) | 10 loanbooks generates ~50+ transactions/month; manual matching is fragile | High | Blocked by proveedor bug; fix is documented but not deployed |
| Supplier invoice auto-registration from WhatsApp | Supplier sends invoice via WhatsApp → auto-created in Alegra | Medium | INTERNO message type detected; processing path unclear |
| Closed accounting period enforcement | Prevent backdating entries; integrity of monthly financials | Medium | Not confirmed as existing; standard in accounting systems |
| Chart-of-accounts learning from corrections | Agent improves classification over time based on user corrections | High | learning_engine.py exists; depth unclear |

### Portfolio Intelligence (FASE 2 — Active)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Portfolio health dashboard with DPD buckets | At-a-glance view: how many clients are 0/30/60/90+ days overdue | Medium | DPD concept exists in codebase; dashboard view needs assembly |
| Early warning system (semaforo) | Flag loans trending toward default before they go hard-delinquent | High | Semaforo API endpoint exists in dashboard; sophistication unclear |
| Collection prioritization queue | Tell collection agent: "call these 3 first today" based on risk score | High | RADAR agent concept exists; implementation depth unknown |
| Predictive default risk per borrower | Score each borrower's probability of default using payment history patterns | High | Requires historical data accumulation; medium-term play |
| Portfolio concentration analysis | Identify risk concentration (same zone, same employer, same moto model) | Medium | CFO estrategico may have pieces; explicit concentration view missing |
| Recovery strategy by vintage cohort | Group loans by origination month; track cohort performance over time | High | Requires multi-month history; long-term intelligence feature |
| WhatsApp auto-response with saldo + next cuota | Client sends "cuanto debo" → instant automated response | Medium | Intent detected; response generation path needs to be closed-loop |
| Collection workflow tracking (gestiones) | Record every collection touch: call attempt, promise-to-pay, result | Medium | gestion endpoint exists in loanbook; reporting view may be missing |
| Restructuring / acuerdo de pago workflow | Formalize payment agreements when client in difficulty | Medium | Partially exists; needs structured workflow |

### Digital Sovereignty (FASE 3 — Active)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Self-hosted LLM option (Ollama/LM Studio) | No Claude API dependency for core classification; cost and privacy control | High | Requires model evaluation for accounting classification quality |
| Self-hosted WhatsApp alternative (Chatwoot/WATI direct) | Mercately is a third-party dependency for critical collection channel | High | Migration risk; Mercately webhooks currently working |
| Local backup + restore for MongoDB | Data sovereignty; no Atlas dependency for business continuity | Medium | Currently Atlas-only; local Mongo + replication target |
| On-premise deployment option | Run SISMO on own hardware if needed; no Render.com dependency | High | render.yaml exists; Docker Compose for local deployment needed |
| Encrypted secrets management | Avoid credentials in .env; vault-based secret storage | Medium | Current: .env + MongoDB fallback; risk documented |
| Audit trail export (immutable) | Legal protection; every financial action attributable | Medium | roddos_events is append-only; export format + immutability guarantee needed |
| API key rotation without downtime | Rotate Alegra/Anthropic/Mercately keys without service interruption | Medium | Not confirmed as existing; operational necessity |

### Cross-Cutting Differentiators (Any Phase)

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Real-time CFO financial narrative | LLM explains "your portfolio health dropped because..." not just numbers | Medium | cfo_agent.py exists; quality of narrative unclear |
| Batch payment processing from bank file | Upload one bank file; system matches and posts 30 payments automatically | High | Partial — bank extract + classification exists; automatic posting blocked by bugs |
| Paz y salvo auto-generation | Client finishes paying → document generated automatically | Low | High value for customer UX; simple if loan state machine is clean |
| Payment link via WhatsApp | Send Nequi/Bancolombia payment link directly from collection queue | Medium | Requires PSP integration; outside current scope |

---

## Anti-Features

Features to explicitly NOT build in current milestones. Either scope creep risks, architectural violations, or things that undermine the core value proposition.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| Native mobile app | Out of scope per PROJECT.md; 2-5 person team can't maintain two frontends | Keep web responsive; optimize for mobile browser |
| Multi-tenancy | SISMO is RODDOS-exclusive; multi-tenant adds massive auth/data isolation complexity | Single-tenant by design |
| Direct bank API integration | Colombian bank APIs (Bancolombia, Nequi) require lengthy PSP agreements; not available quickly | CSV/Excel extract reconciliation as permanent solution |
| Custom accounting engine replacing Alegra | Alegra is system of record; replacing it means rebuilding tax compliance | Classify in SISMO, post to Alegra — this is the correct split |
| Full DIAN SOAP implementation without certificate | Cannot test in production without habilitación certificate; waste without it | Stub until certificate secured; use Alanube as proxy |
| Multi-currency support | RODDOS is COP-only; adding FX adds complexity with no current business need | Single currency; revisit only if international expansion confirmed |
| Customer-facing portal | Clients communicate via WhatsApp; a portal adds UX surface with no adoption path | WhatsApp remains the customer channel |
| AI agent autonomy without human confirmation | Financial operations must have a human in the loop for approval | Agent proposes → human confirms → system executes |
| Real-time chat with external parties | Agents orchestrate; they don't replace operator judgment on complex cases | Keep agents advisory; operator decides |
| Complex approval workflows | Team is 2-5 people; approval chains add friction for no compliance benefit | Single-role confirmation; admin override |
| SMS fallback for WhatsApp | Adds a second messaging channel to maintain; WhatsApp penetration in Colombia is near-universal | Monitor Mercately reliability; implement circuit breaker instead |
| Predictive credit scoring at origination | SISMO is operations, not origination; lending decisions made before loanbook is created | Collect data now; scoring feature is a future standalone milestone |

---

## Feature Dependencies

```
Bank extract reconciliation
  → Correct proveedor extraction (bug fix required first)
  → accounting_engine rule evaluation
  → Alegra journal entry creation

DIAN auto-causation
  → DIAN provider (Alanube/MATIAS) integration
  → Certificate in habilitacion environment
  → Alegra bill auto-creation

WhatsApp auto-response (saldo + cuota)
  → Closed-loop: intent detection → loanbook query → response generation → Mercately send
  → Loanbook state must be accurate (loan state machine fix required)

Portfolio health dashboard
  → DPD tracking accuracy (requires cuota date calculation fix)
  → Loanbook state machine correctness
  → Historical data accumulation (at least 90 days of clean data)

Early warning semaforo (reliable)
  → Portfolio health dashboard is accurate first
  → Cache invalidation fixed (so semaforo reflects current state)

Collection prioritization queue
  → DPD buckets accurate
  → gestiones history populated
  → WhatsApp send confirmed working

Paz y salvo auto-generation
  → Loan state machine: activo → cancelado transition clean
  → All cuotas marked pagado correctly

Digital sovereignty (self-hosted LLM)
  → Accounting classification accuracy established first
  → Baseline smoke test 20/20 passing (know what quality bar to match)

Smoke test 20/20 (Agente Contador)
  → accounting_engine proveedor bug fixed
  → Alegra sync for all entry types working
  → Real Alegra IDs in test fixtures
```

---

## MVP Recommendation for Three Active Milestones

### FASE 1 — Complete Financial System (Prioritize):
1. Fix proveedor extraction bug in bank_reconciliation.py (unblocks 40% accuracy gain)
2. Smoke test 20/20 with real Alegra IDs (validates accounting completeness)
3. Expense causation from Telegram photo (closes the loop for most common daily operation)
4. Bank extract auto-reconciliation at 90%+ match (eliminates manual matching work)

Defer from FASE 1: DIAN until certificate secured; multi-currency forever

### FASE 2 — Portfolio Intelligence (Prioritize):
1. Fix loanbook state machine (prerequisite for everything)
2. DPD dashboard with buckets (0/1-30/31-60/61-90/90+)
3. WhatsApp auto-response: saldo + proxima cuota (closes collection loop)
4. Collection queue with priority ranking (directs daily work)

Defer from FASE 2: Predictive scoring (needs 6+ months of data); cohort analysis (premature)

### FASE 3 — Digital Sovereignty (Prioritize):
1. Self-hosted deployment option via Docker Compose (removes Render.com dependency)
2. Encrypted secrets management (removes .env credential risk)
3. Audit trail export in immutable format (legal protection)
4. Circuit breaker for Mercately outages (resilience without replacing provider)

Defer from FASE 3: Self-hosted LLM (quality risk; evaluate when accounting engine is 95%+ accurate); full Mercately replacement (working system; only replace with evidence of risk)

---

## Complexity Reference

**Low:** 1-3 days, single module, no new integrations
**Medium:** 1-2 weeks, multiple modules, may touch existing integrations
**High:** 2-4 weeks, new architectural components, third-party integrations, or correctness constraints

---

## Sources

- SISMO PROJECT.md — validated requirements and out-of-scope items
- SISMO INTEGRATIONS.md — current integration capabilities
- SISMO ARCHITECTURE.md — data flows and module boundaries
- SISMO CONCERNS.md — tech debt, known bugs, missing critical features
- Domain knowledge: Colombian fintech lending operations, Alegra accounting software capabilities, WhatsApp-first collection workflows
- Confidence: MEDIUM — No live research available; based on codebase analysis + training-data domain knowledge of fintech lending platforms in LatAm
