# Technology Stack

**Project:** SISMO — Fintech Lending Operations Automation (RODDOS S.A.S.)
**Researched:** 2026-03-24
**Scope:** Additional components needed for Phase 1 (accounting automation), Phase 2 (portfolio intelligence), Phase 3 (digital sovereignty). Existing stack NOT re-evaluated.

---

## Existing Stack (DO NOT CHANGE)

Locked in production with real financial data. This research adds to it, never replaces it.

| Layer | Technology | Version |
|-------|------------|---------|
| Backend | FastAPI + Python | 0.110.1 / 3.11.0 |
| Frontend | React + TypeScript | 19.0.0 / 5.9.3 |
| Database | MongoDB Atlas + Motor | latest / 3.7.0 |
| AI | Claude Sonnet via Anthropic SDK | 0.34.0 |
| Accounting | Alegra API | (external) |
| WhatsApp | Mercately webhooks | (external) |
| Scheduler | APScheduler | 3.10.4 |
| Hosting | Render.com | (PaaS) |

---

## Phase 1 Additions: Accounting Automation Smoke Test 20/20

### Testing Infrastructure

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pytest** | 8.3.x | Test runner for smoke tests | Industry standard, async support via pytest-asyncio, zero config overhead. unittest is verbose; pytest fixtures are cleaner for Alegra mock/real dual mode. |
| **pytest-asyncio** | 0.23.x | Async test support | SISMO is fully async (Motor, httpx). Required to await FastAPI routes and Motor queries in tests. |
| **httpx** | 0.27.0 | Already installed — use as test client | `httpx.AsyncClient` with `transport=ASGITransport(app=app)` replaces TestClient for async endpoints. Already in requirements. |
| **pytest-mock** | 3.14.x | Mock Alegra API calls | Isolates accounting engine tests from Alegra rate limits. `mocker.patch` on `httpx.AsyncClient.post` intercepts Alegra calls without changing production code. |

**Confidence: HIGH** — pytest + pytest-asyncio is the canonical async FastAPI testing stack. No alternatives needed.

**What NOT to use:**
- `unittest.TestCase` — verbose, no async support without extra wrappers
- `respx` (httpx mock library) — adds dependency; `pytest-mock` covers the need with less surface area

### Smoke Test Architecture Decision

The 20/20 smoke test (ciclo completo contable) should run against **real Alegra sandbox** with real IDs, matching the existing decision "Smoke test con IDs reales de Alegra." This means:

- Tests are **integration tests**, not unit tests
- They validate the accounting_engine classification rules end-to-end
- `pytest -m smoke` marker separates them from unit tests
- No fixture mocking for Alegra — use real Alegra test credentials

### Accounting Engine Refactor Support

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **No new library** | — | ai_chat.py split | The 5,217-line ai_chat.py is a tech debt issue, not a library gap. Solution is extraction into modules (contador_agent.py, cfo_agent.py, radar_agent.py, loanbook_agent.py) using existing Python stdlib. |

---

## Phase 2 Additions: Portfolio Intelligence

### Financial Analytics

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pandas** | 2.2.2 | Already installed — portfolio KPI calculation | Already in stack. Use it for cartera aging buckets, PAR (Portfolio At Risk) ratios, cohort analysis by loanbook vintage. |
| **numpy** | 1.26.x | Numerical operations for risk metrics | pandas dependency, likely already installed transitively. Needed for IRR/NPV calculations on loan portfolios. |
| **scipy** | 1.13.x | Statistical distributions for risk scoring | Provides `scipy.stats` for default probability modeling. Lightweight addition for a lending-specific risk model. MEDIUM confidence — verify if complexity justifies dependency. |

**Confidence for scipy: MEDIUM** — Useful only if building a full credit scoring model. If portfolio intelligence means dashboards and KPI trends, pandas alone suffices. Defer scipy until Phase 2 design is concrete.

**What NOT to use:**
- `scikit-learn` — heavyweight ML library for a 34-motorcycle portfolio. Overkill. A simple PAR30/PAR60/PAR90 calculation in pandas is more maintainable and auditable.
- `statsmodels` — academic library, poor DX for operational use. Pandas + numpy covers 95% of lending analytics.

### Portfolio Dashboard Backend

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **No new framework** | — | Portfolio API endpoints | Extend existing FastAPI routers. The existing `/api/cfo/*` pattern already serves dashboard data. Add `/api/cartera/*` routes following the same pattern. |

