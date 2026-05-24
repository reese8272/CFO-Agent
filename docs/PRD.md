# PRD — Personal Financial CFO Agent

**Version**: 0.2 (CFO pivot) | **Status**: Draft, ready for issue scoping after Section 5 of `docs/KICKSTART.md` placeholders are filled
**Last updated**: 2026-05-23

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

## Problem Statement

Existing personal-finance tools are either *trackers* (Monarch, Copilot, YNAB), *narrow optimizers* (MaxRewards, Credit Karma), *shallow chatbots* (Cleo), or *career-only platforms* (Levels.fyi, Pave). None solve the **data completeness problem** across both wealth levers — they can't see gig income at its source, cash income, real estate equity, retirement accounts at every institution, business P&L, true net hourly across streams, 1099 deductions, comp benchmarks, or any record of the user's intentional decisions. With incomplete context, every recommendation is generic. With complete context — automated where possible, manual where required — a competent LLM becomes a real CFO + career strategist: it knows where you are on **both** the allocation sequence and the income-generation sequence, calibrates advice to your specific irregular income and career trajectory, tracks progress toward 5-year goals, and explains the principle behind every move so the user builds judgment over time.

## Core Insight

> The reason no AI gives truly personalized financial advice is a data problem, not an intelligence problem.

The unlock isn't smarter AI. It's **complete context + good AI**.

## North Star (Day-One Indispensable)

> **"Tell me where I am — across allocation AND income — and what my single highest-leverage next move is."**

The agent reasons across two compounding tracks at once:

- **Allocation track** — the six-step wealth-building sequence in `docs/WEALTH_PRINCIPLES.md` (emergency fund → eliminate drag → tax-advantaged → market exposure → leverage → ownership). Computed by `vault/wealth_position.py`.
- **Income track** — the five-step income-generation sequence in `docs/WEALTH_PRINCIPLES.md` (net-hourly truth → cut the bottom → career velocity → deduction discipline → negotiation). Computed by `vault/income_position.py`.

On every turn the agent identifies the highest-leverage next move across both tracks and commits to one. This differentiates the product vs trackers ("here's what you spent"), optimizers ("use this card"), and career-only tools ("here's your market comp") — none of which can tell you *where you are* across both levers or *what to do next* in a way that compounds.

## Target User (v1)

A single user — the developer/owner. **Personal use only.** Architecture must not preclude multi-user, but no auth-of-others, no sharing, and no compliance scope beyond a personal threat model in v1.

## User Stories

### Allocation-side stories
- As the user, I want a single chat surface where I ask anything about my financial life and get a CFO-level answer that uses my complete picture.
- As the user, I want a **complete manual vault** for everything Plaid can't reach: gig income (DoorDash), cash income (coaching), real estate equity, business income, retirement accounts, goals, decisions.
- As the user, I want the agent to tell me **where I am in the wealth-building sequence** (emergency fund → eliminate high-interest debt → max tax-advantaged → market exposure → leverage → ownership) and what my **next move** is.
- As the user, I want the agent to surface **tax-advantaged room I haven't used** — specifically the Solo 401(k) I qualify for via 1099 income, and Roth IRA capacity.
- As the user, I want **scenario modeling** — "if I save $X/month, when do I hit Y? what if I drop DoorDash to 2 nights?"
- As the user, I want the agent to **commit to a recommendation** (CFO with a point of view), not present a buffet of options.
- As the user, I want the agent to **explain the principle** behind every move (debt avalanche, time-in-market, tax arbitrage, etc.) so I learn, not just comply.
- As the user, I want the agent to **remember decisions** I've made ("Roth before real estate this year") and not re-recommend against them.
- As the user, I want a **weekly digest** — cash position, week-over-week change, trajectory vs goals, this week's next move.
- As the user, I want **proactive alerts** for surplus detection ("$800 left this month — here's where it goes and why"), drift from plan, missed payment risk, and unused tax-advantaged room.
- As the user, I want to **add Plaid live data** once the manual layer is solid, without restructuring the agent.

