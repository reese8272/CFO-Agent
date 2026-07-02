# PRODUCTION ROADMAP — path to "100% production" (Road A: portfolio / single-user)

> Generated from the 2026-07-02 production assessment (`docs/assessment/REPORT.md`).
> **Scope: Road A** — public code + self-hosted single-user. Multi-tenant isolation is
> explicitly OUT of scope here and tracked as the Road-B backlog at the bottom (see also
> `docs/DECISIONS.md` 2026-07-02 entry).
>
> Sequencing rule: **risk-first, then dependency order.** Ship one phase at a time through the
> CLAUDE.md Issue Workflow (Check → Approve → Build → Review). Re-run `/assess` after each phase;
> the REPORT diff should show findings moving to "Fixed" with nothing regressed.
>
> This roadmap **supersedes and expands the old Issue #28** (P2 hardening) — its five items are
> absorbed into Phases 2–5 below.

Finish line for Road A: **`/assess` returns PRODUCTION-READY — YES (Road A)** — i.e. zero
BLOCKER/SEV1 open, scale axes A–I ✅/⚠️-with-documented-defer, and the deferred tenant-isolation
row is the only ⚠️ remaining, explicitly logged.

---

## Phase 0 — Baseline hygiene (mechanical, unblocks clean signal)  ·  ~½ day
*No behavior change; makes every later diff readable and the repo safe to publish.*

- [ ] `ruff check --fix` (clears 27 of 32; hand-fix the 4 F841 unused locals + 2 F541).
      Silence the F821 false positive in `vault/financial_snapshot.py:32` via a
      `TYPE_CHECKING` import (it is NOT a runtime bug).
- [ ] Add `.dockerignore` (`.env`, `.env.*`, `!.env.example`, `.git`, `__pycache__`, `tests`,
      `docs`, `*.pyc`, `*.png`). Confirm with `docker history` that no env/git layer ships.
- [ ] Bump the 7 CVE'd pinned deps and re-run CI: `pyjwt`, `cryptography`, `starlette`,
      `python-multipart`, `requests`, `python-dotenv`, `pytest`. Pin with `==`; run the full
      suite; log any accepted-risk CVE in `docs/DECISIONS.md`.
- [ ] Re-baseline Layer 0 honestly: `run_layer0.py --update-baseline`, then set the ruff gate to
      0 and record the current mypy count as the ceiling to ratchet down (Phase 7).
- **Accept:** ruff 0, CI green on bumped deps, image carries no `.env`/`.git`, baselines committed.

## Phase 1 — The BLOCKER: restore the disclaimer invariant  ·  ships ALONE  ·  ~½ day
*Nothing else ships until this is green. It is the one compliance defect that exists at any user count.*

- [ ] `agent/nodes/synthesizer.py:83` — `needs = result.get("requires_disclaimer") or
      any(p["requires_disclaimer"] for p in state.get("proposals", []))`;
      `disclaimer = get_disclaimer() if needs else None`.
- [ ] Add the structural enforcement test `disclaimer.py`'s docstring already promises: any turn
      whose proposals include a `requires_disclaimer=True` node (e.g. `tax_optimizer`) MUST carry
      a non-null disclaimer in the final synthesized output. Add to `tests/eval/`.
- **Accept:** disclaimer test green; a tax/Roth turn always renders the disclaimer even if the
      final LLM returns `requires_disclaimer=false`.

## Phase 2 — LLM surface safety: rate limit + timeout + caching  ·  ~1 day
*Absorbs Issue #28 P2-1 (rate limit) + P2-2 (LLM timeout). Closes scale axes E + F.*

- [ ] `@limiter.limit(...)` + `request: Request` on every LLM/expensive route: `/chat` (10/min),
      `/intake/interview` (20/min), `/intake/extract` (6/min), `/digest/run-now` (3/hour).
- [ ] Move the limiter to the shared Redis store: `Limiter(..., storage_uri=settings.redis_url)`
      (in-memory currently fails open per-replica).
- [ ] Wire the timeout: `AsyncAnthropic(api_key=..., timeout=settings.llm_timeout_seconds,
      max_retries=2)` in `clients.py`.
- [ ] `routers/intake.py` — log `response.usage` after both `.create` calls; add
      `cache_control: ephemeral` to the static `_INTERVIEW_SYSTEM` block and the `_EXTRACT_TOOL`
      prefix (CLAUDE.md mandates caching + token logging on every call).
- [ ] Add `anthropic_model_fast` / `anthropic_model_smart` to `Settings` + `.env.example`; read
      them in the 6 agent nodes and `intake.py` instead of hardcoded ids.