### Forecasting / Cashflow Projection

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **pandas** | 2.2.2 | Already installed — cashflow projections | Loanbook amortization schedules are already calculated in Python. Extend with forward-looking projection using dateutil (already installed). |
| **python-dateutil** | 2.9.0 | Already installed — payment schedule dates | Handles Colombia calendar edge cases (quincenal vs mensual) already used in loanbook logic. |

**Confidence: HIGH** — No new dependencies needed for cashflow forecasting. The existing stack covers it.

---

## Phase 3 Additions: Digital Sovereignty Infrastructure

### Self-Hosted Infrastructure

The "digital sovereignty" principle means SISMO must not depend on third-party platforms for its **operational core**. Current vulnerabilities: Render.com (hosting), MongoDB Atlas (database), Alegra (accounting of record).

#### Hosting Migration (Render → Self-Hosted)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Docker** | 27.x | Container runtime | Industry standard. Packages FastAPI + Python dependencies into portable image. Required for any self-hosted deployment. |
| **Docker Compose** | 2.x | Local and server orchestration | Single-server deployment (not Kubernetes scale). RODDOS is a 2-5 person team — Docker Compose is operationally simpler than k8s and sufficient for the load. |
| **Nginx** | 1.26.x | Reverse proxy + TLS termination | Routes `api.roddos.co` → FastAPI container, `app.roddos.co` → React build. Handles SSL via Let's Encrypt. Battle-tested for this exact pattern. |
| **Certbot** | 3.x | TLS certificate automation | Let's Encrypt integration. Free, automated renewal. Standard for self-hosted web apps in LATAM. |

**Confidence: HIGH** — Docker + Nginx + Certbot is the canonical self-hosted Python app stack in 2025. No exotic alternatives needed.

**What NOT to use:**
- Kubernetes — massive operational overhead for a single-server deployment serving 2-5 users
- Caddy — reasonable alternative to Nginx but introduces another tool to learn; Nginx has more documentation in Spanish
- Traefik — better for multi-container orchestration at scale, not justified here

#### Database Sovereignty (MongoDB Atlas → Self-Hosted)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **MongoDB Community** | 7.0.x | Self-hosted document database | Drop-in replacement for Atlas connection string. Motor driver works identically. Version 7.0 is current LTS as of 2025. |
| **mongodump / mongorestore** | (bundled) | Backup and restore | Official MongoDB tools for backup strategy. Cron job + S3-compatible storage covers RODDOS backup needs. |

**Confidence: HIGH** — MongoDB Community 7.0 with identical Motor connection is the lowest-friction path to database sovereignty.

**What NOT to use:**
- PostgreSQL migration — would require rewriting all Motor queries, breaking production. Out of scope per PROJECT.md constraints.
- DocumentDB (AWS) — still a third-party platform, violates sovereignty principle
- Percona Server for MongoDB — advanced features RODDOS doesn't need; stick with Community

#### Backup / Storage

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **MinIO** | RELEASE.2025-x | S3-compatible object storage | Self-hosted file storage for Excel uploads, PDF reports, document analysis artifacts. S3-compatible API means future migration to AWS S3 is trivial if needed. |

**Confidence: MEDIUM** — MinIO is the standard self-hosted S3 replacement. Verify current release on minio.io before pinning. Flag: only needed if RODDOS wants to stop storing files in MongoDB GridFS or Render ephemeral storage.

**What NOT to use:**
- AWS S3 — cloud dependency, contradicts sovereignty goal
- Cloudflare R2 — another third-party platform

#### CI/CD (Render → Self-Hosted)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **GitHub Actions** | (SaaS) | CI/CD pipeline | Already using GitHub (git repo visible). Free tier covers RODDOS deployment needs. Runs tests (pytest), builds Docker image, pushes to server via SSH. This is the minimum viable CI/CD. |
| **Docker Hub** or **GHCR** | (SaaS) | Container registry | GitHub Container Registry (GHCR) is free for private repos, integrated with GitHub Actions. No additional account needed. |

**Confidence: HIGH** — GitHub Actions + GHCR is the lowest-friction CI/CD for a team already on GitHub.

**What NOT to use:**
- Jenkins — operational overhead, requires dedicated server, overkill for 2-5 person team
- GitLab CI — would require migrating git hosting
- Self-hosted Drone/Woodpecker — adds infrastructure to maintain; GitHub Actions free tier is sufficient

