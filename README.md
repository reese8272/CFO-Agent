# Personal CFO Agent

**An AI "CFO" for your personal finances** — a LangGraph agent that reasons over an encrypted picture of your money and commits to one clear, principle-backed recommendation instead of a wall of options.

![Status: In active development](https://img.shields.io/badge/status-%F0%9F%9A%A7%20in%20active%20development-orange)
![Python 3.13](https://img.shields.io/badge/python-3.13-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.139-009688)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1c3c3c)
![Tests](https://img.shields.io/badge/tests-159-brightgreen)

> **Status: 🚧 In active development — not yet deployed to production.** The full stack runs locally under Docker Compose (API, agent, worker, PostgreSQL, Redis, Cloudflare Tunnel) and the test suite is green, but this is a personal, single-user build still being hardened. It is a portfolio project, not a launched product, and is not financial advice.

---

## What it does

Personal CFO ingests your financial picture — accounts, debts, income streams, expenses, real-estate, brokerage holdings, and business income — into an **encrypted vault**, then lets you chat with a **LangGraph agent** that behaves like a CFO with a point of view. Every turn flows through a multi-node reasoning graph (analyze → route to a specialist → coach → track → alert → synthesize) and returns a *single* committed recommendation that cites a named wealth principle and, where relevant, year-versioned IRS tax constants. Deterministic tooling (scenario projections, market-price and property-value lookups, a weekly email digest) surrounds the LLM so the numbers stay exact and auditable.

## Screenshot

The project deploys behind a Cloudflare Tunnel. Below is the tunnel configuration for the `CFO-Agent` service (shown here pre-activation during development):

![screenshot](./Screenshot%202026-05-27%20221009.png)

---

## Key features

- **🔐 Encrypted financial vault** — sensitive columns (balances, amounts, account details) are encrypted at rest with Fernet via transparent SQLAlchemy `TypeDecorator`s (`EncryptedString`, `EncryptedNumeric`, `EncryptedJSON`). Plaintext never touches Postgres; ciphertext never touches application logic. Full CRUD over accounts, cards, income streams, expenses, debts, assets, real estate, business income, and holdings.
- **🧠 LangGraph agent with a point of view** — an 11-node graph routes each question to the right specialist (Strategist, Career, Income-Optimizer, or Tax-Optimizer), runs it through a Coach → Tracker → Alert chain, and has the Synthesizer commit to **one** recommendation rather than enumerating options.
- **📚 Principle-grounded reasoning** — every strategist output cites a named principle from a registry, and year-versioned tax constants (2026 Roth/IRA/HSA/Solo-401k limits, SE-tax and mileage rates sourced from IRS publications) are stamped with the tax year on every citation.
- **⚡ Anthropic prompt caching** — each node caches its system prompt and the assembled user-profile block with `cache_control: ephemeral`, cutting token cost and latency across the multi-hop graph.
- **🗂️ Hybrid memory / retrieval** — a Retrieval node assembles a deterministic "User Profile" context from vault aggregates, wealth/income ladder positions, active decisions, and recent patterns; conversations, messages, decisions, and patterns persist across sessions.
- **📈 Deterministic scenario engine** — compound-interest "time to target" and "income change" projections computed in exact `Decimal`, kept out of the LLM so forecasts are reproducible.
- **📥 Statement imports** — CSV and OFX transaction import with date-format detection and content-hash deduplication, plus reusable category mappings.
- **💹 Live market & property data** — brokerage holdings priced via yfinance (Alpha Vantage fallback); real-estate values via the RentCast AVM, with a mandatory "not a licensed appraisal" disclaimer travelling on the HTTP response.
- **📨 Weekly digest worker** — an APScheduler cron emails a weekly financial digest (Mondays 07:00 UTC) and pings an optional external dead-man's-switch monitor.
- **🛡️ Security posture** — single-user JWT auth (bcrypt, OAuth2 password-flow shape kept for a future multi-tenant path), slowapi rate limiting, CORS, audit-log rows on vault mutations, and a structural test that enforces the legal disclaimer on any tax/investment-touching response.
- **✅ Tested** — 159 tests including a dedicated agent evaluation harness (`tests/eval/`) with canned scenarios and expected facts, run in CI against real Postgres and Redis (no DB mocking).

---

## Architecture

A FastAPI application fronts a LangGraph agent and a set of deterministic services. PostgreSQL is the system of record (sensitive columns Fernet-encrypted), Redis backs LangGraph checkpoints and caching, and an in-process APScheduler worker runs scheduled jobs. Everything is containerized with Docker Compose and exposed through a Cloudflare Tunnel.

```
                         ┌──────────────────────────────────────────────┐
   Browser (HTMX)  ──►   │              FastAPI app (main.py)             │
                         │  auth · vault · holdings · imports · wealth   │
                         │  chat · memory · scenarios · digest · intake  │
                         └───────┬───────────────┬───────────────┬──────┘
                                 │               │               │
                    ┌────────────▼───┐   ┌───────▼───────┐   ┌───▼──────────┐
                    │  LangGraph     │   │  Scenario     │   │  Integrations │
                    │  agent         │   │  engine       │   │  yfinance /   │
                    │                │   │  (Decimal)    │   │  RentCast /   │
                    │                │   └───────────────┘   │  CSV · OFX    │
                    │                │                       └──────────────┘
                    │  retrieval → analyzer → {strategist | career |
                    │    income_optimizer | tax_optimizer} → coach →
                    │    tracker → alert → synthesizer → persist
                    └───┬─────────────────────────┬──────────────┬──────┘
                        │                         │              │
                 ┌──────▼──────┐          ┌───────▼──────┐   ┌───▼──────────┐
                 │ PostgreSQL  │          │    Redis     │   │  Anthropic   │
                 │ 16 (Fernet- │          │ 7 (LangGraph │   │  API (prompt │
                 │  encrypted) │          │ checkpoints) │   │   caching)   │
                 └─────────────┘          └──────────────┘   └──────────────┘
                        ▲
                 ┌──────┴───────┐   ┌──────────────────┐
                 │ Alembic      │   │ APScheduler      │
                 │ migrations   │   │ worker (weekly   │
                 └──────────────┘   │ digest + ping)   │
                                    └──────────────────┘
```

**Agent graph:** `retrieval → analyzer → [conditional route] → coach → tracker → alert → synthesizer → persist`. The Analyzer classifies the turn and routes to a specialist node by priority (allocation → career → income → tax → coach-only); conditional-node proposals merge via a parallel-safe reducer before the Coach and Synthesizer collapse them into one answer.

---

## Tech stack

| Layer | Technology |
|---|---|
| **Language** | Python 3.13 |
| **Web / API** | FastAPI 0.139, Starlette, Uvicorn, Pydantic v2 + pydantic-settings |
| **Agent** | LangGraph 1.2 with `langgraph-checkpoint-redis`, Anthropic SDK 0.84 (prompt caching) |
| **Data** | PostgreSQL 16, SQLAlchemy 2.0 (async, `psycopg` v3), Alembic migrations |
| **Cache / state** | Redis 7 |
| **Worker** | APScheduler (in-process async scheduler) |
| **Auth / crypto** | PyJWT, bcrypt, `cryptography` (Fernet) |
| **Rate limiting** | slowapi |
| **Integrations** | yfinance + Alpha Vantage (market data), RentCast (property AVM), `ofxtools` + stdlib `csv` (imports) |
| **Frontend** | Vanilla HTML + HTMX (no build step) |
| **Infra** | Docker + Docker Compose, Cloudflare Tunnel, `autoheal`, GitHub Actions CI/CD |

---

## Getting started

Prerequisites: Docker and Docker Compose.

```bash
# 1. Configure environment
cp .env.example .env

# 2. Fill in the required secrets in .env:
#    ANTHROPIC_API_KEY   — from https://console.anthropic.com
#    JWT_SECRET_KEY      — openssl rand -hex 32
#    VAULT_ENCRYPTION_KEY — python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
#    DIGEST_RECIPIENT    — email for the weekly digest
#    (DATABASE_URL / REDIS_URL default to the compose service names)

# 3. Start Postgres, Redis, the app, and the Cloudflare tunnel
docker compose up -d --build

# 4. Apply database migrations
docker compose exec app alembic upgrade head

# 5. Verify health
curl localhost:8000/health
#    → {"status":"ok","postgres":"ok","redis":"ok"}
```

The API is served on `http://localhost:8000` and redirects to the login page. Create the single user via `POST /auth/register` (registration closes after the first user), then explore the vault, chat, scenarios, and intake pages under `/static/`.

**Local development** with hot-reload:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up --build
```

> Interactive API docs are served at `/docs` in development. Disabling them in production is part of the in-progress hardening pass (see **Roadmap**).

---

## Project structure

```
CFO-analyzer/
├── main.py              # FastAPI entrypoint — lifespan, middleware, router wiring, /health
├── config.py            # Typed pydantic-settings config (fails fast on missing secrets)
├── db.py                # Async SQLAlchemy engine, session factory, health ping
├── crypto.py            # Fernet encryption boundary + Encrypted* TypeDecorators
├── auth.py              # Single-user bcrypt + JWT authentication
├── clients.py           # Redis and Anthropic client singletons
├── rate_limit.py        # slowapi limiter
├── disclaimer.py        # Canonical legal disclaimer
├── digest.py            # Weekly digest generation + send
├── agent/               # LangGraph agent
│   ├── graph.py         #   graph topology + compile
│   ├── state.py         #   frozen AgentState contract
│   ├── prompts.py       #   cached system prompts
│   ├── principles*.py   #   wealth-principle registry + year-versioned tax constants
│   └── nodes/           #   analyzer, strategist, coach, career, tax/income optimizers, tracker, alert, synthesizer
├── routers/             # API routes: vault, holdings, imports, wealth, chat, memory, scenarios, digest, intake
├── vault/               # Encrypted financial models, schemas, CRUD, wealth/income ladder logic
├── memory/              # Conversation/message/decision/pattern models + retrieval context builder
├── scenarios/           # Deterministic Decimal projection engine + models
├── integrations/        # yfinance/Alpha Vantage, RentCast, CSV/OFX import parsers
├── worker/              # APScheduler cron (weekly digest + healthcheck ping)
├── migrations/          # Alembic migrations
├── static/              # HTMX frontend pages (login, vault, chat, scenarios, intake, digest, settings)
├── tests/               # 159 tests incl. tests/eval/ agent evaluation harness
└── docs/                # PRD, architecture (SOT), threat model, decisions, deployment, wealth principles
```

---

## Roadmap / what's next

Current focus is a P2 production-hardening pass before the system is opened beyond its single owner:

- **Hardening** — per-route rate limiting on the LLM endpoints, explicit Anthropic call timeouts, FK indexes on hot columns, graceful-shutdown window, and pagination caps on list endpoints.
- **Plaid account aggregation** — scaffolded in config as a Phase 2 integration; not yet wired.
- **Multi-tenant path** — the auth layer keeps the OAuth2 password-flow shape deliberately; going multi-user requires per-user data-isolation tests, per-user quotas, key-rotation runbook, and a refreshed threat model (tracked in `docs/`).
- **Deployment** — the full Docker Compose + Cloudflare Tunnel pipeline exists; production rollout and monitoring are being finalized.

---

## Disclaimer

This tool is for financial education and personal organization. It is **not** a licensed financial advisor. For tax strategy, real estate transactions, and investment decisions, consult a licensed professional.
