---
phase: 1
slug: contador-core
status: draft
nyquist_compliant: true
wave_0_complete: false
created: 2026-03-24
---

# Phase 1 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | run_smoke_test.py (requests, custom script) — no pytest detected |
| **Config file** | None — smoke test is standalone script |
| **Quick run command** | `python backend/run_smoke_test.py` |
| **Full suite command** | `python backend/run_smoke_test.py` |
| **Estimated runtime** | ~60 seconds (20 tests against live Alegra API) |

---

## Sampling Rate

- **After every task commit:** Run `python backend/run_smoke_test.py` — verify affected tests pass
- **After every plan wave:** Run `python backend/run_smoke_test.py` — 20/20 green
- **Before `/gsd:verify-work`:** Full suite must be green (20/20)
- **Max feedback latency:** ~60 seconds

---

## Per-Task Verification Map

| Req ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|--------|------|------|-------------|-----------|-------------------|-------------|--------|
| CONT-00 | 01 | 1 | 32 flujos tienen path a Alegra | manual | Review coverage matrix | Deliverable is document | ⬜ pending |
| CONT-01 | 01 | 1 | Proveedor extraido activa reglas | integration | `python backend/run_smoke_test.py` (T01-T04) | ✅ | ⬜ pending |
| CONT-06 | 02 | 2 | 20/20 tests pasan con IDs reales | smoke | `python backend/run_smoke_test.py` | ✅ | ⬜ pending |
| CONT-03 | 03 | 3 | Reintento no crea duplicado | integration | T13 smoke test (POST nomina → 409) | ✅ | ⬜ pending |
| CONT-04 | 03 | 3 | Webhook fallido → DLQ + retry | integration | `python backend/tests/test_dead_letter_queue.py` | ❌ W0 | ⬜ pending |
| CONT-05 | 03 | 3 | Cache invalida inmediatamente | unit | `python backend/tests/test_cache_invalidation.py` | ❌ W0 | ⬜ pending |
| CONT-02 | 04 | 3 | Sistema funciona tras decomposicion | smoke | `python backend/run_smoke_test.py` (20/20) | ✅ | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `backend/tests/test_dead_letter_queue.py` — verify insert into DLQ when handler fails, and retry job processes pending items (CONT-04)
- [ ] `backend/tests/test_cache_invalidation.py` — verify `_cache` empties immediately after `emit_event` with registered event type (CONT-05)

*No pytest configured — Wave 0 tests can be simple scripts following the existing smoke test pattern.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| 32 accounting flows have path to Alegra | CONT-00 | Deliverable is a coverage matrix document | Review `flujos_cobertura_matrix.md` — all 32 flows must have status Funcional, Parcial, or No implementado |

---

## Validation Sign-Off

- [x] All tasks have automated verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references (CONT-04, CONT-05)
- [x] No watch-mode flags
- [x] Feedback latency < 60s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** pending

---

*Phase: 01-contador-core*
*Validation strategy created: 2026-03-24*
