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
- [ ] Open
- **Depends on**: 1
- **What**: SQLAlchemy models for every vault entity (see `docs/SOT.md` data model) + memory tables. Alembic wired. `crypto.py` with Fernet `encrypt()`/`decrypt()` from `VAULT_ENCRYPTION_KEY`.
- **Acceptance criteria**:
  - [ ] `alembic upgrade head` creates every table including `real_estate`, `business_income`, `retirement_accounts`, `career_position`
  - [ ] Encrypted round-trip test passes
  - [ ] Missing `VAULT_ENCRYPTION_KEY` fails app start with a clear error
  - [ ] Audit log table append-only at the app layer

---

## Issue 3: Single-user auth (JWT)
- [ ] Open
- **Depends on**: 2
- **What**: `/auth/register` (rejects after first user), `/auth/token`, `get_current_user` dependency. bcrypt + PyJWT.
- **Acceptance criteria**:
  - [ ] Register allowed once, 409 thereafter
  - [ ] Token endpoint returns valid JWT with configured expiry
  - [ ] Protected routes 401 without token

---

## Issue 4: Vault CRUD + minimal HTMX UI
- [ ] Open
- **Depends on**: 3
- **What**: CRUD endpoints for every vault entity. HTMX forms in `static/vault.html`. Includes the new entities (real estate, business income, retirement accounts, career position).
- **Acceptance criteria**:
  - [ ] Every entity from `docs/SOT.md` CRUDable via API
  - [ ] Closing an entity writes an audit log row
  - [ ] HTMX form for at least cards + retirement accounts + career position renders and persists
  - [ ] Tests cover CRUD happy paths + 404/401

---

## Issue 5: Wealth-position computation + endpoint
- [ ] Open
- **Depends on**: 4
- **What**: `vault/wealth_position.py` computes the user's current step on the wealth-building sequence (`docs/WEALTH_PRINCIPLES.md`). `GET /wealth/position` returns it. `GET /wealth/trajectory` returns next-move + open gaps.
- **Acceptance criteria**:
  - [ ] Function returns a deterministic step (1–6) given any vault state
  - [ ] Unit tests cover boundary cases (e.g., emergency fund exactly at 3 months)
  - [ ] Endpoint returns `{step, step_name, next_move, open_gaps}`
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
- **What**: Add Analyzer (turn classification), Strategist (wealth-vehicle prioritization given `wealth_position`), Coach (principle citation). Conditional routing.
- **Acceptance criteria**:
  - [ ] "Where should I put $500 surplus" routes Analyzer → Strategist → Coach → Synthesizer
  - [ ] "Explain debt avalanche" routes Analyzer → Coach → Synthesizer
  - [ ] Each node logs its own latency/tokens
  - [ ] Synthesizer commits to one recommendation; refuses to enumerate unless asked

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
- **What**: Tracker computes trajectory vs goals + career off-pace. Alert fires on surplus, missed-payment risk, unused tax-advantaged room, drift, income drop, career off-pace. Both append to response when triggered; both persist to `patterns`.
- **Acceptance criteria**:
  - [ ] Surplus alert fires when threshold exceeded
  - [ ] Unused-Roth-room alert fires within 90 days of year-end if applicable
  - [ ] Career off-pace alert fires when elapsed-fraction > delta-achieved-fraction
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
- **What**: APScheduler worker. `digest.py` pulls week's vault state + new patterns + wealth_position + trajectory and emails a Markdown summary.
- **Acceptance criteria**:
  - [ ] `POST /digest/run-now` generates and sends a digest
  - [ ] Cron fires weekly at configured time
  - [ ] Digest includes: cash position, week-over-week change, current step + next move, new alerts, one action item
  - [ ] End-to-end test with mocked SMTP

---

## Issue 13: Plaid integration (deferred — open separately)
- [ ] Open
- **Depends on**: 12
- **What**: Plaid Link flow, link-token endpoint, item exchange, account + transaction sync, webhook handler.
- **Acceptance criteria**:
  - [ ] User links an institution via Plaid Link
  - [ ] Linked accounts and transactions populate the vault (does not overwrite manual entries — linked status is separate)
  - [ ] `ITEM_LOGIN_REQUIRED` surfaces a re-link prompt
  - [ ] Plaid access tokens encrypted at rest

---

## Issue 14+: Eval harness, monitoring, key-rotation runbook, opt-out controls

See `docs/SOT.md` "Known Production Gaps" — each becomes its own issue when the core loop is shipped.
