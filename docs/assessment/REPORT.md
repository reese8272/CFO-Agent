# PERSONAL CFO — Production Assessment

**Date:** 2026-07-02  ·  **Commit:** 758852f  ·  **App LOC:** 10,106 (13,412 incl. tests)  ·  **Tests:** 155 passed / 2 skipped (CI; local pytest blocked by env)

## VERDICT: PRODUCTION-READY — NO

One **live BLOCKER** ships today regardless of user count: the Synthesizer can silently drop the
mandatory financial disclaimer on tax/investment output (`agent/nodes/synthesizer.py:83`), which
violates the frozen hard rule in `CONTRACTS.md §2` and the CLAUDE.md domain rule — in a finance
tool this is a compliance defect, not a nice-to-have. On top of that, the LLM routes (`/chat`,
`/intake/interview|extract`, `/digest/run-now`) ship with **no rate limiting** despite slowapi
being wired, the Anthropic client has **no timeout**, and stock-price refresh makes **blocking HTTP
calls on the event loop** — each a SEV1 that bites under any real concurrency.

**Scope note (decides ~8 of the SEV1s):** the app is a correct, well-built *single-user v1* today.
Whether the tenant-isolation gaps (no `user_id` column anywhere; no query filters by owner across
`vault/`, `memory/`, and the agent's Tracker/Alert queries) are **BLOCKERs or deferred pre-GA
items depends on what "public" means** — a self-hosted single-user portfolio piece vs. a
multi-tenant SaaS with real second users. See "Two roads" at the bottom.

---

## Layer 0 — deterministic gates (from _machine.json)
| Gate | Result | Baseline | Status |
|---|---|---|---|
| ruff | 32 issues | 0 | ❌ |
| mypy | 154 errors | 1,000,000 (permissive floor) | ⚠️ (never tightened) |
| coverage | skipped (local env: starlette pin) | 0.0 | ⚠️ (CI-only) |
| bandit | high 0 / med 0 | high 0 / med 0 | ✅ |
| pip-audit (env) | 72 vulns | — | ⚠️ (whole env; see below) |
| pip-audit (`requirements.txt`) | **7 pinned deps with real CVEs** | 0 | ❌ |

**ruff 32:** 25× unused import (F401, auto-fixable), 4× unused local (F841), 2× f-string-no-
placeholder (F541), 1× F821 `Undefined name FinancialSnapshot` — **the F821 is a linter false
positive** (`from __future__ import annotations` makes it a never-evaluated string), not a runtime
NameError. `ruff check --fix` clears 27 of 32 mechanically.

**pip-audit on pinned deps — real, load-bearing for a finance app:**
- `pyjwt 2.10.1` (auth token layer) — 8+ advisories
- `cryptography 44.0.0` (Fernet vault encryption) — 5 advisories incl. CVE-2024-12797
- `starlette 0.41.3` — 8 advisories · `python-multipart 0.0.20` (file upload) — 6
- `requests 2.32.3` — 2 · `python-dotenv 1.0.1` — 1 · `pytest 8.3.4` — 1

Top untested load-bearing code (coverage not measurable locally — **must be pulled from the CI
coverage artifact** to complete this row): the disclaimer-enforcement path and the agent graph
routing are the highest-value gaps to confirm coverage on given the findings below.

## Layer 1 — module register (ranked)
| Sev | Module | Location | Issue | Backed fix |
|---|---|---|---|---|
| **BLOCKER** | agent | `nodes/synthesizer.py:83` | Disclaimer set only from the final LLM's `requires_disclaimer`; ignores proposals' flag (`tax_optimizer` always True) → disclaimer silently dropped on tax/investment output. Violates CONTRACTS.md §2. | `needs = result.get("requires_disclaimer") or any(p["requires_disclaimer"] for p in state.get("proposals", []))`; add the structural test disclaimer.py already promises. |
| SEV1 | agent | `graph.py:85-97` | `_route_from_analyzer` returns one node → only ONE specialist ever fires; `operator.add` fan-out + `turn_kind="both"` are dead code. | `add_conditional_edges` with a **list** return so every routed specialist runs; eval asserting a "both" turn yields ≥2 proposals. |
| SEV1 | agent | `nodes/coach.py:136` + `state.py:56` | Coach means to *replace* proposals but `Annotated[list, operator.add]` *appends* → Synthesizer sees duplicate (raw+enriched) proposals. | Coach writes to a separate non-additive key, or custom reducer replacing by `node`; test `len(proposals)` == specialist count. |
| SEV1 | routers | `chat.py:31`, `intake.py:678/711`, `digest.py:21` | LLM/expensive routes have **no `@limiter.limit`** → unbounded LLM spend / DoS. | `@limiter.limit("10/minute")` on `/chat`, `20/min` interview, `6/min` extract, `3/hour` digest; add `request: Request` param. |
| SEV1 | routers/integrations | `holdings.py:95,118` → `market_data.py:42,56` | `fetch_price` (blocking `requests`+`yfinance`) called on the event loop in a per-ticker loop → stalls all concurrent requests. | `await asyncio.to_thread(fetch_price, ...)` (mirror the correct RentCast call at `vault.py:512`). |
| SEV1 | integrations | `market_data.py:42` | `yf.Ticker().fast_info` HTTP fetch with **no timeout** → indefinite hang on slow upstream. | Wrap in `asyncio.to_thread` + outer `asyncio.wait_for(timeout=10)`, or direct `requests.get(timeout=...)`. |
| SEV1 | _root_infra | `clients.py:56` | `AsyncAnthropic()` built with **no timeout** (inherits 600s default); `config.llm_timeout_seconds=120` exists but is never wired. | `AsyncAnthropic(api_key=..., timeout=get_settings().llm_timeout_seconds, max_retries=2)`. |
| SEV1 | _root_infra | `crypto.py:26-30` | Single-key `Fernet`; no `MultiFernet` → the key-rotation runbook THREAT_MODEL promises is operationally impossible. | Accept `VAULT_ENCRYPTION_KEYS` (csv); `MultiFernet([Fernet(k) for k in keys])` — first encrypts, all decrypt. |
| SEV1 | _root_infra | `Dockerfile:29` (no `.dockerignore`) | `COPY . .` bakes `.env` (if present at local build), `.git/`, `tests/`, `docs/` into the pushed image. CI's clean checkout is safe; local `docker build` is not. | Add `.dockerignore`: `.env`, `.env.*`, `!.env.example`, `.git`, `__pycache__`, `tests`, `docs`, `*.pyc`. |
| SEV1 | routers | `intake.py:695,724` | Direct Anthropic calls: **token usage not logged** + **no prompt caching** despite large static system/tool blocks reused every turn. Violates CLAUDE.md "caching mandatory / log tokens every call". | Log `r.usage`; add `cache_control: ephemeral` to the static system + tool prefix. |
| SEV1 | vault | `models.py` (10 FK cols) | 10 foreign-key columns, **zero indexed** (`Card.account_id`, `Holdings.account_id`, `SideIncome*.income_stream_id`, `Transaction.*`, …) → seq-scans on filtered lists + lock escalation on parent DELETE. | One Alembic migration, `CREATE INDEX CONCURRENTLY` per FK. |
| SEV1 | vault | `financial_snapshot.py:327` vs `income_position.py:173` vs `wealth_position.py:221` | `_to_monthly` defined **3× with divergent constants** (4.333 vs 4.33; missing `semimonthly`/`annually` in one) → snapshot totals disagree with the ladder math they're built from. | Extract one case-folded `to_monthly()` into `vault/_money.py`; import in all three. |
| SEV1 | worker | `cron.py:44` | Weekly digest on in-process scheduler with **no idempotency guard / leader election** → N replicas = N duplicate emails per user. Safe only on the documented single container. | `processed_jobs(job_key UNIQUE)` insert keyed `digest:<ISO-week>` + send only if inserted; or Redis `SET NX` lease. |
| SEV1 (latent→BLOCKER at 2nd user) | vault / memory / agent / routers | `vault/models.py`, `memory/models.py`, `agent/nodes/tracker.py,alert.py`, all `crud.list_*` | **No `user_id` column anywhere; no query filters by owner.** `compute_*` accept `user_id` and silently ignore it (a trap that reads as "scoped"). Correct for single-user v1; a cross-tenant leak the instant a 2nd user exists. | Pre-GA: add `user_id` FK to every tenant table + `.where(Model.user_id==user.id)` on every query + a 2-tenant regression test. |
| SEV2 | _root_infra | `rate_limit.py:8` | slowapi default **in-memory** store → per-process, fails open on restart, not fleet-wide. | `storage_uri=get_settings().redis_url` (Redis already a dep). |
| SEV2 | _root_infra | `auth.py:113-118` | Login is a username-enumeration timing oracle (bcrypt skipped when user absent). | Always bcrypt-verify a fixed dummy hash when `user is None`. |
| SEV2 | _root_infra | `main.py:59-64` | `/docs`,`/redoc`,`/openapi.json` exposed in prod (no env gate). | `docs_url=None if prod else "/docs"` (+ redoc/openapi). |
| SEV2 | _root_infra | `main.py` / Dockerfile CMD | uvicorn has no `--timeout-graceful-shutdown` → in-flight LLM calls killed on redeploy. | Append `--timeout-graceful-shutdown 30`. |
| SEV2 | routers | `vault.py` (17 GETs), `holdings.py`, `wealth.py`, `imports.py` | List endpoints do unbounded `select().all()` → unbounded fetch + HTMX render. | `limit: int = Query(100, le=500)` threaded into `crud.list_*`, or hard `.limit(500)` in crud. |
| SEV2 | routers | `wealth.py:27-47`, `intake.py:167,440`, `holdings.py:82` | Endpoints return bare `dict` — **no response Pydantic model** (CONTRACTS.md §3 specifies shapes). | Declare `response_model` with the frozen shapes. |
| SEV2 | routers | `imports.py:26` | Untrusted upload parsed with no size cap + unhandled parse errors → 500 / unbounded memory. | `try/except ValueError→422`; enforce max upload size; parse via `asyncio.to_thread`. |
| SEV2 | integrations | `csv_import.py:71-142` | CSV/OFX parse of untrusted files: unbounded rows in memory + sync on loop; OFX XML entity-expansion (billion-laughs) surface. | Cap upload size + row count; `asyncio.to_thread`; confirm/`defusedxml` for OFX. |
| SEV2 | vault | `models.py:34` | `Account.plaid_account_id` stored **plaintext** (THREAT_MODEL §4 wants identifiers redacted). | `EncryptedString` column or store last-4/opaque ref. |
| SEV2 | vault | `financial_snapshot.py:119,133-138` | `k401_match_capture_pct` never computed (always NULL); HSA always divides by SINGLE limit → family user overstated ~1.9×. | Implement/remove the 401k field; add coverage-tier + select family limit. |
| SEV2 | vault | `financial_snapshot.py:54` | `analysis_jsonb` holds raw top-level `Decimal` → possible `TypeError` at flush if EncryptedJSON uses stock `json.dumps`. (needs-runtime-confirmation) | Coerce top-level Decimals to float/str; end-to-end store test. |
| SEV2 | agent | `nodes/tax_optimizer.py:68` | Hardcoded 22% bracket in quarterly-estimate; not year-stamped / not from `principles.py`. | Derive bracket from income or make a year-stamped constant; cite "for 2026…". |
| SEV2 | agent | 6 nodes | Model ids hardcoded across 6 files; `config.py` has no `anthropic_model` field. | Add `anthropic_model_fast/_smart` to Settings; read in nodes. |
| SEV2 | agent | `nodes/coach.py:104-115` | Fragile `next(b … tool_use)` extraction under `MAX_TOKENS=512`: truncation → malformed input / `StopIteration` → unhandled 500. | Guard with `next((...), None)` + fallback; raise Coach MAX_TOKENS. |
| SEV2 | memory | `models.py:32`, `retrieval.py:72-110` | `Message.conversation_id` FK unindexed (seq-scan on chat restore); per-turn retrieval hits unindexed sort/filter cols. | `index=True` on the FK + `Pattern.detected_at` / `FinancialSnapshot.computed_at`; partial index on active decisions. |
| SEV2 | scenarios | `models.py:14-25` | Money fields accept negatives with no validation → nonsensical projections instead of 422. | `@field_validator(>=0)` on amounts; move `target>0` into a validator. |
| SEV2 | worker | `cron.py:45-53,19-24` | No `misfire_grace_time`/`coalesce` (silent weekly skip on >1s stall); digest awaited with no timeout. | `misfire_grace_time=3600, coalesce=True`; `asyncio.wait_for(..., 300)`. |
| SEV2 | routers | `digest.py:30` | `detail=f"...{exc}"` leaks raw SMTP exception to client. | Fixed `detail="Digest send failed"`; log `exc` server-side. |
| cleanup | many | — | 32 ruff issues (25 unused imports auto-fixable), CRUD/HTMX/`_to_monthly` DRY, unclamped `leverage_score`, legacy `anthropic-beta` header, bare `except Exception`, untyped signatures feeding 154 mypy errors. | `ruff check --fix`; then chip the mypy backlog toward 0 and re-baseline. |

Module verdicts: **agent: has BLOCKER** · routers: NEEDS-WORK · vault: NEEDS-WORK · memory: NEEDS-WORK · scenarios: NEEDS-WORK · worker: NEEDS-WORK · integrations: NEEDS-WORK · _root_infra: NEEDS-WORK

## Layer 2 — scale checklist (scale-checklist.md)
| Axis | Status | Evidence |
|---|---|---|
| A Pool math | ⚠️ | `pool_size=5, max_overflow=5` pinned, `pool_pre_ping=True` (good); no `pool_recycle`, no PgBouncer, math vs replicas undocumented. Fine at single replica. (needs load evidence) |
| B Async loop hygiene | ❌ | Blocking `requests`/`yfinance` `fetch_price` on the loop from holdings routes; sync CSV/OFX parse on the loop. |
| C Job idempotency | ❌ | Weekly digest has no idempotency key / leader election — double-sends under 2+ replicas. |
| D Tenant isolation | ⚠️/❌ | No `user_id` column and no owner filter anywhere. By-design single-user v1; the gating axis for "public". |
| E Backpressure | ❌ | No Anthropic timeout; yfinance no timeout; digest job no timeout. Timeouts on external calls are largely absent. |
| F Rate limit / quota | ❌ | In-memory limiter (fails open per-replica); LLM routes unguarded; no per-user quota. |
| G Observability | ⚠️ | Token usage logged in `agent/` but not in `intake.py`; no Sentry/error tracking; no metrics (p50/p95/p99, queue depth). `/health` reports degraded=503 (good). |
| H Migration/index safety | ⚠️/❌ | 10 unindexed FKs + memory FK; fix must ship as `CREATE INDEX CONCURRENTLY`. No pgvector in use. Backups not restore-tested (per docs). |
| I Secrets / deletion | ❌ | No `.dockerignore` (secrets bakeable locally); no Fernet key rotation; `/docs` exposed in prod; no account-deletion/erasure endpoint. |

## Diff vs previous report
First assessment — no prior `REPORT.md`. All findings are new. This is the baseline; re-run
`/assess` after each remediation phase and this section will show Fixed / New / Regressed.

## Top 5 actions, in order
1. **Restore the disclaimer invariant (BLOCKER).** Fix `synthesizer.py:83` to OR-in every
   proposal's `requires_disclaimer`, and land the structural enforcement test. Nothing else
   ships until this is green.
2. **Rate-limit + timeout the LLM surface.** `@limiter.limit` on `/chat`, `/intake/*`,
   `/digest/run-now`; wire `llm_timeout_seconds` into `AsyncAnthropic`; move limiter store to
   Redis. Closes the unbounded-spend / DoS and the 600s-hang exposure together.
3. **Get blocking I/O off the event loop.** `asyncio.to_thread` (+ `wait_for` deadline) around
   every `fetch_price` and the CSV/OFX parse; cap upload size. Closes scale axis B.
4. **Secrets & deps hygiene for a public repo.** Add `.dockerignore`; bump the 7 CVE'd pinned
   deps (`pyjwt`, `cryptography`, `starlette`, `python-multipart`, `requests`, `python-dotenv`,
   `pytest`) and re-run CI; gate `/docs` behind `env=production`; add `MultiFernet` key rotation.
5. **Index + math correctness pass.** One `CREATE INDEX CONCURRENTLY` migration for the 10 FKs +
   memory FK; unify `_to_monthly` into `vault/_money.py`; add `limit` caps to the 17 list
   endpoints; `ruff check --fix` and start chipping the 154 mypy errors toward a real baseline.

---

## Two roads (the scope decision that sets the real finish line)

**Road A — Portfolio / self-hosted single-user (public *code*, one operator).**
"100% production" = the register above minus the tenant-isolation row. The disclaimer BLOCKER,
rate-limiting, timeouts, async hygiene, secrets/deps hygiene, indexes, and correctness fixes are
all in scope. Tenant isolation stays a documented, deferred pre-GA item. Reachable in a focused
sprint; strongest résumé/LinkedIn artifact per unit effort.

**Road B — Multi-tenant SaaS (real second users).**
Everything in Road A **plus** the full `docs/CLAUDE.md` Pre-GA block becomes mandatory and the
tenant-isolation row promotes to a set of BLOCKERs: `user_id` on every table + owner filter on
every query + a standing 2-tenant regression test (best via Postgres RLS), per-user rate limits &
quotas, OAuth2 multi-tenant auth replacing single-user JWT, ToS/Privacy, account-deletion/erasure,
key-rotation runbook exercised. Substantially larger; a real product, not a portfolio piece.
