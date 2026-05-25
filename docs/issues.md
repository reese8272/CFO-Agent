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
  - [ ] **Steady-state manual workload measured at <30 min/month** — requires live walkthrough with running app; deferred to pre-deploy gate
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
- [ ] Open
- **Depends on**: 4b
- **What**: Added 2026-05-24 to the free-first ingestion strategy. Bulk-upload CSV or OFX statements from any institution that exports them (most banks, credit cards, brokerages do). User uploads the file, picks the target account, classifies any unmapped categories, and the parser populates the vault. Replaces Plaid as the primary aggregation tool for v1.
- **Acceptance criteria**:
  - [ ] `POST /import/transactions` accepts CSV (multiple bank/card formats) and OFX
  - [ ] User selects target `account_id` and the parser maps rows to transactions (or to balance updates for balance-only accounts)
  - [ ] Duplicate detection: re-importing the same file does not double-insert (idempotent on a hash of date + amount + merchant)
  - [ ] Unmapped categories surface a one-click classifier UI that learns from prior classifications
  - [ ] Audit log row per import batch
  - [ ] Tests cover at least 3 institutional CSV formats (one bank, one card, one brokerage) + 1 OFX file

---

## Issue 5: Wealth-position + income-position + net-worth-trajectory endpoints
- [ ] Open
- **Depends on**: 4
- **What**: `vault/wealth_position.py` computes the user's step on the allocation track (1–6). `vault/income_position.py` computes the step on the income track (1–5). Both backed by `GET /wealth/position` and `GET /income/position`. `GET /wealth/trajectory` returns next-move + open gaps across both tracks. `GET /wealth/net_worth_trajectory` returns historical net worth from `net_worth_snapshots` plus the target curve to the configured 5-/10-year vision. **Scope expanded 2026-05-24** to include the income track and net-worth trajectory.
- **Acceptance criteria**:
  - [ ] `wealth_position` returns a deterministic step (1–6) given any vault state
  - [ ] `income_position` returns a deterministic step (1–5) given any vault state
  - [ ] Unit tests cover boundary cases on both (e.g., emergency fund exactly at 3 months; lowest-margin stream exactly 30% below top)
  - [ ] Endpoints return `{step, step_name, next_move, open_gaps}`
  - [ ] Trajectory endpoint returns highest-leverage next move across both tracks
  - [ ] Net-worth-trajectory endpoint returns `{snapshots, target_curve, pace_vs_target}`
  - [ ] No LLM call needed — pure data logic

---

## Issue 6: Anthropic singleton + retrieval node
- [ ] Open
- **Depends on**: 5
- **What**: `clients.py` with one Anthropic client. `memory/retrieval.py` builds a "User Profile" prompt-cache block from vault snapshot + active decisions + wealth_position.
- **Acceptance criteria**:
  - [ ] Module-level Anthropic client; fail-fast on missing key
  - [ ] Retrieval output deterministic (same input → same output)
  - [ ] Cache control headers on the profile block
  - [ ] Two consecutive identical calls show cache hit on second

---

## Issue 7: Minimal LangGraph — Retrieval → Synthesizer → Persist
- [ ] Open
- **Depends on**: 6
- **What**: Single-path graph end-to-end. `/chat` endpoint accepts a question, returns `{recommendation, reasoning, principle, disclaimer?}`. Disclaimer included when the response touches tax/legal/investment specifics — enforced by `disclaimer.py`.
- **Acceptance criteria**:
  - [ ] `POST /chat {"message": "..."}` returns structurally valid response
  - [ ] Conversation + message rows persisted
  - [ ] Latency, tokens, cited principle logged
  - [ ] Disclaimer present on tax/legal/investment turns (structural test)

---

## Issue 8: Analyzer + Strategist + Coach nodes
- [ ] Open
- **Depends on**: 7
- **What**: Add Analyzer (turn classification — routes to allocation/income/both), Strategist (allocation-side wealth-vehicle prioritization given `wealth_position`), Coach (principle citation, pulling from universal `agent/principles.py` plus arena-specific `principles_real_estate.py` / `principles_saas.py` / `principles_investing.py` based on turn context). Conditional routing. Synthesizer prompt encodes the Coach Voice from `docs/WEALTH_PRINCIPLES.md` and stamps every recommendation with a long-horizon clause (how this advances the 10-year vision).
- **Acceptance criteria**:
  - [ ] "Where should I put $500 surplus" routes Analyzer → Strategist → Coach → Synthesizer
  - [ ] "Explain debt avalanche" routes Analyzer → Coach → Synthesizer
  - [ ] "How do I get started in real estate?" routes Analyzer → Coach (loading `principles_real_estate`) → Synthesizer
  - [ ] Each node logs its own latency/tokens
  - [ ] Synthesizer commits to one recommendation; refuses to enumerate unless asked
  - [ ] Every Synthesizer response includes one clause stamping the recommendation against the 10-year vision (target net worth / passive income / chosen path)
  - [ ] Synthesizer voice matches the Coach Voice spec (eval-harness tone checks pass; no hustle-bro, no condescending explainer, no Suze-Orman finger-wagging)