- **Accept:** a scripted burst on `/chat` returns 429 past the limit; a forced slow Anthropic
      response aborts at `llm_timeout_seconds`; intake logs `tokens in/out`; limiter survives a
      restart (Redis-backed).

## Phase 3 — Async hygiene & backpressure  ·  ~1 day
*Closes scale axis B; hardens the public surface against slow/hostile input.*

- [ ] `routers/holdings.py:95,118` — `await asyncio.to_thread(fetch_price, ...)` (mirror the
      correct RentCast call at `vault.py:512`).
- [ ] `integrations/market_data.py:42` — bound yfinance with `asyncio.wait_for(..., timeout=10)`;
      add `timeout=` to the Alpha Vantage `requests.get`; use a module-level `requests.Session()`.
- [ ] `routers/imports.py` + `integrations/csv_import.py` — enforce a max upload size (reject
      > ~10 MB), cap parsed rows, run parse via `asyncio.to_thread`, wrap in
      `try/except ValueError → HTTPException(422)`; confirm ofxtools disables XML entity
      expansion or pre-parse with `defusedxml`.
- [ ] `worker/cron.py` — `misfire_grace_time=3600, coalesce=True`; wrap the digest run in
      `asyncio.wait_for(..., 300)`; hoist the httpx ping client to a module singleton.
- **Accept:** concurrent `/holdings/refresh` no longer stalls other requests (loop stays
      responsive under a load probe); an oversized/garbage upload returns 422, not 500.

## Phase 4 — Data layer: indexes, pagination, money correctness  ·  ~1–1.5 days
*Absorbs Issue #28 P2-3 (FK indexes) + P2-5 (list pagination). Closes scale axis H + a real math bug.*

> **Deploy-pipeline prerequisites (this phase ships the first migration since the pipeline was
> found fragile; see ISSUE-2026-07-02-01):** the Phase 0/1 deploy timed out at the Alembic step
> because the whole SSH command must finish inside `command_timeout: 10m` and `alembic current`
> is slow (~2min). Phase 2 added `SET LOCAL lock_timeout='30s'` to `migrations/env.py` (a blocked
> migration now fails fast). Still to do here: (1) give the migration its own SSH step / raise
> `command_timeout`; (2) `CREATE INDEX CONCURRENTLY` **cannot** run inside
> `context.begin_transaction()` — add an autocommit/isolation escape hatch in `env.py` (or run the
> index DDL non-transactionally) or the migration will fail outright.

- [ ] One Alembic migration, `CREATE INDEX CONCURRENTLY` (outside a txn) for the 10 vault FKs +
      `memory.Message.conversation_id` + `Pattern.detected_at` + `FinancialSnapshot.computed_at`.
- [ ] Add `limit: int = Query(100, le=500)` (or a hard `.limit(500)` in the crud layer) to the
      17 vault list endpoints + `holdings`, `wealth`, `imports` lists.
- [ ] **Unify `_to_monthly`** — extract one case-folded `to_monthly(amount, cadence)` into
      `vault/_money.py`; delete the 3 divergent copies (4.333 vs 4.33; missing cadences). Add a
      test that all cadences agree across snapshot + position math.
- [ ] `financial_snapshot.py` — implement or remove `k401_match_capture_pct` (currently always
      NULL); select `HSA_LIMIT_FAMILY_2026` for family plans; coerce top-level `Decimal` in
      `analysis_jsonb` before flush (confirm/add the store-round-trip test).
- [ ] `scenarios/models.py` — `@field_validator` rejecting negative money fields (→ 422).
- [ ] `vault/models.py:34` — encrypt `Account.plaid_account_id` (or store last-4/opaque ref).
- **Accept:** migration runs online (no long lock); list endpoints cap output; `_to_monthly`
      agreement test green; snapshot stores end-to-end without a Decimal TypeError.

## Phase 5 — Prod hardening & API surface  ·  ~1 day
*Absorbs Issue #28 P2-4 (graceful shutdown) + P3 items. Closes scale axis I.*

- [ ] `main.py` — gate `/docs`,`/redoc`,`/openapi.json` behind `env == "production"`.
- [ ] uvicorn CMD (Dockerfile + compose) — `--timeout-graceful-shutdown 30`.
- [ ] `crypto.py` — `MultiFernet` from `VAULT_ENCRYPTION_KEYS` (csv): first key encrypts, all
      decrypt. Document the rotation runbook in `docs/DEPLOYMENT.md` and exercise it once.
