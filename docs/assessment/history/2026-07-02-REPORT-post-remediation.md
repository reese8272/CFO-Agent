# PERSONAL CFO — Production Assessment (post-remediation)

**Date:** 2026-07-02  ·  **Commit:** main @ Phase 6  ·  **App LOC:** ~10k  ·  **Tests:** 172 passed / 4 skipped (local + CI)

## VERDICT: PRODUCTION-READY — YES (Road A)

Every **BLOCKER and SEV1** from the 2026-07-02 baseline is **Fixed** or a **documented Road-A/Road-B
deferral**. The one live BLOCKER (disclaimer drop) is fixed with a structural test; the SEV1 cluster
(no rate limiting, no LLM timeout, blocking I/O on the loop, single-specialist routing, duplicated
proposals, missing indexes, key rotation, secrets-in-image) is all closed across Phases 0–6, verified
locally, in CI, and live. The remaining open items are **SEV2/cosmetic** (a NULL 401k placeholder, an
un-audited derived-snapshot write, two dead docstring classes) plus the explicit Road-A deferrals
(list pagination → 4b, response models + plaid-encryption → 5b, tenant isolation → Road B). Per the
roadmap finish-line definition — *zero BLOCKER/SEV1 open; scale axes ✅/⚠️-with-documented-defer;
tenant isolation the only expected ⚠️* — this meets **YES (Road A)**.

---

## Layer 0 — deterministic gates (from _machine.json)
| Gate | Baseline (2026-07-02) | Now | Status |
|---|---|---|---|
| ruff | 32 | **0** | ✅ |
| mypy | 154 | 152 | ⚠️ (permissive ceiling; ratchet later) |
| bandit | 0 / 0 | 0 / 0 | ✅ |
| pip-audit (`requirements.txt`) | 7 CVE'd deps | **0** | ✅ |
| coverage | CI-only | CI-only | ⚠️ (unchanged; local env can't run) |

## Layer 1 — remediation register (by module)
| Module | BLOCKER/SEV1 status | Verdict |
|---|---|---|
| agent | BLOCKER disclaimer ✅ · routing fan-out ✅ · reducer no-dup ✅ · coach guard ✅ · tenant DEFERRED(Road B) | PASS |
| _root_infra | .dockerignore ✅ · LLM timeout ✅ · MultiFernet ✅ · /docs gate ✅ · graceful shutdown ✅ · timing-oracle ✅ · Redis limiter ✅ · 7 CVE deps ✅ | PASS (10/10) |
| routers | LLM rate limits ✅ · blocking fetch off-loop ✅ · token log + caching ✅ · upload 413/422 ✅ · digest leak ✅ · pagination DEFERRED(4b) · response_model DEFERRED(5b) | PASS |
| vault | 5 missing indexes ✅ · `_to_monthly` unified ✅ · HSA family ✅ · Decimal-jsonb (non-issue) ✅ · plaid-enc DEFERRED(5b) · tenant DEFERRED(Road B) · k401 NULL placeholder + snapshot-audit (SEV2 open) | PASS |
| integrations | blocking fetch off-loop ✅ · yfinance deadline ✅ · CSV row/size caps ✅ · Session pool ✅ · OFX defusedxml DEFERRED(Road B) | PASS |
| worker | misfire/coalesce ✅ · digest wait_for ✅ · httpx singleton ✅ · multi-replica idempotency DEFERRED(Road B) | PASS (single-container) |
| scenarios | negative-money validation ✅ | PASS |
| memory | FK + sort indexes ✅ · tenant DEFERRED(Road B) · 2 dead docstring classes (cosmetic open) | PASS |

Open (non-blocking) SEV2/cosmetic: `financial_snapshot.k401_match_capture_pct` (documented NULL
placeholder), derived-snapshot write not audit-logged (likely deliberate exemption), two dead
docstring-only classes in `memory/retrieval.py`.

## Layer 2 — scale checklist (A–I)
| Axis | Baseline | Now | Evidence |
|---|---|---|---|
| A Pool math | ⚠️ | ⚠️ | `pool_recycle=1800` added, single replica documented; needs load evidence |
| B Async loop hygiene | ❌ | ✅ | `fetch_price_async` (to_thread + wait_for); CSV/OFX parse off-loop |
| C Job idempotency | ❌ | ⚠️ | misfire_grace/coalesce/timeout added; multi-replica idempotency deferred (single-container) |
| D Tenant isolation | ⚠️ | ⚠️ | **the one expected ⚠️** — documented Road-A single-user defer (DECISIONS 2026-07-02) |
| E Backpressure | ❌ | ✅ | Anthropic `timeout`, yfinance `wait_for`, digest `wait_for` |
| F Rate limit/quota | ❌ | ✅ | `@limiter.limit` on all LLM routes, Redis-backed store (per-tenant quota = Road B) |
| G Observability | ⚠️ | ⚠️ | token usage logged everywhere incl. intake; Sentry/metrics on the backlog |
| H Migration/index safety | ❌ | ✅ | 5 indexes added, `SET LOCAL lock_timeout`, plain create_index on tiny tables |
| I Secrets/deletion | ❌ | ✅ | `.dockerignore`, `MultiFernet` rotation, `/docs` gated in prod, graceful shutdown (erasure endpoint = Road B) |

## Diff vs baseline (2026-07-02 first report)
- **Fixed:** the BLOCKER (disclaimer) + ~20 SEV1s across all 8 modules; ruff 32→0; 7 CVE'd deps→0; scale axes B/E/F/H/I ❌→✅.
- **New:** none (no regressions; test count 155→172).
- **Regressed:** none.
- **Still open (by design):** tenant isolation (Road B), list pagination (4b), response models + plaid-encryption (5b), OFX defusedxml (Road B), multi-replica digest idempotency (Road B), + 3 SEV2/cosmetic items.

## Operational note
Deploy reliability on the small ARM VM: a rollout can transiently OOM-kill the app (502) —
recover with a re-run; prevent with VM swap (see `docs/DEPLOYMENT.md §7.1`, ISSUE-2026-07-02-02).

## Bottom line
**PRODUCTION-READY: YES (Road A).** The portfolio/single-user finish line is met. Reaching Road B
(real second users) still requires the full Pre-GA block — tenant isolation being the headline.
