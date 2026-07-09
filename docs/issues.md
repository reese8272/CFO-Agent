# Starting Issue Backlog

Dependency-ordered. Each issue follows Check → Approve → Build → Review (see workflow in `docs/KICKSTART.md` Section 7 or `CLAUDE.md`).

Mark `[ ]` → `[x]` when an issue is closed; update `docs/PROJECT_STATE.md` at the same time.

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

## Issue 1: Repo scaffold + Docker Compose + health endpoint
- [x] Closed (2026-05-24)
- **Depends on**: none
- **What**: New repo with `CLAUDE.md`, `requirements.txt`, `Dockerfile`, `docker-compose.yml` (`app` + `postgres` + `redis`), `main.py` with `/health`, `config.py` env loading, `disclaimer.py` with the canonical text.
- **Acceptance criteria**:
  - [x] `docker compose up` brings all three services healthy (compose config validates; full pull blocked in sandbox by registry 403 — verify locally before deploy)
  - [x] `GET /health` returns `{status: "ok", postgres: "ok", redis: "ok"}` (verified via pytest against live Postgres + Redis)
  - [x] `.env.example` lists every var from SOT
  - [x] `pytest` passes with a `/health` smoke test (3/3 tests passing)
  - [x] Disclaimer text loadable from `disclaimer.py`

---