- [ ] `auth.py` — fix the login timing oracle (always bcrypt a dummy hash when `user is None`).
- [ ] `rate_limit`/`db` — `pool_recycle=1800`; document the pool×replicas ≤ `max_connections`
      math in `docs/DEPLOYMENT.md` (single replica for Road A, but state it).
- [ ] `routers/wealth.py`, `intake.py:167/440`, `holdings.py:82` — declare `response_model` with
      the CONTRACTS.md §3 shapes (no bare dicts).
- [ ] `routers/digest.py:30` — stop leaking the raw SMTP exception; return a fixed detail, log
      server-side. Add security-response-headers middleware.
- **Accept:** `/docs` 404s in prod; redeploy drains in-flight requests; a key-rotation dry-run
      decrypts old + new; all endpoints return validated models.

## Phase 6 — Agent correctness (design)  ·  ~1–1.5 days
*The agent works today but doesn't do what its design says — fix before showcasing it.*

- [ ] `agent/graph.py` — `add_conditional_edges` with a **list** return so every routed specialist
      fires (today only one ever does); eval asserting a "both" turn yields ≥2 proposals.
- [ ] `agent/nodes/coach.py` + `state.py` — stop the additive-reducer duplication (Coach appends a
      second enriched copy); write to a non-additive key or a replace-by-`node` reducer; test
      `len(proposals) == specialist count`.
- [ ] `coach.py:104-115` — guard the `next(... tool_use)` extraction with a fallback + raise
      `MAX_TOKENS` so a truncated array output can't 500.
- [ ] `tax_optimizer.py:68` — derive the marginal bracket (or make it a year-stamped
      `principles.py` constant); drop the hardcoded 22%.
- [ ] Clamp LLM `leverage_score` to 0.0–1.0 in the 4 nodes that don't; drop the legacy
      `anthropic-beta` prompt-caching header (GA now).
- **Accept:** eval harness green; a multi-topic turn produces multiple specialist proposals with
      one committed synthesis; no duplicate proposals reach the Synthesizer.

## Phase 7 — Portfolio polish & close  ·  ~1 day
*Make it read like a senior engineer's project, then prove the finish line.*

- [ ] Public-facing `README.md`: what it is + the mandatory disclaimer, architecture diagram
      (FastAPI + LangGraph agent + Postgres/Redis + Cloudflare Tunnel), screenshots, "how it's
      built" (prompt caching, Fernet-at-rest, eval harness), and an explicit
      "single-user v1 / multi-tenant is future work" note (turns the deferred scope into a
      *design decision you can defend in an interview*).
- [ ] Pull the CI coverage artifact; confirm the disclaimer path + graph routing are covered;
      fill the highest-value gaps (target the load-bearing paths, not a coverage number — 80/20).
- [ ] Ratchet the mypy backlog down from 154 toward 0 (or a defensible floor) and tighten the
      Layer 0 baseline.
- [ ] Re-run `/assess` → expect **PRODUCTION-READY — YES (Road A)**; snapshot the diff.
- [ ] `/close-out`, update `docs/PROJECT_STATE.md`, close the GitHub issues.

---

## Deferred to Road B (multi-tenant SaaS) — do NOT do for Road A
Tracked here so the scope line is explicit and defensible (see `docs/DECISIONS.md`, CLAUDE.md
Pre-GA block). Each becomes a BLOCKER only if a real second user is invited:
- `user_id` column on every tenant-scoped table + owner filter on every query (best: Postgres RLS
  with `SET app.current_tenant`); standing 2-tenant regression test.
- Per-user rate limits + usage quotas (Road A's limits are per-IP / global).
- OAuth2 multi-tenant auth replacing single-user JWT.
- ToS + Privacy Policy; account-deletion / right-to-erasure endpoint (idempotent).
- Key-rotation runbook exercised on real tenant data; SOC2-baseline audit logging if billing.
- Re-evaluate the "CFO with a point of view" stance for third-party liability.

## Suggested GitHub issue mapping
| Phase | Issue | Old #28 items absorbed |
|---|---|---|
| 0 | Baseline hygiene (ruff/deps/.dockerignore/baseline) | — |
| 1 | Disclaimer invariant (BLOCKER) | — |
| 2 | LLM surface safety | P2-1, P2-2 |
| 3 | Async hygiene & backpressure | (P3-1 error states adjacent) |
| 4 | Data layer: indexes + pagination + money math | P2-3, P2-5 |
| 5 | Prod hardening & API surface | P2-4, P3-2 |
| 6 | Agent correctness | P3-3 (model id) |
| 7 | Portfolio polish & close | — |