### Income-side stories
- As the user, I want **net hourly truth** across every income stream — gross minus stream-specific expenses (gas, food during shifts, depreciation, opportunity cost) divided by hours — so I can rank streams and cut the bottom.
- As the user, I want the agent to **track career trajectory** — current comp, target role, target comp, time-in-role — and tell me when I'm off-pace.
- As the user, I want **comp benchmarks** for my role and metro stored in the vault, and surfaced when I ask "what's market for me?"
- As the user, I want the agent to **flag job-switch timing** — "you've been in this role 18 months; market data + your benchmark says a switch returns ~$X delta; here's the math."
- As the user, I want **promotion- and raise-prep coaching** — what's missing from my case, what to anchor in the conversation, when to bring it up.
- As the user, I want **1099 deduction discipline** — mileage, home-office %, equipment, education tracked per tax year, with the agent surfacing what I'm missing.
- As the user, I want **quarterly estimated tax** guidance — what to send IRS this quarter to avoid the underpayment penalty.
- As the user, I want the agent to **remember negotiation milestones** — upcoming reviews, contract renewals, raise-eligibility dates — and surface them proactively.

## Technical Decisions

**Decision**: Build MVP on a **complete manual vault** before any Plaid integration — **Why**: The data-completeness problem can't be solved by Plaid alone (gig source, cash, real estate, business, decisions are invisible to it). Owning the manual layer first forces the schema to be right; Plaid becomes a *partial automation* of an already-complete model.

**Decision**: **CFO-with-a-POV, not advisor-presenting-options** — **Why**: The brief calls out the distinction explicitly. The synthesizer prompt enforces a single committed recommendation with reasoning, not a list. Users who want options can always ask.

**Decision**: **Wealth-building sequence as a first-class concept** — **Why**: The agent must always know which step the user is on (see `docs/WEALTH_PRINCIPLES.md`) and what the next move is. This is the differentiator vs generic "spending insights." Encoded in a `wealth_position` view computed from vault data.

**Decision**: Single-user personal app for v1 — **Why**: Eliminates compliance scope (no PII for third parties, no SOC2 path) and removes the hardest security problems until product value is proven. Schema includes `user_id` foreign keys from day one so multi-user is mechanical later.

**Decision**: **LangGraph** for agent orchestration with named nodes (Analyzer → Strategist → Coach → Tracker → Alert → Synthesizer) — **Why**: Multi-step reasoning over a wealth picture needs explicit state and conditional routing. LangGraph is built for that.

**Decision**: **Claude (Anthropic SDK)** as the only LLM — **Why**: Best at nuanced explanation and at refusing to invent state-specific tax/legal facts. Prompt caching keeps cost flat as the vault grows.

**Decision**: **PostgreSQL** for vault + memory, **Redis** for agent session state — **Why**: Postgres handles relational financial data plus JSONB for flexible card-benefit blobs. Redis keeps LangGraph node state hot.

**Decision**: **Encryption at rest for all financial fields** (Fernet, key in env) — **Why**: Personal threat model is realistic — device theft, accidental git push, backup leak — not nation-state. Symmetric encryption on sensitive columns + full-disk encryption + TLS in transit covers it.

**Decision**: **FastAPI + HTMX**, no SPA — **Why**: The hard part is the agent, not the UI. Chat textbox, vault forms, goal-progress view, digest viewer. Avoid build-step complexity.

**Decision**: **Docker Compose** for local dev and self-hosted prod — **Why**: Three services (Postgres, Redis, FastAPI + worker) need orchestration. Compose is the minimal correct tool.

**Decision**: **Disclaimer wrapper on every agent response touching tax/legal/investment specifics** — **Why**: The agent is not a licensed advisor. The synthesizer prompt enforces the disclaimer; a structural test verifies it appears whenever the response touches those domains.

**Decision**: Defer Plaid until after Issue ~11 — **Why**: Plaid adds OAuth, token rotation, vendor coupling, and per-account cost. The manual layer must be proven valuable first; if it isn't, Plaid won't save it.