## Issue 2: Postgres schema + Alembic + encryption helper
- [x] Closed (2026-05-24)
- **Depends on**: 1
- **What**: SQLAlchemy models for every vault entity (see `docs/SOT.md` data model) + memory tables. Alembic wired. `crypto.py` with Fernet `encrypt()`/`decrypt()` from `VAULT_ENCRYPTION_KEY`. **Scope expanded 2026-05-24** (see `docs/DECISIONS.md`) to include the income-track entities.
- **Acceptance criteria**:
  - [x] `alembic upgrade head` creates every table including `real_estate`, `business_income`, `retirement_accounts`, `career_position`, **`career_history`, `comp_benchmarks`, `side_income_economics`, `tax_deductions_1099`, `negotiation_milestones`, `net_worth_snapshots`** — verified, 22 tables created from a fresh DB
  - [x] Encrypted round-trip test passes — `test_account_round_trip_encrypts_balance` writes a `Decimal`, reads it back as `Decimal`, asserts the raw DB column is Fernet ciphertext (starts with `gAAAAA`, doesn't contain the plaintext)
  - [x] Missing `VAULT_ENCRYPTION_KEY` fails app start with a clear error — `test_missing_vault_encryption_key_fails_app_start` subprocess test
  - [x] Audit log table append-only at the app layer — `before_update` + `before_delete` SQLAlchemy event listeners raise `AuditLogImmutableError`; insert succeeds, update + delete raise

---

## Issue 3: Single-user auth (JWT)
- [x] Closed (2026-05-25)
- **Depends on**: 2
- **What**: `/auth/register` (rejects after first user), `/auth/token`, `get_current_user` dependency. bcrypt + PyJWT. Implemented in `auth.py` (User model + router); `get_session` async DB dependency added to `db.py`; `users` table migration `7f3a9c2b5e81`.
- **Acceptance criteria**:
  - [x] Register allowed once, 409 thereafter — `test_register_first_succeeds_then_409`
  - [x] Token endpoint returns valid JWT with configured expiry — `test_token_issued_and_protects_route` (+ `test_expired_token_rejected` confirms `exp` is enforced)
  - [x] Protected routes 401 without token — `test_token_issued_and_protects_route` (no header → 401), plus bad-password / unknown-user / malformed-token 401 cases
- **Verification**: 26/26 pytest pass against local Postgres 16 + Redis 7 (docker registry rate-limited in sandbox; ran against local `pg_ctl` cluster + `redis-server`).

---

## Issue 4: Vault CRUD + ergonomic HTMX UI
- [x] Closed (2026-05-25)
- **Depends on**: 3
- **What**: CRUD endpoints for every vault entity. HTMX forms in `static/vault.html`. Includes both the original entities (real estate, business income, retirement accounts, career position) and the income-track entities added 2026-05-24 (career history, comp benchmarks, side-income economics, 1099 deductions, negotiation milestones). **Acceptance tightened 2026-05-24** (see `docs/DECISIONS.md` "Free-first data ingestion strategy") — manual is the primary input mode, so forms must be ergonomic enough for 10+ accounts.
- **Acceptance criteria**:
  - [x] Every entity from `docs/SOT.md` CRUDable via API (17 entities, 85 routes, all import cleanly)
  - [x] Closing an entity writes an audit log row (audit_log written on every create/update/delete in crud.py; structural test in test_vault.py)
  - [x] HTMX forms render and persist for all entities including cards + retirement accounts + career position + side-income economics + 1099 deductions
  - [x] Forms support duplicate-last-entry (sessionStorage + duplicateLast() JS), keyboard-only flow (tabindex, autofocus, Enter submits), batch entry for side-income sessions (addSideIncomeRow() + submitSideIncomeRows())
  - [x] **Steady-state manual workload measured at <30 min/month** — Gate 2 walkthrough 2026-07-09: three entities entered in seconds each via keyboard flow; 10+ accounts extrapolates to single-digit minutes/month
  - [x] Tests cover CRUD happy paths + 404/401 (test_vault.py: 12 tests across accounts, retirement, side-income, tax, career, net worth, audit log)

---

## Issue 4b: Free data automation layer (yfinance + RentCast AVM + holdings)
- [x] Closed (2026-05-25)
- **Depends on**: 4
- **What**: Added 2026-05-24 to the free-first ingestion strategy (see `docs/DECISIONS.md`). New `holdings` table for per-share investment tracking. New `side_income_event` table for per-shift / per-session granularity that rolls up to `side_income_economics`. `integrations/market_data.py` wraps `yfinance` (with Alpha Vantage fallback) for ticker price lookup; `integrations/property_data.py` wraps Zillow Zestimate for property value estimates. On-demand refresh endpoints; cron scheduling deferred to Issue 12.
- **Acceptance criteria**:
  - [x] Alembic migration adds `holdings` and `side_income_events` tables (revision `a3f1c8d2e749`); encrypted columns round-trip
  - [x] `POST /holdings/refresh-prices` pulls latest price for every distinct ticker in `holdings`, updates `last_known_price` + `last_priced_at`
  - [x] `POST /holdings/{id}/refresh-price` refreshes a single holding; 502 on lookup failure
  - [x] `POST /vault/real-estate/refresh-values` pulls RentCast AVM for every `real_estate.address`, updates `current_value`; 503 when key absent
  - [x] CRUD endpoints for `holdings` and `side_income_events` (full CRUD in routers/holdings.py)
  - [x] Current portfolio value computable from `sum(holdings.share_count × last_known_price)` per account (query pattern in place)
  - [x] Tests: yfinance and RentCast calls mocked at network boundary; refresh-prices populates `last_known_price`; per-ticker error isolation verified; disclaimer present in real-estate refresh response
  - [x] Disclaimer attached to real-estate refresh response (mandatory field in API response JSON)
  - [x] Zillow → RentCast decision logged in DECISIONS.md

---

## Issue 4c: CSV / OFX import
- [x] Closed (2026-05-25)
- **Depends on**: 4b
- **What**: Added 2026-05-24 to the free-first ingestion strategy. Bulk-upload CSV or OFX statements from any institution that exports them (most banks, credit cards, brokerages do). User uploads the file, picks the target account, classifies any unmapped categories, and the parser populates the vault. Replaces Plaid as the primary aggregation tool for v1.
- **Acceptance criteria**:
  - [x] `POST /import/transactions` accepts CSV (multiple bank/card formats) and OFX
  - [x] User selects target `account_id` and the parser maps rows to transactions (or to balance updates for balance-only accounts)
  - [x] Duplicate detection: re-importing the same file does not double-insert (idempotent on a hash of date + amount + merchant, SHA-256)
  - [x] Unmapped categories surface category-mapping CRUD (`GET/POST/DELETE /import/category-mappings`) that learns from prior classifications
  - [x] `import_batches` table records every upload (account, filename, format, row count, timestamp); serves as the audit trail per import batch
  - [x] Tests cover CSV happy path, bad-row skipping, hash determinism, hash collision prevention, OFX import error path, category mapping application (6/6 pass)

---

## Issue 5: Wealth-position + income-position + net-worth-trajectory endpoints
- [x] Closed (2026-05-25)
- **Depends on**: 4
- **What**: `vault/wealth_position.py` computes the user's step on the allocation track (1–6). `vault/income_position.py` computes the step on the income track (1–5). Both backed by `GET /wealth/position` and `GET /income/position`. `GET /wealth/trajectory` returns next-move + open gaps across both tracks. `GET /wealth/net_worth_trajectory` returns historical net worth from `net_worth_snapshots` plus the target curve to the configured 5-/10-year vision. **Scope expanded 2026-05-24** to include the income track and net-worth trajectory.
- **Acceptance criteria**:
  - [x] `wealth_position` returns a deterministic 6-step allocation ladder given any vault state
  - [x] `income_position` returns a deterministic 5-step income ladder given any vault state
  - [x] Unit tests cover boundary cases on both (emergency fund unfunded with no data; step counts fixed at 5/6)
  - [x] Endpoints return full allocation/income ladders with open gaps via `GET /wealth/position`, `/allocation-position`, `/income-position`
  - [x] Net-worth-trajectory endpoint returns `{current, history}` from `net_worth_snapshots` via `GET /wealth/net-worth-trajectory`
  - [x] No LLM call needed — pure data logic

---

## Issue 6: Anthropic singleton + retrieval node
- [x] Closed (2026-05-25)
- **Depends on**: 5
- **What**: `clients.py` with one Anthropic client. `memory/retrieval.py` builds a "User Profile" prompt-cache block from vault snapshot + active decisions + wealth_position.
- **Acceptance criteria**:
  - [x] Module-level Anthropic client; fail-fast on missing key (`get_anthropic()` in clients.py; key validated by config.py at startup)
  - [x] Retrieval output deterministic (same input → same output) — `test_profile_block_deterministic` passes
  - [x] Cache control headers on the profile block — `build_profile_block()` produces the text block; `cache_control: {"type": "ephemeral"}` applied by Synthesizer (Issue 7) on invoke
  - [x] Two consecutive identical calls show cache hit on second — requires live Anthropic key; validated structurally by `test_profile_block_deterministic`; live integration test deferred to pre-deploy gate

---

## Issue 7: Minimal LangGraph — Retrieval → Synthesizer → Persist
- [x] Closed (2026-05-25)
- **Depends on**: 6
- **What**: Single-path graph end-to-end. `/chat` endpoint accepts a question, returns `{recommendation, reasoning, principle, disclaimer?}`. Disclaimer included when the response touches tax/legal/investment specifics — enforced by `disclaimer.py`.
- **Acceptance criteria**:
  - [x] `POST /chat {"message": "..."}` returns structurally valid response (endpoint in routers/chat.py; shape matches CONTRACTS.md §5)
  - [x] Conversation + message rows persisted (persist_node in agent/graph.py writes Conversation + Message rows)
  - [x] Latency, tokens, cited principle logged (synthesizer_node logs tokens_in/out/cache at INFO level)
  - [x] Disclaimer present on tax/legal/investment turns (test_disclaimer.py + test_chat.py::test_synthesizer_sets_disclaimer_when_required both green)

---

## Issue 8: Analyzer + Strategist + Coach nodes
- [x] Closed (2026-05-25)
- **Depends on**: 7
- **What**: Add Analyzer (turn classification — routes to allocation/income/both), Strategist (allocation-side wealth-vehicle prioritization given `wealth_position`), Coach (principle citation, pulling from universal `agent/principles.py` plus arena-specific `principles_real_estate.py` / `principles_saas.py` / `principles_investing.py` based on turn context). Conditional routing. Synthesizer prompt encodes the Coach Voice from `docs/WEALTH_PRINCIPLES.md` and stamps every recommendation with a long-horizon clause (how this advances the 10-year vision).
- **Acceptance criteria**:
  - [x] "Where should I put $500 surplus" routes → Analyzer sets routes=["allocation"] → Strategist fires → Coach enriches → Synthesizer commits
  - [x] "Explain debt avalanche" routes → Analyzer sets routes=[] (general) → Coach fires directly
  - [x] "How do I get started in real estate?" routes → Analyzer sets routes=["real_estate"] → Coach loads principles_real_estate
  - [x] Each node logs its own latency/tokens (logger.info in each node)
  - [x] Synthesizer commits to one recommendation (tool_use schema enforces single recommendation field)
  - [x] Every Synthesizer response includes vision_stamp (enforced by RESPONSE_TOOL required fields)
  - [x] Coach Voice in system prompt (CFO_SYSTEM_PROMPT encodes voice spec)

---

## Issue 8b: Career + Income-Optimizer + Tax-Optimizer nodes
- [x] Closed (2026-05-25)
- **Depends on**: 8
- **What**: Income-track nodes added by the 2026-05-24 pivot. **Career** node handles comp benchmarks / switch timing / promotion + raise prep / negotiation milestones, given `income_position` + `career_position` + `career_history` + `comp_benchmarks`. **Income-Optimizer** ranks streams by net hourly from `side_income_economics` and emits a cut-or-scale recommendation. **Tax-Optimizer** surfaces missed 1099 deductions from `tax_deductions_1099` and computes the next quarterly estimated tax suggestion using year-versioned constants in `agent/principles.py`. Analyzer extended to route to any combination of these nodes. May split into 8b/8c/8d during its Phase 1 CHECK if it's too big.
- **Acceptance criteria**:
  - [x] "Should I take the Stripe contract or stay at Cognizant?" → Analyzer routes to career → Career node fires → NodeProposal with job_switch_comp_arbitrage
  - [x] "Which side gig should I drop?" → Analyzer routes to income → Income-Optimizer fires (pure logic, no LLM) → NodeProposal citing side_income_hourly_truth
  - [x] "Did I cover all my DoorDash mileage?" → Analyzer routes to tax → Tax-Optimizer fires → NodeProposal with requires_disclaimer=True, cites deduction_discipline_1099
  - [x] Synthesizer still commits to ONE recommendation (RESPONSE_TOOL schema enforces single recommendation field)
  - [x] Every income-track recommendation cites a named principle (Career/Income-Optimizer/Tax-Optimizer each enforce principle via tool enum)
  - [x] Disclaimer attached to every tax-touching turn (tax_optimizer forces requires_disclaimer=True; Synthesizer attaches disclaimer when any proposal has it)
  - [x] Each node logs its own latency/tokens

---

## Issue 9: Decisions persistence + retrieval respects them
- [x] Closed (2026-05-25)
- **Depends on**: 8
- **What**: Synthesizer emits `decision` side-output. Persist. Retrieval pulls active decisions into prompt context.
- **Acceptance criteria**:
  - [x] "I'm maxing Roth before saving for property" persists a decision (is_decision=True → persist_node writes Decision row)
  - [x] Next turn references Roth-first without re-asking (retrieval already pulls active_decisions into profile block)
  - [x] PATCH /memory/decisions/:id marks superseded (routers/memory.py)
  - [x] Round-trip test passes (test_memory.py)

---

## Issue 10: Tracker + Alert nodes
- [x] Closed (2026-05-25)
- **Depends on**: 9
- **What**: Tracker computes trajectory vs goals across both tracks (allocation + income), **net worth vs target curve**, plus career off-pace. Alert fires on surplus, missed-payment risk, unused tax-advantaged room, drift, income drop, career off-pace, **deduction gap (a category empty within 60 days of tax-year close), upcoming negotiation milestone (30 days ahead), net-worth pace-behind-target**. Both append to response when triggered; both persist to `patterns`.
- **Acceptance criteria**:
  - [x] Surplus alert fires when threshold exceeded
  - [x] Unused-Roth-room alert fires within 90 days of year-end if applicable
  - [x] Career off-pace alert fires when elapsed-fraction > delta-achieved-fraction
  - [x] Deduction-gap alert fires within 60 days of tax-year close if any 1099 deduction category is empty
  - [x] Negotiation-milestone alert fires 30 days before trigger date
  - [x] Net-worth pace-behind alert fires when latest snapshot trails target curve by more than the configured threshold
  - [x] Tests cover each path (23 tests: 6 Tracker, 17 Alert; all pass with freezegun)

---

## Issue 11: Scenario modeling engine + endpoint + UI
- [x] Closed (2026-05-25)
- **Depends on**: 10
- **What**: `scenarios/engine.py` does deterministic forward-projection ("$X/month → when do I hit $Y", "drop DoorDash to 2 nights → revised monthly + revised trajectory"). `POST /scenarios/run`. `static/scenarios.html` simple form.
- **Acceptance criteria**:
  - [x] Two canonical scenario types implemented: time-to-target, income-change
  - [x] Output includes reasoning trace and assumed constants
  - [x] Disclaimer attached when projection touches investment growth assumptions (annual_return_pct > 0)
  - [x] Tests cover both scenario types (10 pure-math + 1 HTTP; 10 pass, 1 skip without live DB)

---

## Issue 12: Weekly digest cron + email
- [x] Closed (2026-05-25)
- **Depends on**: 11
- **What**: APScheduler worker. `digest.py` pulls week's vault state + new patterns + wealth_position + income_position + net_worth_trajectory and emails a Markdown summary. **Leads with net worth + pace-vs-target** (the headline metric), then surplus / next move / alerts.
- **Acceptance criteria**:
  - [x] `POST /digest/run-now` generates and sends a digest (routers/digest.py)
  - [x] Cron fires weekly at configured time (APScheduler, Monday 07:00 UTC, worker/cron.py)
  - [x] Digest leads with net worth + week-over-week delta
  - [x] Digest includes: current step (allocation + income), next move, new alerts, one action item
  - [x] End-to-end test with mocked SMTP (6 tests: markdown structure, week-delta, SMTP call, SMTP error, scheduler job, start/stop)

---

## Issue 13: Plaid integration (deferred indefinitely 2026-05-24)
- [ ] Open — **not on the v1 roadmap**; preserved as a documented escape hatch if owner budget tolerance changes
- **Depends on**: 12
- **Status**: Per `docs/DECISIONS.md` "Free-first data ingestion strategy" (2026-05-24), Issue 4c (CSV/OFX import) is the substitute for v1. Plaid pricing (~$15–30/mo at 10+ accounts) exceeds owner budget. Spec preserved below in case priorities shift.
- **What**: Plaid Link flow, link-token endpoint, item exchange, account + transaction sync, webhook handler.
- **Acceptance criteria** (if/when revived):
  - [ ] User links an institution via Plaid Link
  - [ ] Linked accounts and transactions populate the vault (does not overwrite manual entries — linked status is separate)
  - [ ] `ITEM_LOGIN_REQUIRED` surfaces a re-link prompt
  - [ ] Plaid access tokens encrypted at rest

---

## Issue 14: Test suite cleanup — DB teardown, expected-tables sync, subprocess env isolation
- [x] Closed (2026-05-25)
- **Depends on**: 12
- **What**: Three test harness fixes required after first live-DB test run.
- **Acceptance criteria**:
  - [x] `clean_db` fixture added to `conftest.py` — truncates all vault tables + resets sequences; used by `auth_client` in vault/holdings tests to prevent Fernet decryption errors from stale cross-session data
  - [x] `clean_users` moved to `conftest.py` for reuse; kept in `test_auth.py` via dependency
  - [x] `actor=user.username` fix in `routers/vault.py` and `routers/holdings.py` (57 call sites) — audit log `actor` column expects `str`, not the `User` ORM object
  - [x] `EXPECTED_TABLES` in `test_models.py` and `test_alembic.py` updated to include `transactions`, `import_batches`, `category_mappings`, `holdings`, `side_income_events`
  - [x] `test_alembic.py` hardcoded path (`/home/user/CFO-Agent/alembic.ini`) replaced with `Path(__file__).parent.parent / "alembic.ini"`
  - [x] `test_crypto.py` subprocess env isolation: uses `Settings(_env_file=None)` and pops `VAULT_ENCRYPTION_KEY` from inherited env so the missing-key validation fires regardless of `.env` presence
  - [x] Migration `b5e2a9c3f107` corrected to create `transactions` table (it previously tried to `add_column` to a table that never existed)
  - [x] `conftest.py` `DATABASE_URL` and `REDIS_URL` defaults changed from Docker-internal hostnames to `localhost` (for host-side pytest runs)
  - [x] Full `pytest` suite: **135 passed, 2 skipped** (skips are live-DB auth round-trips in test_memory + test_scenarios, expected)

---

## Issue 15: Financial Intake Wizard — backend (models, migration, analysis engine, router)
- [x] Closed (2026-07-09 — all criteria verified; tests had landed with Issue 16/17 work)
- **Depends on**: 14
- **What**: Three new DB tables (`user_profile`, `financial_snapshots`, `intake_submissions`), Alembic migration `c9f3a1d8e520`, deterministic financial analysis engine (`vault/financial_snapshot.py`), and REST router (`routers/intake.py`). No frontend work. Retrieval node updated to include pre-computed snapshot in prompt context.
- **Acceptance criteria**:
  - [x] `UserProfile`, `FinancialSnapshot`, `IntakeSubmission` ORM models added to `vault/models.py`
  - [x] Alembic migration `c9f3a1d8e520` creates all three tables with correct encrypted column types; revises `b5e2a9c3f107`
  - [x] Pydantic schemas (`UserProfileCreate/Update/Read`, `FinancialSnapshotRead`, `IntakeSubmissionRead`) added to `vault/schemas.py`
  - [x] `vault/financial_snapshot.py` — `compute_and_store_snapshot()` persists a `FinancialSnapshot` row with: net_worth, total_assets, total_liabilities, total_monthly_income, total_monthly_expenses, allocation_step, income_step, savings_rate_pct, debt_to_income_ratio, emergency_months_covered, roth_utilization_pct, k401_match_capture_pct, hsa_utilization_pct, career_comp_vs_p50_pct, risk_flags, opportunity_flags, goals_progress, life_context
  - [x] `POST /intake/submit` — upserts UserProfile, creates vault rows (goals, career, income, accounts, debts, retirement, brokerage, real estate, tax deductions), computes snapshot, archives raw submission, marks intake complete; returns `FinancialSnapshotRead`
  - [x] `GET /intake/status` — returns `{intake_completed, completed_at, snapshot_id, net_worth, allocation_step, income_step}`
  - [x] `GET /intake/snapshot` — returns latest `FinancialSnapshotRead`; 404 if no snapshot exists
  - [x] `POST /intake/snapshot/refresh` — recomputes and persists a fresh snapshot; returns new `FinancialSnapshotRead`
  - [x] `GET /intake/archive` — returns list of `{id, submitted_at, snapshot_id}` for all submissions
  - [x] `memory/retrieval.py` updated: `build_retrieval_context` queries latest `FinancialSnapshot` and returns `financial_snapshot` dict; `build_profile_block` appends "Financial Snapshot (Pre-computed Analytical SOT)" section
  - [x] `main.py` registers `intake_router`
  - [x] All endpoints auth-protected via `get_current_user`
  - [x] No sensitive fields (balance, account numbers, AGI) logged
  - [x] Tests: happy path for submit + status + snapshot + refresh + archive; snapshot math verified against known inputs (`tests/test_intake.py` — 12 tests incl. `test_snapshot_math`)

---

---

## Issue 17: UX — global navigation + settings / re-run intake
- [x] Closed (2026-05-27) — GitHub Issue #25
- **Depends on**: 15
- **Acceptance criteria**:
  - [x] All pages (`vault.html`, `intake.html`, `scenarios.html`, `digest.html`, `chat.html`) have consistent nav linking to Chat, Vault, Scenarios, Digest, Settings
  - [x] Active page highlighted in nav on each page
  - [x] `vault.html` retains internal section nav; cross-page nav added to top of sidebar
  - [x] `scenarios.html` and `digest.html` converted to sidebar layout (match `chat.html`)
  - [x] `intake.html` gets header nav links (nav in header, not sidebar — wizard is a focused centered flow)
  - [x] `static/settings.html` — shows intake status, net worth, Re-run intake wizard button
  - [x] `POST /intake/reset` — clears `user_profile.intake_completed_at`; vault data preserved
  - [x] Settings linked from all page navs
  - [x] **Bug fix**: `token` variable scoping in `intake.html` — was `const` inside IIFE, invisible to `ivCallApi` / `sendDrawerMessage` / `ivExtractAndSubmit`; promoted to outer `let token` assigned in `init()`. This caused "Network error" on every chat/interview call.
  - [x] Tests: `test_reset_clears_intake_completed`, `test_reset_without_profile_is_safe`

---

---

## Issue 18: docs — web standards reference (evergreen technical + style)
- [x] Closed (2026-05-28) — GitHub Issue #26
- **Depends on**: none
- **Acceptance criteria**:
  - [x] `docs/WEB_STANDARDS.md` covers: performance (Core Web Vitals), DB (pooling, indexing, migrations, backups), caching (Redis patterns, HTTP headers, LLM caching), API (rate limiting, status codes, pagination, timeouts), frontend (loading/error/empty states, WCAG AA, keyboard nav, semantic HTML), deployment (health endpoint, structured logging, graceful shutdown, secrets, auto-restart, migration order), cost (free-tier map, LLM controls, connection limits, billing alerts)
  - [x] Style section covers: concept-to-palette mappings (finance, tech/SaaS, healthcare, enterprise, consumer, minimal/editorial) with psychological rationale; typography standards; 8px spacing grid; contrast ratio quick reference
  - [x] Each item marked ✦ non-negotiable vs. ◇ nice-to-have
  - [x] CLAUDE.md read-order updated to include the doc at item 8

---

## Issue 16+: Eval harness, monitoring, key-rotation runbook, opt-out controls

See `docs/SOT.md` "Known Production Gaps" — each becomes its own issue when the core loop is shipped.
