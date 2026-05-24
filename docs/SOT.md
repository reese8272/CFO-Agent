# SOT — Source of Truth

**Last updated**: 2026-05-23

This describes how the personal-cfo agent **will be built**. Update on every architectural change. Conflicts with `docs/PRD.md`: this file wins — log divergence in `docs/DECISIONS.md`.

> **Disclaimer**: This tool is for financial education and personal organization. It is not a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.

---

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
├── CLAUDE.md
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
│   │                           # Goal, CareerPosition, CareerHistory, CompBenchmark,
│   │                           # SideIncomeEconomics, TaxDeduction1099,
│   │                           # NegotiationMilestone
│   ├── schemas.py              # Pydantic
│   ├── crud.py                 # CRUD with encryption
│   ├── wealth_position.py      # Compute current step on allocation track (1–6)
│   └── income_position.py      # Compute current step on income track (1–5)
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
│   │   ├── strategist.py       # Allocation-side: wealth-vehicle prioritization,
│   │   │                       # debt vs invest tension
│   │   ├── career.py           # Income-side: comp benchmarks, switch timing,
│   │   │                       # promotion/raise prep, negotiation milestones
│   │   ├── income_optimizer.py # Net hourly per stream, prune-or-scale recommendation
│   │   ├── tax_optimizer.py    # 1099 deduction surfacing, quarterly tax estimation
│   │   ├── coach.py            # Explains the why; names the principle
│   │   ├── tracker.py          # Trajectory vs goals; drift + off-pace detection
│   │   ├── alert.py            # Proactive triggers (surplus, missed pmt risk,
│   │   │                       # unused room, career off-pace, deduction gap)
│   │   └── synthesizer.py      # Compose final response; commit to ONE move across
│   │                           # both tracks; enforce CFO POV + disclaimer
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
    ├── WEALTH_PRINCIPLES.md
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

career_history                       # ADDED 2026-05-24 pivot
  id, role, employer, comp_total_encrypted, start_date, end_date,
  reason_for_leaving (promoted/switched/laid_off/quit/other),
  notes, created_at

comp_benchmarks                      # ADDED 2026-05-24 pivot
  id, role, metro, source (levels_fyi/bls/pew/pave/user/other),
  comp_p50_encrypted, comp_p75_encrypted, comp_p90_encrypted,
  as_of_date, notes, created_at

side_income_economics                # ADDED 2026-05-24 pivot
  id, income_stream_id (FK to income_streams),
  period_start, period_end,
  gross_encrypted, hours_worked,
  expenses_jsonb (gas/food/depreciation/opportunity_cost/other, each encrypted),
  net_encrypted (computed), net_hourly_encrypted (computed), created_at

tax_deductions_1099                  # ADDED 2026-05-24 pivot
  id, tax_year, category (mileage/home_office/equipment/education/other),
  amount_encrypted, evidence_note_encrypted, created_at
  # Mileage stored as miles * year-versioned IRS rate from agent/principles.py

negotiation_milestones               # ADDED 2026-05-24 pivot
  id, kind (annual_review/contract_renewal/raise_eligibility/other),
  trigger_date, related_role, prep_notes_encrypted,
  status (upcoming/in_progress/completed/missed), completed_at, created_at

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
                  └──────┬───────┘  wealth_position + income_position + memory
                         ▼
                  ┌──────────────┐
                  │   Analyzer   │  classify the turn; route to allocation node(s),
                  └──────┬───────┘  income node(s), or both
                         ▼
        ┌─────────┬──────┴──────┬────────────────┬───────────┬─────────┐
        ▼         ▼             ▼                ▼           ▼         ▼
  ┌──────────┐ ┌──────┐ ┌──────────────┐ ┌──────────────┐ ┌──────┐ ┌──────┐
  │Strategist│ │Career│ │Income-       │ │Tax-          │ │Coach │ │Alert │
  │(alloc)   │ │      │ │Optimizer     │ │Optimizer     │ │      │ │      │
  └────┬─────┘ └──┬───┘ └──────┬───────┘ └──────┬───────┘ └──┬───┘ └──┬───┘
       └──────────┴────────────┴────────────────┴───────────┴────────┘
                                      ▼
                            ┌──────────────┐
                            │   Tracker    │  trajectory vs goals (both tracks);
                            └──────┬───────┘  career off-pace; deduction gap
                                   ▼
                            ┌──────────────┐
                            │ Synthesizer  │  ONE committed move across both tracks;
                            └──────┬───────┘  named principle; disclaimer when required
                                   ▼
                            ┌──────────────┐
                            │   Persist    │  messages, decisions, patterns, audit
                            └──────────────┘
```

The Strategist, Career, Income-Optimizer, and Tax-Optimizer nodes fire conditionally based on the Analyzer's turn classification. Most turns invoke only one or two; the Synthesizer always picks the single highest-leverage move across whatever fired.

## Security Posture (v1)

- Fernet on all sensitive columns; key in env, never in code, never in git
- TLS in transit via Cloudflare Tunnel
- Full-disk encryption on the host VM
- No third-party analytics or error reporters with payloads
- Audit log on every read/write of vault entities; append-only at the app layer
- Anthropic prompts redact account numbers and exact dollar balances unless arithmetic precision is required — pass rounded aggregates by default
- Backups encrypted with a separate key, stored off-host
- Disclaimer enforced by structural test, not just prompt convention

Full threat model in `docs/THREAT_MODEL.md`.

## Known Production Gaps

- `VAULT_ENCRYPTION_KEY` rotation runbook not written
- No rate limiting on `/chat` (single-user, but LLM cost ceiling matters)
- Plaid deferred; sync gaps when added
- Agent eval harness (`tests/eval/`) covers happy paths only; needs adversarial coverage
- Digest email has no opt-out or pause mechanism
- No external monitoring/alerting wired up