### Monitoring & Observability (Sovereignty)

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **Prometheus** | 2.53.x | Metrics collection | Exposes FastAPI performance metrics. `prometheus-fastapi-instrumentator` (0.6.x) adds /metrics endpoint with zero code changes. Self-hosted, no data leaves the server. |
| **Grafana** | 11.x | Metrics visualization | Dashboards for API response times, error rates, MongoDB query times. Standard companion to Prometheus. Self-hosted, free, battle-tested. |
| **prometheus-fastapi-instrumentator** | 0.6.x | FastAPI metrics middleware | Single decorator on FastAPI app. Exposes request count, latency by endpoint. HIGH confidence — canonical library for FastAPI + Prometheus. |

**Confidence: HIGH** — Prometheus + Grafana is the industry-standard self-hosted observability stack. No LATAM-specific deviation needed.

**What NOT to use:**
- Datadog, New Relic — SaaS, high cost, data sovereignty violation
- OpenTelemetry full suite — adds complexity without proportional benefit for this scale; Prometheus direct instrumentation is simpler
- Sentry (cloud) — for error tracking, use self-hosted Sentry or Glitchtip (lighter alternative)

#### Error Tracking

| Technology | Version | Purpose | Why |
|------------|---------|---------|-----|
| **GlitchTip** | 4.x | Self-hosted error tracking | Open-source Sentry-compatible. Uses Sentry Python SDK (already standard). Lighter than full Sentry self-host. Critical for detecting Alegra sync failures silently. |

**Confidence: MEDIUM** — GlitchTip is the recommended self-hosted Sentry alternative as of 2025. Verify current stability on glitchtip.com before committing to Phase 3.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Test runner | pytest 8.3 | unittest | unittest has no async support without extra wrappers; pytest fixtures cleaner |
| Async test client | httpx (existing) | starlette.testclient | TestClient doesn't support async; httpx ASGITransport does |
| Portfolio analytics | pandas (existing) | scikit-learn | Overkill for 34-unit portfolio; pandas PAR buckets are sufficient and auditable |
| Container orchestration | Docker Compose | Kubernetes | K8s operational overhead unjustified for 2-5 users |
| Reverse proxy | Nginx | Caddy | Nginx has broader Spanish-language documentation; Caddy is valid but adds tool surface |
| Self-hosted DB | MongoDB Community 7.0 | PostgreSQL | Requires full rewrite of Motor queries; violates "no migrate" constraint |
| Observability | Prometheus + Grafana | Datadog | Datadog violates sovereignty principle and costs $15+/host/month |
| Error tracking | GlitchTip | Sentry cloud | Sentry cloud violates sovereignty; self-hosted Sentry is heavy |
| CI/CD | GitHub Actions | Jenkins | Jenkins requires dedicated server and full-time maintenance mindset |

---

## Installation Summary

### Phase 1 — Add to Python requirements

```bash
# Testing
pytest==8.3.4
pytest-asyncio==0.23.8
pytest-mock==3.14.0
# httpx already installed at 0.27.0
```

### Phase 2 — Add to Python requirements

```bash
# numpy likely already installed as pandas dependency — verify
numpy==1.26.4
# scipy only if credit scoring model is in scope
scipy==1.13.1
```

### Phase 3 — Infrastructure (Docker-based, not pip)

```dockerfile
# docker-compose.yml services:
# - fastapi (existing app, containerized)
# - mongodb (community 7.0)
# - nginx (1.26)
# - prometheus (2.53)
# - grafana (11.x)
# - glitchtip (4.x)
# - minio (latest)
```

```bash
# Python additions for Phase 3
prometheus-fastapi-instrumentator==0.6.1
sentry-sdk==2.x  # GlitchTip uses Sentry SDK protocol
```

---

## Critical Constraint Reminders

1. **Do not migrate database** — MongoDB Atlas → Community 7.0 is connection-string swap only
2. **Do not replace Alegra** — It is the accounting system of record per PROJECT.md
3. **Do not replace APScheduler** — Already handling background jobs; adding Celery would require Redis and extra infrastructure
4. **ai_chat.py refactor is code restructuring**, not a library problem — no new dependency resolves the 5,217-line file
5. **DIAN integration remains stubbed** — No DIAN library needed until certificate acquired

---

## Sources

- Python ecosystem knowledge (training cutoff August 2025) — HIGH confidence for pytest, Docker, Nginx, Prometheus/Grafana stack
- FastAPI official documentation patterns for async testing — HIGH confidence
- MongoDB Community 7.0 LTS status — HIGH confidence (stable release since 2023)
- GlitchTip current status — MEDIUM confidence (verify at glitchtip.com before Phase 3 commit)
- scipy for credit scoring — MEDIUM confidence (scope-dependent, verify Phase 2 requirements before adding)
- MinIO current release version — MEDIUM confidence (verify at minio.io before Phase 3 commit)