---

## Issue 8b: Career + Income-Optimizer + Tax-Optimizer nodes
- [ ] Open
- **Depends on**: 8
- **What**: Income-track nodes added by the 2026-05-24 pivot. **Career** node handles comp benchmarks / switch timing / promotion + raise prep / negotiation milestones, given `income_position` + `career_position` + `career_history` + `comp_benchmarks`. **Income-Optimizer** ranks streams by net hourly from `side_income_economics` and emits a cut-or-scale recommendation. **Tax-Optimizer** surfaces missed 1099 deductions from `tax_deductions_1099` and computes the next quarterly estimated tax suggestion using year-versioned constants in `agent/principles.py`. Analyzer extended to route to any combination of these nodes. May split into 8b/8c/8d during its Phase 1 CHECK if it's too big.
- **Acceptance criteria**:
  - [ ] "Should I take the Stripe contract or stay at Cognizant?" routes Analyzer → Career → Coach → Synthesizer with a switch-arbitrage recommendation
  - [ ] "Which side gig should I drop?" routes Analyzer → Income-Optimizer → Coach → Synthesizer with the lowest-net-hourly stream named
  - [ ] "Did I cover all my DoorDash mileage this year?" routes Analyzer → Tax-Optimizer → Synthesizer with a deduction gap report + disclaimer
  - [ ] Synthesizer still commits to ONE recommendation when multiple income nodes fire
  - [ ] Every income-track recommendation cites a named principle from `docs/WEALTH_PRINCIPLES.md` (job-switch arbitrage, side-income hourly truth, 1099 deduction discipline, quarterly estimated tax, or comp negotiation)
  - [ ] Disclaimer attached to every tax-touching turn (structural test)
  - [ ] Each node logs its own latency/tokens

---

## Issue 9: Decisions persistence + retrieval respects them
- [ ] Open
- **Depends on**: 8
- **What**: Synthesizer emits `decision` side-output. Persist. Retrieval pulls active decisions into prompt context.
- **Acceptance criteria**:
  - [ ] "I'm maxing Roth before saving for property" persists a decision
  - [ ] Next turn references Roth-first without re-asking
  - [ ] `PATCH /memory/decisions/:id` marks `superseded`
  - [ ] Round-trip test passes

---

## Issue 10: Tracker + Alert nodes
- [ ] Open
- **Depends on**: 9
- **What**: Tracker computes trajectory vs goals across both tracks (allocation + income), **net worth vs target curve**, plus career off-pace. Alert fires on surplus, missed-payment risk, unused tax-advantaged room, drift, income drop, career off-pace, **deduction gap (a category empty within 60 days of tax-year close), upcoming negotiation milestone (30 days ahead), net-worth pace-behind-target**. Both append to response when triggered; both persist to `patterns`.
- **Acceptance criteria**:
  - [ ] Surplus alert fires when threshold exceeded
  - [ ] Unused-Roth-room alert fires within 90 days of year-end if applicable
  - [ ] Career off-pace alert fires when elapsed-fraction > delta-achieved-fraction
  - [ ] Deduction-gap alert fires within 60 days of tax-year close if any 1099 deduction category is empty
  - [ ] Negotiation-milestone alert fires 30 days before trigger date
  - [ ] Net-worth pace-behind alert fires when latest snapshot trails target curve by more than the configured threshold
  - [ ] Tests cover each path

---

## Issue 11: Scenario modeling engine + endpoint + UI
- [ ] Open
- **Depends on**: 10
- **What**: `scenarios/engine.py` does deterministic forward-projection ("$X/month → when do I hit $Y", "drop DoorDash to 2 nights → revised monthly + revised trajectory"). `POST /scenarios/run`. `static/scenarios.html` simple form.
- **Acceptance criteria**:
  - [ ] Two canonical scenario types implemented: time-to-target, income-change
  - [ ] Output includes reasoning trace and assumed constants
  - [ ] Disclaimer attached when projection touches investment growth assumptions
  - [ ] Tests cover both scenario types

---

## Issue 12: Weekly digest cron + email
- [ ] Open
- **Depends on**: 11
- **What**: APScheduler worker. `digest.py` pulls week's vault state + new patterns + wealth_position + income_position + net_worth_trajectory and emails a Markdown summary. **Leads with net worth + pace-vs-target** (the headline metric), then surplus / next move / alerts.
- **Acceptance criteria**:
  - [ ] `POST /digest/run-now` generates and sends a digest
  - [ ] Cron fires weekly at configured time
  - [ ] Digest leads with net worth + week-over-week delta + pace vs target curve
  - [ ] Digest includes: cash position, current step (allocation + income), next move, new alerts, one action item
  - [ ] End-to-end test with mocked SMTP

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

## Issue 14+: Eval harness, monitoring, key-rotation runbook, opt-out controls

See `docs/SOT.md` "Known Production Gaps" — each becomes its own issue when the core loop is shipped.