**Decision**: **Two parallel tracks, not one** (allocation + income generation) — **Why**: The owner's stated goal ("make as much money as possible given my particular situation") has two compounding levers. The original PRD addressed only allocation. See `docs/DECISIONS.md` entry 2026-05-24 for full reasoning.

**Decision**: **Income generation modeled as its own 5-step sequence** alongside the existing 6-step allocation sequence — **Why**: Mirrors the structure that already works for allocation. Lets the agent compute current position deterministically (`vault/income_position.py`) and the Strategist + Career nodes share a common reasoning shape.

**Decision**: **User-entered comp benchmarks in v1, external API (Levels.fyi / BLS / Pew) deferred** — **Why**: Vendor coupling, API cost, and rate limits are not worth solving before we know the feature gets used. v1 takes user-entered benchmarks; the agent reasons against them and cites them by source.

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
- [ ] Vault covers: accounts, cards, income streams (with `source_type` distinguishing W-2 / 1099 / cash / gig / coaching / business), recurring expenses, debts, assets, **real estate holdings (with equity)**, **business income/expenses**, **retirement accounts (Roth, 401k, IRA, Solo 401k)**, goals, decisions, **career_position** (current comp, target role, target comp, target date), **career_history** (past roles + comp + duration), **comp_benchmarks** (role × metro × source), **side_income_economics** (per-stream gross/hours/expenses/net-hourly), **tax_deductions_1099** (mileage / home-office / equipment / education per tax year), **negotiation_milestones** (upcoming reviews / renewals / raise-eligibility dates).
- [ ] User CRUDs every entity through a web form.
- [ ] Sensitive fields encrypted at rest.

### Wealth-Building Position (Allocation Track)
- [ ] Agent computes the user's current step on the 6-step wealth-building sequence on every chat turn.
- [ ] Agent always surfaces "next move given your position" when relevant.
- [ ] Vault has a `wealth_position` view that is queryable directly (debug + tests).

### Income-Generation Position (Income Track)
- [ ] Agent computes the user's current step on the 5-step income-generation sequence on every chat turn.
- [ ] `vault/income_position.py` returns a deterministic step (1–5) given any vault state.
- [ ] Agent always surfaces "next move on the income track" when relevant.
- [ ] On every turn the synthesizer commits to ONE highest-leverage move chosen across both tracks (not one per track).

### Agent
- [ ] Chat endpoint accepts a question, loads the full vault snapshot + active decisions + memory, runs LangGraph (Analyzer → Strategist → Coach → Tracker → Alert → Synthesizer), returns `{recommendation, reasoning, principle, disclaimer?}`.
- [ ] Synthesizer **commits to one recommendation**; refuses to list options unless explicitly asked.
- [ ] Agent refuses state-specific tax/legal advice with a disclaimer pointing to a CPA/CFP.
- [ ] Every recommendation cites a named wealth principle (see `docs/WEALTH_PRINCIPLES.md`).
- [ ] Decisions the user marks as committed persist and are respected in future turns.

### Career Coaching
- [ ] Vault stores current role, current comp, target role, target comp, target date, full career history.
- [ ] Strategist factors target comp into long-horizon planning.
- [ ] Tracker flags if elapsed time vs delta-to-target comp is off-pace.
- [ ] Career node returns a switch-timing recommendation given time-in-role + benchmark + delta.
- [ ] Career node returns a promotion-prep checklist on request.
- [ ] Negotiation milestones queryable; surfaced proactively within 30 days of trigger date.

### Income-Stream Optimization
- [ ] Net hourly computed per stream (gross − stream-specific expenses) / hours.
- [ ] Income-Optimizer node ranks all active streams by net hourly on demand.
- [ ] Cut-or-scale recommendation surfaced when a stream is more than 30% below the highest-margin stream.

### 1099 Tax Optimization
- [ ] Mileage, home-office %, equipment, education tracked per tax year.
- [ ] Tax-Optimizer node computes total deductions and flags missing categories on demand.
- [ ] Quarterly estimated tax suggestion uses year-versioned constants from `agent/principles.py`.
- [ ] Disclaimer attached to every response touching tax specifics (enforced by structural test).

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
