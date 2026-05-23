# Personal Financial CFO Agent — Project Kickstart

**Working title**: `personal-cfo` (rename freely)
**Source**: condensed and expanded from the updated brief on branch `claude/finance-agent-brief-xIS90`
**Last updated**: 2026-05-23 (v2 — pivoted from generic finance agent to wealth-building CFO)
**Status**: Pre-build planning. Drop this file into the new repo as `docs/KICKSTART.md`, fill the `<PLACEHOLDER>` blocks, then promote each section into its own doc (`docs/PRD.md`, `docs/SOT.md`, `docs/issues.md`, `CLAUDE.md`) before Issue 1.
**Disclaimer (must appear in every interface and the system prompt)**: *This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.*

---

## Table of Contents

1. [Core Insight](#1-core-insight)
2. [PRD](#2-prd)
3. [SOT — Source of Truth](#3-sot--source-of-truth)
4. [Wealth-Building Framework (the reasoning sequence)](#4-wealth-building-framework)
5. [Open-Ended Questions — Answered](#5-open-ended-questions--answered)
6. [Starting Issue Backlog](#6-starting-issue-backlog)
7. [Project Workflow & Required Commands](#7-project-workflow--required-commands)
8. [CLAUDE.md Template (drop into new repo)](#8-claudemd-template)

---

# 1. Core Insight

> **The reason no AI gives truly personalized financial advice is a data problem, not an intelligence problem.**

Every existing tool hits 7/10 because it sees a partial picture. Plaid can read major banks and cards, but it can't see gig income at its source, coaching cash, real estate equity, business P&L, or — most importantly — your *decisions and goals*. The unlock isn't smarter AI. It's **complete context + good AI**.

This product is a **personal CFO agent**, not a budgeting tool and not a card optimizer. It reasons over the full picture (automated where it can, manual where it must be) and helps the user execute the moves that actually compound wealth: Roth IRA, Solo 401(k), index funds, real estate, business income, career-income trajectory.

---

# 2. PRD

**Version**: 0.2 (CFO pivot) | **Status**: Draft, ready for issue scoping after Section 5 placeholders are filled

## Problem Statement

Existing personal-finance tools are either *trackers* (Monarch, Copilot, YNAB), *narrow optimizers* (MaxRewards, Credit Karma), or *shallow chatbots* (Cleo). None solve the **data completeness problem**: they can't see gig income at its source, cash income, real estate equity, retirement accounts at every institution, business P&L, or any record of the user's intentional decisions. With incomplete context, every recommendation is generic. With complete context — automated where possible, manual where required — a competent LLM becomes a real CFO: it knows where you are on the wealth-building sequence, calibrates advice to your specific irregular income, tracks trajectory toward 5-year goals, and explains the principle behind every move so the user builds judgment over time.

## Target User (v1)

A single user — the developer/owner. **Personal use only.** Architecture must not preclude multi-user, but no auth-of-others, no sharing, and no compliance scope beyond a personal threat model in v1.

## User Stories

- As the user, I want a single chat surface where I ask anything about my financial life and get a CFO-level answer that uses my complete picture.
- As the user, I want a **complete manual vault** for everything Plaid can't reach: gig income (DoorDash), cash income (coaching), real estate equity, business income, retirement accounts, goals, decisions.
- As the user, I want the agent to tell me **where I am in the wealth-building sequence** (emergency fund → eliminate high-interest debt → max tax-advantaged → market exposure → leverage → ownership) and what my **next move** is.
- As the user, I want the agent to surface **tax-advantaged room I haven't used** — specifically the Solo 401(k) I qualify for via 1099 income, and Roth IRA capacity.
- As the user, I want the agent to **track career trajectory** as a wealth lever — current comp, target role, target comp, time horizon — and factor career-income growth into the plan.
- As the user, I want **scenario modeling** — "if I save $X/month, when do I hit Y? what if I drop DoorDash to 2 nights?"
- As the user, I want the agent to **commit to a recommendation** (CFO with a point of view), not present a buffet of options.
- As the user, I want the agent to **explain the principle** behind every move (debt avalanche, time-in-market, tax arbitrage, etc.) so I learn, not just comply.
- As the user, I want the agent to **remember decisions** I've made ("Roth before real estate this year") and not re-recommend against them.
- As the user, I want a **weekly digest** — cash position, week-over-week change, trajectory vs goals, this week's next move.
- As the user, I want **proactive alerts** for surplus detection ("$800 left this month — here's where it goes and why"), drift from plan, missed payment risk, and unused tax-advantaged room.
- As the user, I want to **add Plaid live data** once the manual layer is solid, without restructuring the agent.

## Technical Decisions

**Decision**: Build MVP on a **complete manual vault** before any Plaid integration — **Why**: The data-completeness problem can't be solved by Plaid alone (gig source, cash, real estate, business, decisions are invisible to it). Owning the manual layer first forces the schema to be right; Plaid becomes a *partial automation* of an already-complete model.

**Decision**: **CFO-with-a-POV, not advisor-presenting-options** — **Why**: The brief calls out the distinction explicitly. The synthesizer prompt enforces a single committed recommendation with reasoning, not a list. Users who want options can always ask.

**Decision**: **Wealth-building sequence as a first-class concept** — **Why**: The agent must always know which step the user is on (Section 4) and what the next move is. This is the differentiator vs generic "spending insights." Encoded in a `wealth_position` view computed from vault data.

**Decision**: Single-user personal app for v1 — **Why**: Eliminates compliance scope (no PII for third parties, no SOC2 path) and removes the hardest security problems until product value is proven. Schema includes `user_id` foreign keys from day one so multi-user is mechanical later.

**Decision**: **LangGraph** for agent orchestration with 5 named nodes (Analyzer → Strategist → Coach → Tracker → Alert) — **Why**: Multi-step reasoning over a wealth picture needs explicit state and conditional routing. LangGraph is built for that.

**Decision**: **Claude (Anthropic SDK)** as the only LLM — **Why**: Best at nuanced explanation and at refusing to invent state-specific tax/legal facts. Prompt caching keeps cost flat as the vault grows.

**Decision**: **PostgreSQL** for vault + memory, **Redis** for agent session state — **Why**: Postgres handles relational financial data plus JSONB for flexible card-benefit blobs. Redis keeps LangGraph node state hot.

**Decision**: **Encryption at rest for all financial fields** (Fernet, key in env) — **Why**: Personal threat model is realistic — device theft, accidental git push, backup leak — not nation-state. Symmetric encryption on sensitive columns + full-disk encryption + TLS in transit covers it.

**Decision**: **FastAPI + HTMX**, no SPA — **Why**: The hard part is the agent, not the UI. Chat textbox, vault forms, goal-progress view, digest viewer. Avoid build-step complexity.

**Decision**: **Docker Compose** for local dev and self-hosted prod — **Why**: Three services (Postgres, Redis, FastAPI + worker) need orchestration. Compose is the minimal correct tool.

**Decision**: **Disclaimer wrapper on every agent response touching tax/legal/investment specifics** — **Why**: The agent is not a licensed advisor. The synthesizer prompt enforces the disclaimer; a structural test verifies it appears whenever the response touches those domains.

**Decision**: Defer Plaid until after Issue ~11 — **Why**: Plaid adds OAuth, token rotation, vendor coupling, and per-account cost. The manual layer must be proven valuable first; if it isn't, Plaid won't save it.

## Out of Scope (v1)

- Multi-user accounts, sharing, organization tier
- Mobile-native app (responsive web only)
- Investment trade execution or brokerage integration
- Crypto wallet integration
- Tax filing or IRS form generation (reasoning only, no submission)
- Custom budgeting methodologies (envelope, zero-based) as a UI primitive
- SMS/push notifications (email digest only)
- Real estate transaction execution (reasoning only)

## Acceptance Criteria (v1 MVP)

### Vault Completeness
- [ ] Vault covers: accounts, cards, income streams (with `source_type` distinguishing W-2 / 1099 / cash / gig / coaching / business), recurring expenses, debts, assets, **real estate holdings (with equity)**, **business income/expenses**, **retirement accounts (Roth, 401k, IRA, Solo 401k)**, goals, decisions, **career_position** (current comp, target role, target comp, target date).
- [ ] User CRUDs every entity through a web form.
- [ ] Sensitive fields encrypted at rest.

### Wealth-Building Position
- [ ] Agent computes the user's current step on the wealth-building sequence on every chat turn.
- [ ] Agent always surfaces "next move given your position" when relevant.
- [ ] Vault has a `wealth_position` view that is queryable directly (debug + tests).

### Agent
- [ ] Chat endpoint accepts a question, loads the full vault snapshot + active decisions + memory, runs LangGraph (Analyzer → Strategist → Coach → Tracker → Alert → Synthesizer), returns `{recommendation, reasoning, principle, disclaimer?}`.
- [ ] Synthesizer **commits to one recommendation**; refuses to list options unless explicitly asked.
- [ ] Agent refuses state-specific tax/legal advice with a disclaimer pointing to a CPA/CFP.
- [ ] Every recommendation cites a named wealth principle (Section 4).
- [ ] Decisions the user marks as committed persist and are respected in future turns.

### Career Trajectory
- [ ] Vault stores current role, current comp, target role, target comp, target date.
- [ ] Strategist factors target comp into long-horizon planning.
- [ ] Tracker flags if elapsed time vs delta-to-target comp is off-pace.

### Scenario Modeling
- [ ] User can ask "if I save $X/month, when do I hit Y?" and get a deterministic computed answer with a one-paragraph reasoning trace.
- [ ] User can ask "what if I drop DoorDash to 2 nights?" and get a recomputed monthly surplus + revised trajectory.

### Proactive Digest
- [ ] Weekly cron emails a Markdown digest: cash position, week-over-week change, trajectory vs declared goals, this week's next move, any new alerts.
- [ ] Digest cites every vault row it referenced.

### Proactive Alerts
- [ ] Surplus alert when month-to-date inflow minus committed outflow > threshold.
- [ ] Minimum-payment-at-risk alert when due date within 3 days and no scheduled transfer.
- [ ] Unused tax-advantaged room alert (Solo 401k or Roth) on a quarterly cadence.
- [ ] Drift alert when category spend exceeds rolling average threshold.

### Operational
- [ ] All Anthropic calls use prompt caching on the vault snapshot; token usage logged per call.
- [ ] All financial-field reads/writes audit-logged.
- [ ] `docker compose up` brings the full stack live; pytest green.
- [ ] Disclaimer appears on every response touching tax/legal/investment specifics (structural test).

---

# 3. SOT — Source of Truth

**Last updated**: 2026-05-23

This describes how the personal-cfo agent **will be built**. Update on every architectural change. Conflicts with PRD: this file wins — log divergence in `docs/DECISIONS.md`.

## Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Backend | FastAPI (Python 3.13+) | Async-first |
| Agent orchestration | LangGraph | Nodes: Analyzer, Strategist, Coach, Tracker, Alert, Synthesizer |
| LLM | Anthropic SDK; default `claude-sonnet-4-6`, `claude-opus-4-7` for long-horizon strategy turns | Prompt caching on vault snapshot mandatory |
| Vault + memory DB | PostgreSQL 16 | Relational + JSONB for flexible card-benefit & decision blobs |
| Session / agent state | Redis 7 | LangGraph checkpointer + short-lived caches |
| Account aggregation | Plaid API (deferred to Issue 11+) | Tokens encrypted at rest |
| Auth | Single-user JWT in v1; OAuth2 surface preserved for future | bcrypt + PyJWT |
| Encryption at rest | `cryptography` Fernet on sensitive columns | Key from `VAULT_ENCRYPTION_KEY` |
| Frontend | Vanilla HTML + HTMX | Chat, vault forms, goal progress view, digest view, scenario modeler |
| Containerization | Docker Compose | `app`, `postgres`, `redis`, `worker` |
| Deployment (v1) | Same Oracle Cloud Free ARM VM as LIVABILITY, distinct subdomain via Cloudflare Tunnel | Distinct systemd service + Postgres DB |

## Environment Variables

| Variable | Required | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | Yes | Anthropic API key |
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:pass@host:5432/personal_cfo` |
| `REDIS_URL` | Yes | `redis://localhost:6379/0` |
| `JWT_SECRET_KEY` | Yes | 32-byte random secret |
| `JWT_EXPIRY_MINUTES` | No | Default `60` |
| `VAULT_ENCRYPTION_KEY` | Yes | Fernet key; document rotation runbook before changing |
| `LLM_TIMEOUT_SECONDS` | No | Default `120` |
| `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM` | Yes (for digest) | SMTP config |
| `DIGEST_RECIPIENT` | Yes | Email for the weekly digest |
| `PLAID_CLIENT_ID`, `PLAID_SECRET`, `PLAID_ENV` | No (phase 2) | Plaid creds |
| `ENV` | No | `development` \| `production`; gates `/docs`, logging |
| `LANGGRAPH_CHECKPOINT_BACKEND` | No | Default `redis` |
| `WEALTH_DISCLAIMER_TEXT` | No | Defaults to canonical disclaimer; override only with care |
| `ALERT_DRIFT_PCT_THRESHOLD` | No | Default `25`; category spend > rolling-3mo avg by this % fires a drift alert |
| `ALERT_INCOME_DROP_PCT_THRESHOLD` | No | Default `30`; income stream rolling-4wk avg dropping by this % fires an alert |

## File Structure

```
/                               # project root
├── CLAUDE.md                   # Drop in from Section 8
├── .env / .env.example
├── requirements.txt
├── pytest.ini
├── docker-compose.yml
├── Dockerfile
│
├── main.py                     # FastAPI entrypoint
├── config.py                   # Env loading; fail-fast on missing required
├── db.py                       # SQLAlchemy engine + session
├── auth.py                     # Single-user JWT
├── crypto.py                   # Fernet helpers
├── clients.py                  # Anthropic singleton + LangGraph runtime
├── digest.py                   # Weekly digest generator
├── disclaimer.py               # Disclaimer text + structural enforcement
│
├── vault/
│   ├── models.py               # Account, Card, IncomeStream, Expense, Debt, Asset,
│   │                           # RealEstate, BusinessIncome, RetirementAccount,
│   │                           # Goal, CareerPosition
│   ├── schemas.py              # Pydantic
│   ├── crud.py                 # CRUD with encryption
│   └── wealth_position.py      # Compute current step on wealth sequence
│
├── memory/
│   ├── models.py               # Conversation, Message, Decision, Pattern
│   ├── schemas.py
│   └── retrieval.py            # Build context window from vault + memory
│
├── agent/
│   ├── graph.py                # LangGraph compile
│   ├── state.py                # TypedDict
│   ├── nodes/
│   │   ├── analyzer.py         # Full-picture snapshot, turn classification
│   │   ├── strategist.py       # Wealth-vehicle prioritization, debt vs invest tension
│   │   ├── coach.py            # Explains the why; names the principle
│   │   ├── tracker.py          # Trajectory vs goals; drift detection
│   │   ├── alert.py            # Proactive triggers (surplus, missed pmt risk, unused room)
│   │   └── synthesizer.py      # Compose final response; enforce CFO POV + disclaimer
│   ├── principles.py           # Named wealth principles registry (debt avalanche,
│   │                           # tax arbitrage, time-in-market, etc.)
│   ├── prompts.py              # Centralized prompts, cached on vault snapshot
│   └── tools.py                # Function-calling tools (scenario modeler, etc.)
│
├── scenarios/
│   ├── engine.py               # Deterministic forward-projection math
│   └── models.py               # ScenarioInput / ScenarioOutput
│
├── routers/
│   ├── chat.py                 # POST /chat
│   ├── vault.py                # CRUD on all vault entities
│   ├── memory.py               # Decisions + patterns CRUD
│   ├── digest.py               # GET /digest/latest, POST /digest/run-now
│   ├── scenarios.py            # POST /scenarios/run
│   ├── wealth.py               # GET /wealth/position, GET /wealth/trajectory
│   └── plaid.py                # (phase 2) Link, webhook, sync
│
├── worker/
│   └── cron.py                 # APScheduler — weekly digest, quarterly alerts
│
├── static/
│   ├── index.html              # Chat UI
│   ├── vault.html              # Vault edit forms
│   ├── goals.html              # Goal progress + trajectory
│   ├── scenarios.html          # Scenario modeler UI
│   └── digest.html             # Latest digest view
│
├── tests/
│   ├── conftest.py
│   ├── test_vault.py
│   ├── test_wealth_position.py
│   ├── test_agent.py
│   ├── test_memory.py
│   ├── test_scenarios.py
│   ├── test_digest.py
│   ├── test_chat.py
│   ├── test_disclaimer.py      # Structural: disclaimer present when required
│   └── eval/                   # Agent eval harness — canned vault states + expected facts
│       └── scenarios/*.yaml
│
└── docs/
    ├── PRD.md
    ├── SOT.md
    ├── DECISIONS.md
    ├── PROJECT_STATE.md
    ├── issues.md
    ├── THREAT_MODEL.md
    ├── WEALTH_PRINCIPLES.md    # Named-principle definitions the Coach cites
    └── DEPLOYMENT.md
```

## Data Model (initial)

```
accounts
  id, type (checking/savings/credit/loan/retirement/cash/business),
  institution, nickname, current_balance_encrypted,
  last_synced_at, plaid_account_id (nullable), status, created_at

cards
  id, account_id (FK), issuer, network, last4_encrypted,
  benefits_jsonb, credit_limit, statement_day, due_day, autopay,
  current_cycle_spend, status, created_at

income_streams
  id, source, source_type (w2/1099/cash/gig/coaching/business/other),
  cadence (weekly/biweekly/monthly/irregular),
  typical_gross_amount_encrypted, tax_treatment_jsonb,
  rolling_4wk_avg_encrypted (computed), notes, status, created_at

expenses
  id, name, category, cadence, typical_amount_encrypted,
  account_id (FK), card_id (FK), active, created_at

debts
  id, name, balance_encrypted, apr, minimum_payment_encrypted,
  strategy (avalanche/snowball/custom), priority_rank, status, created_at

assets
  id, kind (vehicle/equipment/other), nickname,
  value_estimate_encrypted, notes, created_at

real_estate                          # NEW vs v1
  id, address_encrypted, purchase_price_encrypted, current_value_encrypted,
  mortgage_balance_encrypted, mortgage_apr, monthly_payment_encrypted,
  property_type (primary/rental/other), monthly_rent_encrypted (nullable),
  equity_estimate_encrypted (computed), created_at

business_income                      # NEW vs v1
  id, business_name, entity_type (sole_prop/llc/scorp/other),
  monthly_revenue_encrypted, monthly_expenses_encrypted,
  net_margin_encrypted (computed), notes, status, created_at

retirement_accounts                  # NEW vs v1
  id, kind (roth_ira/traditional_ira/401k/solo_401k/sep_ira/hsa),
  institution, ytd_contribution_encrypted, balance_encrypted,
  ytd_contribution_limit_remaining (computed via tax-year rules),
  notes, created_at

goals
  id, title, kind (emergency_fund/debt_payoff/roth_max/solo_401k_max/
                   index_fund_contribution/real_estate_down/business_milestone/
                   net_worth/custom),
  target_amount_encrypted, current_amount_encrypted (computed),
  deadline, priority, status, created_at

career_position                      # NEW vs v1
  id, current_role, current_employer, current_comp_total_encrypted,
  target_role, target_comp_total_encrypted, target_date,
  cert_or_milestone_jsonb, notes, updated_at

transactions                         # Phase 2 (Plaid)
  id, account_id, posted_at, amount_encrypted, merchant,
  category, raw_payload_jsonb

conversations
  id, started_at, summary

messages
  id, conversation_id, role (user/agent),
  content, tokens_in, tokens_out, latency_ms,
  cited_principle (nullable), cited_vault_refs_jsonb, created_at

decisions
  id, decided_at, summary, principle, expires_at (nullable),
  status (active/superseded/abandoned)

patterns                             # Agent-detected drift / opportunities / alerts
  id, detected_at, kind (surplus/drift/missed_pmt_risk/unused_room/career_off_pace),
  severity, summary, vault_refs_jsonb, acknowledged_at

audit_log
  id, at, actor, action, entity_type, entity_id, before_jsonb, after_jsonb
```

## Agent Architecture (LangGraph)

```
                  ┌──────────────┐
   user turn  ──► │  Retrieval   │  vault snapshot + active decisions + recent patterns +
                  └──────┬───────┘  wealth_position + relevant memory
                         ▼
                  ┌──────────────┐
                  │   Analyzer   │  classify the turn; identify which downstream nodes fire
                  └──────┬───────┘
                         ▼
              ┌──────────┼──────────┐
              ▼          ▼          ▼
        ┌──────────┐ ┌──────┐ ┌──────────┐
        │Strategist│ │Coach │ │   Alert  │   (conditional; one or more fire)
        └────┬─────┘ └──┬───┘ └─────┬────┘
             └──────────┼───────────┘
                        ▼
                 ┌──────────────┐
                 │   Tracker    │  trajectory vs goals; off-pace flagging
                 └──────┬───────┘
                        ▼
                 ┌──────────────┐
                 │ Synthesizer  │  one committed recommendation; reasoning;
                 └──────┬───────┘  named principle; disclaimer when required
                        ▼
                 ┌──────────────┐
                 │   Persist    │  messages, new decisions, new patterns, audit
                 └──────────────┘
```

## Security Posture (v1)

- Fernet on all sensitive columns; key in env, never in code, never in git
- TLS in transit via Cloudflare Tunnel
- Full-disk encryption on the host VM
- No third-party analytics or error reporters with payloads
- Audit log on every read/write of vault entities; append-only at the app layer
- Anthropic prompts redact account numbers and exact dollar balances unless arithmetic precision is required — pass rounded aggregates by default
- Backups encrypted with a separate key, stored off-host
- Disclaimer enforced by structural test, not just prompt convention

## Known Production Gaps

- `VAULT_ENCRYPTION_KEY` rotation runbook not written
- No rate limiting on `/chat` (single-user, but LLM cost ceiling matters)
- Plaid deferred; sync gaps when added
- Agent eval harness (`tests/eval/`) covers happy paths only; needs adversarial coverage
- Digest email has no opt-out or pause mechanism
- No external monitoring/alerting wired up

---

# 4. Wealth-Building Framework

The agent always reasons against this sequence. It must know which step the user is on and surface the next move accordingly. Encoded in `vault/wealth_position.py` and visible to the agent on every turn.

```
Step 1 — Stability          Emergency fund (3–6 months expenses) in cash/HYSA
Step 2 — Eliminate Drag     All high-interest debt (typically >7–8% APR) eliminated
Step 3 — Tax-Advantaged     Roth IRA maxed ($7k/year for 2026; verify annually)
                            Solo 401k for self-employed income (up to ~$69k/year; verify)
                            HSA if eligible (triple tax-advantaged)
Step 4 — Market Exposure    Consistent index-fund contribution (taxable brokerage)
Step 5 — Leverage           Real estate / rental property
Step 6 — Ownership          Business income that doesn't require your time
```

**Named principles the Coach cites** (lives in `docs/WEALTH_PRINCIPLES.md`):

- Emergency fund first — eliminates forced bad decisions under stress
- Debt avalanche — pay highest APR first; mathematically optimal
- Time-in-market — compounding requires consistency; timing is luck
- Tax arbitrage — pre-tax/Roth/taxable bucket selection by horizon and bracket
- Employer match capture — never leave free money
- Solo 401k for 1099 income — most gig workers don't know they qualify
- Lifestyle creep avoidance — direct raises to investment vehicles, not spend
- Career income as wealth lever — comp delta invested early beats most other moves
- Real estate leverage — your money controlling more money, with cash flow
- Business income compounding — separating earning from time-spent

**The agent's job is not to teach a class.** It cites the principle in one sentence per recommendation. The user can ask "explain that more" to get the longer lesson on demand.

---

# 5. Open-Ended Questions — Answered

Each subsection answers a question from the brief. `<PLACEHOLDER>` markers are where you must fill in before Issue 1.

## 5.1 The Real Goal

**Q: What does winning in 5 years look like?**
A: **TODO — owner to fill.** Templates were drafted (Career + Index Funds / First Rental + Saver / Coaching Business + Market) but the owner flagged them as not matching current life state. This is the product's strategic north star and must be the owner's own words. Until filled, the Strategist falls back to optimizing the wealth-building sequence (Section 4) one step at a time — that's a safe default but loses long-horizon calibration. Fill before Issue 8 (Strategist node) at the latest.

Suggested format when filling:
- Net worth: $___
- Passive monthly income: $___/mo
- First rental property by year: ___
- Business revenue: $___/yr
- Roth balance: $___
- Index fund balance: $___
- Career: target role / target comp / target date

**Q: What's your actual monthly surplus right now?**
A: **Unknown — computed by Issue 4's first deliverable.** Once the vault is populated (every account, income stream, recurring expense, minimum debt payment), the system computes surplus directly: `sum(rolling_4wk_avg of income_streams) − sum(typical_amount of active expenses) − sum(minimum_payment of active debts)`. Don't pre-fill a guess here — the whole point of the vault is to surface the real number.

**Q: Most urgent wealth vehicle right now?**
A: **TBD by Issue 5's `wealth_position` computation.** Once the vault has emergency fund, debt APRs, retirement balances, and YTD contributions, `vault/wealth_position.py` returns a deterministic step (1–6) and the next move falls out of it. Strong candidate to investigate first given the brief's 1099 income from DoorDash + coaching: the Solo 401(k) — most gig workers don't know they qualify, and contribution headroom there typically exceeds the Roth IRA limit by an order of magnitude. Agent confirms against current debt/emergency-fund state before recommending.

## 5.2 Data Completeness

**Q: Every account, card, income stream, debt — list it.**
A: **Captured row-by-row by the vault in Issue 4** (CRUD endpoints + HTMX forms), not pre-typed here. This section is a completeness checklist for the owner — confirm you can name every:
- **Income stream** (W-2, 1099, cash, gig, coaching, business) with cadence and typical amount
- **Account** (checking, savings, HYSA, retirement at every institution, cash, business)
- **Card** (issuer, network, statement day, due day, limit, category multipliers)
- **Debt** (balance, APR, minimum, current strategy)
- **Real estate / asset** with equity / value estimate
- **Goal** with target amount and deadline

Known from the brief: Cognizant W-2 (biweekly), DoorDash 1099 (~3 evenings/week, irregular), coaching cash. Everything else is filled into the vault during Issue 4. Don't dual-write a copy here — the vault is the source of truth.

**Q: DoorDash + coaching income range and variability?**
A: Captured in `income_streams.rolling_4wk_avg_encrypted` (computed) once the user logs 4+ weeks of actual receipts. Vault forms (Issue 4) accept best/worst/typical amounts at create time as a forecast prior until rolling data accumulates.

**Q: Non-bank-account assets?**
A: Captured in the `assets` and `real_estate` tables (Issue 2 schema, Issue 4 CRUD). Car value, work equipment, anything else material.

## 5.3 Wealth Strategy Layer

**Q: Agent has a point of view, or just presents options?**
A: **CFO with a point of view.** The synthesizer commits to one recommendation. If the user wants alternatives, they ask "what else could I do" and the agent enumerates with reasoning.

**Q: How does the agent handle the debt-payoff vs invest-now tension?**
A: Encoded heuristic, transparent and overridable:
- Debt with APR ≥ 7%: pay off before any non-match investing
- Debt with APR 4–7%: case-by-case based on user's risk tolerance and timeline; agent surfaces the math
- Debt with APR < 4%: minimum payments; redirect surplus to investing
- Employer 401k match is always first dollar regardless of debt (it's a 100% instant return)
- This heuristic is documented in `docs/WEALTH_PRINCIPLES.md`; user can override via a decision row

**Q: Career income as a wealth lever — agent tracks it?**
A: Yes. `career_position` table stores current and target role/comp/date. Strategist factors target comp into long-horizon planning. Tracker flags off-pace.

## 5.4 Intelligence & Teaching

**Q: Recommendation vs lesson?**
A: A **recommendation** is one sentence stating the action. A **lesson** is the one-sentence principle that makes it correct. Every Coach output emits both. The longer-form lesson is on demand only — the user asks "explain that more" and gets the `WEALTH_PRINCIPLES.md` entry expanded into a coaching paragraph.

**Q: How do you avoid confidently wrong advice?**
A: Four layers.
1. **Prompt-level refusal** for state-specific tax rules, legal advice, investment trade execution → "I'm not the right tool for this; here's what to ask a CPA/CFP."
2. **Source-grounded answers** for anything provable from the vault → synthesizer cites the rows it used.
3. **Year-versioned tax constants** (Roth limit, Solo 401k limit, mileage rate) updated annually in `agent/principles.py`; agent says "for 2026..." every time.
4. **Eval harness** — `tests/eval/scenarios/*.yaml` with expected facts that must appear/not appear; runs before every deploy.

**Q: Proactive vs reactive triggers?**
A: Proactive (Alert node):
- Surplus detected (MTD inflow − committed outflow > threshold)
- Minimum payment due within 3 days, no scheduled transfer
- Roth or Solo 401k room unused with <90 days to year-end
- Category spend exceeds rolling 3mo average by **25%** (env-tunable via `ALERT_DRIFT_PCT_THRESHOLD`)
- Income stream rolling-4wk-avg drops **30%** (env-tunable via `ALERT_INCOME_DROP_PCT_THRESHOLD`)
- Career off-pace: elapsed time / target time > delta-comp-achieved / delta-comp-target

Reactive (chat only):
- Card-of-choice questions
- Scenario modeling
- Principle deep-dive
- Long-form coaching

## 5.5 Memory

**Q: How does the agent remember decisions?**
A: `decisions` table. Synthesizer emits `{decision: {...}}` side-output; post-processor persists it. Retrieval node loads active decisions into context on every turn. Decisions transition `active → superseded → abandoned`; never deleted.

**Q: How does goal progress survive a changing situation?**
A: `goals.current_amount_encrypted` is a computed view, not a stored value — it derives from the underlying vault state each turn. When the user's situation changes (income drops, expense added), trajectory recomputes automatically and Tracker flags drift.

**Q: What's the agent's core financial model of the user?**
A: The vault schema in Section 3 + active rows of `decisions` + active rows of `patterns` + `career_position` + `wealth_position` computed view. The full vault snapshot is the prompt-cache key — Anthropic prompt caching reuses it until any row changes.

## 5.6 Security

**Q: Threat model?**
A: In order of likelihood:
1. Device theft with active session → short JWT TTL + full-disk encryption + Fernet on sensitive columns
2. Accidental `.env` git push → `.gitignore` + pre-commit hook + key never in code
3. Backup file leak → encrypted with separate key, stored off-host
4. Anthropic log retention → prompts redact precise balances + account numbers; only aggregates/last-4s leave the system
5. Plaid breach (phase 2) → out of our hands; rotate access tokens on signal

Out of scope: nation-state, insider threat at Anthropic, supply-chain compromise.

**Q: Plaid tokens — storage + rotation?**
A: Stored encrypted in `accounts.plaid_access_token_encrypted`. Rotated on Plaid `ITEM_LOGIN_REQUIRED` webhook; user re-links via standard Link flow.

**Q: Does single-user-forever change the posture?**
A: Yes — no GDPR/CCPA, no breach-notification obligation, no SOC2. The above posture is appropriate. **If a second user is ever invited, redo `docs/THREAT_MODEL.md` before the invite.**

## 5.7 Build Scope

**Q: Personal-only or product?**
A: **Personal-only v1.** Schema includes `user_id` foreign keys so multi-user is mechanical later, but no additional auth, no sharing, no compliance work in v1.

**Q: The one thing that would make this indispensable on day one?**
A: **"Tell me where I am in the wealth-building sequence and what my next move is."** Anchors every chat turn on Section 4's six steps. The agent always knows the current step (computed by `wealth_position`) and surfaces the next move. This makes the product unique vs trackers ("here's what you spent") and optimizers ("use this card") — both of which can't tell you *where you are* or *what to do next* in a sequence that compounds wealth.

**Q: What does v1 look like?**
A: Manual vault + chat agent + wealth-position computation + weekly digest + scenario modeling. **No Plaid.** Ship the loop that proves "complete context + good AI = a real CFO" using only manually-entered data. Plaid is a partial automation of that, not a prerequisite.

---

# 6. Starting Issue Backlog

Dependency-ordered. Each issue follows Check → Approve → Build → Review (Section 7).

---

**Issue 1: Repo scaffold + Docker Compose + health endpoint**
**Depends on**: none
**What**: New repo with `CLAUDE.md` (Section 8), `requirements.txt`, `Dockerfile`, `docker-compose.yml` (`app` + `postgres` + `redis`), `main.py` with `/health`, `config.py` env loading, `disclaimer.py` with the canonical text.
**Acceptance criteria**:
- [ ] `docker compose up` brings all three services healthy
- [ ] `GET /health` returns `{status: "ok", postgres: "ok", redis: "ok"}`
- [ ] `.env.example` lists every var from SOT
- [ ] `pytest` passes with a `/health` smoke test
- [ ] Disclaimer text loadable from `disclaimer.py`

---

**Issue 2: Postgres schema + Alembic + encryption helper**
**Depends on**: 1
**What**: SQLAlchemy models for every vault entity (Section 3 data model) + memory tables. Alembic wired. `crypto.py` with Fernet `encrypt()`/`decrypt()` from `VAULT_ENCRYPTION_KEY`.
**Acceptance criteria**:
- [ ] `alembic upgrade head` creates every table including `real_estate`, `business_income`, `retirement_accounts`, `career_position`
- [ ] Encrypted round-trip test passes
- [ ] Missing `VAULT_ENCRYPTION_KEY` fails app start with a clear error
- [ ] Audit log table append-only at the app layer

---

**Issue 3: Single-user auth (JWT)**
**Depends on**: 2
**What**: `/auth/register` (rejects after first user), `/auth/token`, `get_current_user` dependency. bcrypt + PyJWT.
**Acceptance criteria**:
- [ ] Register allowed once, 409 thereafter
- [ ] Token endpoint returns valid JWT with configured expiry
- [ ] Protected routes 401 without token

---

**Issue 4: Vault CRUD + minimal HTMX UI**
**Depends on**: 3
**What**: CRUD endpoints for every vault entity. HTMX forms in `static/vault.html`. Includes the new entities (real estate, business income, retirement accounts, career position).
**Acceptance criteria**:
- [ ] Every entity from Section 3 CRUDable via API
- [ ] Closing an entity writes an audit log row
- [ ] HTMX form for at least cards + retirement accounts + career position renders and persists
- [ ] Tests cover CRUD happy paths + 404/401

---

**Issue 5: Wealth-position computation + endpoint**
**Depends on**: 4
**What**: `vault/wealth_position.py` computes the user's current step on the wealth-building sequence (Section 4). `GET /wealth/position` returns it. `GET /wealth/trajectory` returns next-move + open gaps.
**Acceptance criteria**:
- [ ] Function returns a deterministic step (1–6) given any vault state
- [ ] Unit tests cover boundary cases (e.g., emergency fund exactly at 3 months)
- [ ] Endpoint returns `{step, step_name, next_move, open_gaps}`
- [ ] No LLM call needed — pure data logic

---

**Issue 6: Anthropic singleton + retrieval node**
**Depends on**: 5
**What**: `clients.py` with one Anthropic client. `memory/retrieval.py` builds a "User Profile" prompt-cache block from vault snapshot + active decisions + wealth_position.
**Acceptance criteria**:
- [ ] Module-level Anthropic client; fail-fast on missing key
- [ ] Retrieval output deterministic (same input → same output)
- [ ] Cache control headers on the profile block
- [ ] Two consecutive identical calls show cache hit on second

---

**Issue 7: Minimal LangGraph — Retrieval → Synthesizer → Persist**
**Depends on**: 6
**What**: Single-path graph end-to-end. `/chat` endpoint accepts a question, returns `{recommendation, reasoning, principle, disclaimer?}`. Disclaimer included when the response touches tax/legal/investment specifics — enforced by `disclaimer.py`.
**Acceptance criteria**:
- [ ] `POST /chat {"message": "..."}` returns structurally valid response
- [ ] Conversation + message rows persisted
- [ ] Latency, tokens, cited principle logged
- [ ] Disclaimer present on tax/legal/investment turns (structural test)

---

**Issue 8: Analyzer + Strategist + Coach nodes**
**Depends on**: 7
**What**: Add Analyzer (turn classification), Strategist (wealth-vehicle prioritization given `wealth_position`), Coach (principle citation). Conditional routing.
**Acceptance criteria**:
- [ ] "Where should I put $500 surplus" routes Analyzer → Strategist → Coach → Synthesizer
- [ ] "Explain debt avalanche" routes Analyzer → Coach → Synthesizer
- [ ] Each node logs its own latency/tokens
- [ ] Synthesizer commits to one recommendation; refuses to enumerate unless asked

---

**Issue 9: Decisions persistence + retrieval respects them**
**Depends on**: 8
**What**: Synthesizer emits `decision` side-output. Persist. Retrieval pulls active decisions into prompt context.
**Acceptance criteria**:
- [ ] "I'm maxing Roth before saving for property" persists a decision
- [ ] Next turn references Roth-first without re-asking
- [ ] `PATCH /memory/decisions/:id` marks `superseded`
- [ ] Round-trip test passes

---

**Issue 10: Tracker + Alert nodes**
**Depends on**: 9
**What**: Tracker computes trajectory vs goals + career off-pace. Alert fires on surplus, missed-payment risk, unused tax-advantaged room, drift, income drop, career off-pace. Both append to response when triggered; both persist to `patterns`.
**Acceptance criteria**:
- [ ] Surplus alert fires when threshold exceeded
- [ ] Unused-Roth-room alert fires within 90 days of year-end if applicable
- [ ] Career off-pace alert fires when elapsed-fraction > delta-achieved-fraction
- [ ] Tests cover each path

---

**Issue 11: Scenario modeling engine + endpoint + UI**
**Depends on**: 10
**What**: `scenarios/engine.py` does deterministic forward-projection ("$X/month → when do I hit $Y", "drop DoorDash to 2 nights → revised monthly + revised trajectory"). `POST /scenarios/run`. `static/scenarios.html` simple form.
**Acceptance criteria**:
- [ ] Two canonical scenario types implemented: time-to-target, income-change
- [ ] Output includes reasoning trace and assumed constants
- [ ] Disclaimer attached when projection touches investment growth assumptions
- [ ] Tests cover both scenario types

---

**Issue 12: Weekly digest cron + email**
**Depends on**: 11
**What**: APScheduler worker. `digest.py` pulls week's vault state + new patterns + wealth_position + trajectory and emails a Markdown summary.
**Acceptance criteria**:
- [ ] `POST /digest/run-now` generates and sends a digest
- [ ] Cron fires weekly at configured time
- [ ] Digest includes: cash position, week-over-week change, current step + next move, new alerts, one action item
- [ ] End-to-end test with mocked SMTP

---

**Issue 13: Plaid integration (deferred — open separately)**
**Depends on**: 12
**What**: Plaid Link flow, link-token endpoint, item exchange, account + transaction sync, webhook handler.
**Acceptance criteria**:
- [ ] User links an institution via Plaid Link
- [ ] Linked accounts and transactions populate the vault (does not overwrite manual entries — linked status is separate)
- [ ] `ITEM_LOGIN_REQUIRED` surfaces a re-link prompt
- [ ] Plaid access tokens encrypted at rest

---

**Issue 14+: Eval harness, monitoring, key-rotation runbook, opt-out controls**
(See SOT "Known Production Gaps" — each becomes its own issue when the core loop is shipped.)

---

# 7. Project Workflow & Required Commands

The workflow you'll use in the new repo. Mirrors LIVABILITY's discipline.

## 7.1 Four-Phase Issue Workflow

Run this loop for every issue. Do not start Issue N+1 until Issue N has cleared all four phases.

### Phase 1 — CHECK
Research the industry-standard approach for every non-trivial pattern. Look up current best practices. Present a brief in this exact format:

> **Issue N — [title]**
> **Approach:** [specific pattern, library, or architecture]
> **Why for this project:** [1–2 sentences tying to stack/constraints]
> **Alternatives ruled out:** [what we considered and why it lost]
> **Good to go?**

### Phase 2 — APPROVE
Wait for explicit confirmation. If approach changes during discussion, that's a candidate for `docs/DECISIONS.md`.

### Phase 3 — BUILD
- Follow all Coding Principles and Production Standards.
- Write tests alongside the code.
- Run full test suite before Phase 4.

### Phase 4 — REVIEW & ASSESS

**Resource lifecycle**
- [ ] DB sessions opened via context manager, guaranteed to close
- [ ] External clients (Anthropic, Plaid, SMTP) module-level singletons
- [ ] Test resources cleaned up

**Path and config safety**
- [ ] All file paths absolute
- [ ] All new config in `.env.example` with description
- [ ] Nothing belonging in `.gitignore` left unignored

**Code cleanliness**
- [ ] No TODO, commented blocks, debug statements
- [ ] No duplicated logic
- [ ] Every new function typed

**Security (load-bearing for this project)**
- [ ] Every sensitive-field read uses `decrypt()`
- [ ] No balance, account number, or token in any log
- [ ] Anthropic prompts reviewed for sensitive-field leakage
- [ ] Audit log row on every vault mutation
- [ ] Disclaimer present where required (structural test green)

**Wealth-strategy correctness (CFO-specific)**
- [ ] Every Strategist recommendation cites a named principle from `docs/WEALTH_PRINCIPLES.md`
- [ ] Year-versioned tax constants (Roth limit, Solo 401k limit, mileage rate) sourced from `agent/principles.py`, not inlined
- [ ] Synthesizer commits to one recommendation (does not enumerate unless asked)
- [ ] No state-specific tax/legal advice without refusal + CPA/CFP pointer

**Docs**
- [ ] `docs/SOT.md` updated if stack/schema/structure changed
- [ ] `docs/DECISIONS.md` updated if implementation diverged
- [ ] `docs/WEALTH_PRINCIPLES.md` updated if a new principle is cited

**Close out**
- [ ] All acceptance criteria checked off
- [ ] `docs/PROJECT_STATE.md` updated

## 7.2 Slash Commands & Skills to Use

| Command | When to use it |
|---|---|
| `/init` | Once at repo creation. You can also paste Section 8 directly. |
| `/issue-workflow` | At the start of every issue. Walks the Check → Approve → Build → Review loop. |
| `/best-practices` | Designing any non-trivial pattern (agent state machine, encryption boundary, scenario engine math). |
| `/production-principles` | Before Phase 1 of any issue touching auth, data, or money. |
| `/production-standard` | Phase 4 sanity check that code meets production bar. |
| `/production-code` | Code-level production review of a specific module. |
| `/production-security` | **Every issue touching the vault, retirement accounts, Plaid tokens, audit log, or disclaimer.** Non-negotiable. |
| `/production-tech` | Picking a new dependency or framework. |
| `/production-process` | Adjusting CI/CD, deployment, ops processes. |
| `/code-review` | On the diff before pushing each issue's final commit. `--comment` posts to PR. |
| `/review` | On a PR before merge. |
| `/security-review` | **Every branch before merging to main.** Required for this project's data class. |
| `/verify` | After Phase 3 to drive the change in the running app. Tests prove correctness; this proves the feature works. |
| `/run` | Spin up the app for manual driving (chat, vault, scenario modeler, digest). |
| `/claude-api` | Any time you write or modify an Anthropic SDK call — keeps prompt caching, model IDs, tool-use patterns correct. |
| `/session-start-hook` | Once if running on Claude Code on the web — sets up SessionStart hook for tests/linters in cloud sessions. |
| `/update-config` | Adjusting `.claude/settings.json` permissions, hooks, env vars. |
| `/fewer-permission-prompts` | Periodically; scans transcripts and allowlists safe Bash/MCP calls. |
| `/loop` | Recurring tasks during dev (e.g., `/loop 30m /check-ci`). Not for the weekly digest — use APScheduler. |

## 7.3 Pre-Deploy Checklist

**Gate 1 — Automated**
```
pytest
```
Zero failures. Eval harness in `tests/eval/` green.

**Gate 2 — Manual smoke test**
```
docker compose up
```
Drive the change at `http://localhost:8000`:
- [ ] Happy path works end-to-end
- [ ] Edge cases from acceptance criteria behave
- [ ] Disclaimer visible where required
- [ ] No regression in adjacent features (chat, vault, scenarios, digest)
- [ ] Browser console clean

## 7.4 Coding Principles

- **DRY** — extract any logic used more than once
- **SOLID** — invoke `/best-practices` for depth
- **KISS** — simplest solution that meets acceptance criteria; >30-line function = probably split
- **Industry standard unless overridden** — FastAPI idioms, Anthropic SDK best practices (prompt caching, structured output, token limits), LangGraph patterns. Deviations get a `docs/DECISIONS.md` entry.

## 7.5 Production Standards

- No hardcoded secrets. `.env` only.
- All config via `python-dotenv`; fail fast on missing required.
- `logging` module only — no `print()`.
- Proper HTTP status codes.
- Pydantic on every endpoint.
- Error messages safe — no stack traces, no DB errors to client.
- `requirements.txt` pinned with `==`.
- **Project-specific**: every log line and every LLM prompt reviewed for sensitive-field leakage; every tax/investment-touching response carries the disclaimer.

## 7.6 Testing Rules

- Full pytest run before every issue close
- Tests for new behavior written alongside the code
- 80/20: happy path + load-bearing edge cases
- Tests live in `tests/`, mirror source structure
- No mocking the DB — use a real test Postgres via docker-compose
- Test the API surface end-to-end with FastAPI `TestClient`
- **Agent eval harness** — `tests/eval/scenarios/*.yaml`: canned vault state + expected facts (must-appear and must-not-appear); runs before every `agent/` change

---

# 8. CLAUDE.md Template

Drop into the new repo's root as `CLAUDE.md`.

```markdown
# CLAUDE.md — PERSONAL CFO Project Rules

These rules govern every session. They override default Claude Code behavior where noted.

---

## Disclaimer (must appear in every interface and the system prompt)

This tool is for financial education and personal organization. It is not a
licensed financial advisor. For tax strategy, real estate transactions, and
investment decisions, consult a licensed professional.

---

## Read Order (Every Session)

Before writing a single line of code, read these files in order:

1. `docs/SOT.md` — current stack, architecture, file structure
2. `docs/PROJECT_STATE.md` — which issues are done, in progress, or blocked
3. `docs/issues.md` — the issue being worked
4. `docs/DECISIONS.md` — any deviations from PRD already made
5. `docs/THREAT_MODEL.md` — security posture (data is sensitive)
6. `docs/WEALTH_PRINCIPLES.md` — named principles the Coach cites

If any are missing or stale, flag it before proceeding.

---

## Project Structure

Canonical layout is enforced. Do not create files outside it without updating `docs/SOT.md` first. See `docs/SOT.md` for the full tree.

Rules:
- Python source lives at root, in `routers/`, `vault/`, `memory/`, `agent/`, `scenarios/`, or `worker/` — nowhere else
- Frontend assets go in `static/`
- All documentation goes in `docs/`
- Tests mirror source structure in `tests/`

---

## Source of Truth Files

| File | Purpose | Updated when |
|---|---|---|
| `docs/PRD.md` | Requirements | Rarely; only on formal scope change |
| `docs/SOT.md` | Architecture | Any time stack/schema/structure changes |
| `docs/DECISIONS.md` | Deviation log | Any architectural decision diverging from PRD |
| `docs/PROJECT_STATE.md` | Progress | Every time an issue is completed |
| `docs/issues.md` | Work queue | Check `[ ]` → `[x]` when an issue is done |
| `docs/THREAT_MODEL.md` | Security posture | Any time data classes / threat surface / auth changes |
| `docs/WEALTH_PRINCIPLES.md` | Named principles registry | Any time a new principle is cited by the Coach |

---

## Issue Workflow — Check → Approve → Build → Review & Assess

One issue at a time. Do not begin Issue N+1 until Issue N clears all four phases.

### Phase 1 — CHECK
Research industry-standard approach. Present a brief:

> **Issue N — [title]**
> **Approach:** [specific pattern]
> **Why for this project:** [1–2 sentences]
> **Alternatives ruled out:** [what we considered]
> **Good to go?**

### Phase 2 — APPROVE
Wait for explicit confirmation. Capture changed approaches in `docs/DECISIONS.md`.

### Phase 3 — BUILD
- Follow Coding Principles and Production Standards
- Write tests alongside code
- Run full test suite before Phase 4

### Phase 4 — REVIEW & ASSESS

**Resource lifecycle**
- [ ] DB sessions via context manager, guaranteed to close
- [ ] External clients (Anthropic, Plaid, SMTP) module-level singletons
- [ ] Test resources cleaned up

**Path and config safety**
- [ ] All paths absolute
- [ ] All new config in `.env.example` with description
- [ ] Nothing belonging in `.gitignore` left unignored

**Code cleanliness**
- [ ] No TODO, commented blocks, debug
- [ ] No duplicated logic
- [ ] Every new function typed

**Security (this project is finance — extra weight)**
- [ ] Every sensitive-field read uses `decrypt()`
- [ ] No balance, account number, or token in any log
- [ ] Anthropic prompts reviewed for sensitive-field leakage
- [ ] Audit log row written for every vault mutation
- [ ] Disclaimer enforcement test green

**Wealth-strategy correctness**
- [ ] Every Strategist recommendation cites a named principle from `docs/WEALTH_PRINCIPLES.md`
- [ ] Year-versioned tax constants sourced from `agent/principles.py`
- [ ] Synthesizer commits to one recommendation (not a list)
- [ ] No state-specific tax/legal advice without refusal + CPA/CFP pointer

**Docs**
- [ ] `docs/SOT.md` updated if stack/schema/structure changed
- [ ] `docs/DECISIONS.md` updated if implementation diverged
- [ ] `docs/WEALTH_PRINCIPLES.md` updated if a new principle is cited

**Close out**
- [ ] All acceptance criteria checked off
- [ ] `docs/PROJECT_STATE.md` updated

---

## Coding Principles

> Invoke `/best-practices` for deep guidance.

### DRY
Extract any logic used more than once.

### SOLID
Single Responsibility, Open/Closed, Liskov, Interface Segregation, Dependency Inversion.

### KISS
Simplest solution wins. No premature abstractions. >30-line function = probably split.

### Industry Standard Unless Overridden
- FastAPI-idiomatic backend
- Anthropic SDK best practices (prompt caching, structured output, token limits)
- LangGraph patterns for agent orchestration
- Any deviation requires a `docs/DECISIONS.md` entry

---

## Production Standards

- No hardcoded secrets. `.env` only, never committed.
- All config via `python-dotenv`. Fail fast on missing required.
- `logging` module only — no `print()`.
- Proper HTTP status codes (200, 400, 401, 404, 422, 500/502).
- Pydantic on every endpoint.
- Error messages safe.
- `requirements.txt` pinned with `==`.
- **Finance-specific**: every log line and every LLM prompt reviewed for sensitive-field leakage; every tax/investment-touching response carries the disclaimer.

---

## Testing Rules

- Full pytest run before every issue close
- Tests for new behavior written with the code
- 80/20: happy path + load-bearing edges
- `tests/` mirrors source structure
- No DB mocking — use real Postgres via docker-compose
- API-surface end-to-end with FastAPI `TestClient`
- **Agent eval harness** in `tests/eval/` — canned scenarios with expected facts; runs before every `agent/` change

---

## Production Deployment

Runs in Docker Compose on <PLACEHOLDER: target host, e.g., the Oracle Cloud Free ARM VM> with traffic via Cloudflare Tunnel to <PLACEHOLDER: domain>.

Deploy:
\`\`\`bash
ssh <user>@<host>
cd ~/personal-cfo
git pull origin main
docker compose pull && docker compose up -d
\`\`\`

Status:
\`\`\`bash
docker compose ps
docker compose logs --tail 100 app
\`\`\`

### Pre-Deploy Checklist

**Gate 1**: `pytest` (including `tests/eval/`) — zero failures.
**Gate 2**: `docker compose up` locally, exercise the change in the browser, confirm happy path + edge cases + disclaimer visibility + no console errors.

Only then deploy.

---

## Code Style

- Python: PEP 8, max 100 chars, type hints on every signature
- HTML/JS: HTMX + vanilla JS, 2-space indentation
- SQL: uppercase keywords, lowercase identifiers, parameterized queries always
- Comments only when WHY is non-obvious
- Naming: `snake_case` Python, `camelCase` JS, `UPPER_SNAKE` constants

---

## Architecture Constraints

- Backend: FastAPI + Python 3.13+
- Agent: LangGraph (Analyzer, Strategist, Coach, Tracker, Alert, Synthesizer)
- LLM: Anthropic SDK with prompt caching mandatory; token usage logged after every call
- DB: PostgreSQL 16 + Alembic; Redis 7 for agent state
- Encryption: Fernet on sensitive columns
- Frontend: Vanilla HTML + HTMX (no build step)
- Containerization: Docker Compose
- Deployment: Cloudflare Tunnel from a host machine

Deviations require a `docs/DECISIONS.md` entry before implementation.

---

## Wealth-Strategy Rules (project-specific)

- The agent is a **CFO with a point of view** — synthesizer commits to one recommendation; refuses to enumerate options unless explicitly asked
- Every Strategist output cites a named principle from `docs/WEALTH_PRINCIPLES.md`
- Year-versioned tax constants (Roth limit, Solo 401k limit, mileage rate) live in `agent/principles.py` and are stamped with the year — agent says "for <year>..." every time
- State-specific tax/legal advice → refusal + CPA/CFP pointer, every time
- The disclaimer is mandatory on any response touching tax, legal, or investment specifics (structural test enforces this)

---

## Pre-General-Availability Requirements

This is personal-only in v1. Before any second user is invited:

- Redo the threat model in `docs/THREAT_MODEL.md`
- Add per-user data isolation tests
- Add per-user rate limiting and quotas
- Add ToS and Privacy Policy
- Document key-rotation runbook
- Add SOC2-baseline audit logging if billing is involved
- Replace single-user JWT with full OAuth2 multi-tenant flow
- Re-evaluate the "CFO with a point of view" stance for liability — may need to soften to "advisor presenting options" for non-self use
```

---

## End

Once `<PLACEHOLDER>` blocks in Section 5 are filled and the new repo exists:

1. Copy this file to the new repo as `docs/KICKSTART.md`
2. Promote Section 2 → `docs/PRD.md`, Section 3 → `docs/SOT.md`, Section 4 → `docs/WEALTH_PRINCIPLES.md`, Section 6 → `docs/issues.md`, Section 8 → `CLAUDE.md`
3. Create empty `docs/DECISIONS.md`, `docs/PROJECT_STATE.md`, `docs/THREAT_MODEL.md`
4. Run `/init` if you want Claude Code to scaffold further
5. Run `/issue-workflow` and begin Issue 1
