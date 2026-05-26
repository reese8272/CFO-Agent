# Project State

Live snapshot of where the build stands. Update at every issue close.

**Last updated**: 2026-05-26

---

## Status

**Phase**: v1 feature-complete + CI wired. Issues 1–14 shipped (Issue 13 Plaid deferred indefinitely). Full pytest suite: 135 passed, 2 skipped against live Postgres + Redis. GitHub Actions workflows created (CI, Docker build, deploy skeleton). Remaining manual gates: vault.html browser walkthrough and production deploy.

**Key decisions**: Pivot 2026-05-24 — Personal CFO + Career Strategist. Free-first ingestion (yfinance + RentCast + CSV/OFX). Encryption at ORM layer via TypeDecorators. All documented in `docs/DECISIONS.md`.

## North Star

> "Tell me where I am — across allocation AND income — and what my single highest-leverage next move is."

The agent reasons across two parallel tracks every turn:
- **Allocation track** — 6-step sequence in `docs/WEALTH_PRINCIPLES.md`, computed by `vault/wealth_position.py`
- **Income track** — 5-step sequence in `docs/WEALTH_PRINCIPLES.md`, computed by `vault/income_position.py`

Synthesizer commits to ONE move across both tracks.

## Open TODOs (Owner Input Required)

- [x] **5-year goal (`docs/KICKSTART.md` Section 5.1)** — filled 2026-05-25. Target: $1M net worth by 2031, $200–300k/yr income, $3–5k/mo passive. Five levers: W-2 switches to $140k, SaaS/product revenue to $60–120k/yr, Roth maxed annually, index fund brokerage $100–200k, own primary residence by 2031. See Section 5.1 for full detail and DB entries to create at vault-population time.
- [x] **Run the research prompt** — completed 2026-05-24. Output landed in `docs/RESEARCH_NOTES.md` (11 domains, ~50 named principles, all 2026 tax constants verified against IRS Rev. Proc. 2025-32 / Notice 2025-67 / Rev. Proc. 2025-19 / Notice 2026-10, plus Top 10 / Top 5 books / Red Flags). Content ports into `WEALTH_PRINCIPLES.md`, `agent/principles.py`, and the three arena modules during Issues 6 and 8.

## Issues

| # | Title | Status |
|---|---|---|
| 14 | Test suite cleanup — DB teardown, expected-tables sync, subprocess env isolation | **Closed 2026-05-25** |
| 1 | Repo scaffold + Docker Compose + health endpoint | **Closed 2026-05-24** |
| 2 | Postgres schema + Alembic + encryption helper *(scope expanded)* | **Closed 2026-05-24** |
| 3 | Single-user auth (JWT) — register-once + token + get_current_user | **Closed 2026-05-25** |
| 4 | Vault CRUD + ergonomic HTMX UI *(scope expanded + tightened)* | **Closed 2026-05-25** |
| **4b** | **Free data automation layer (yfinance + RentCast AVM + holdings)** *(new — 2026-05-24 free-first)* | **Closed 2026-05-25** |
| **4c** | **CSV / OFX import** *(new — 2026-05-24 free-first, replaces Plaid for v1)* | **Closed 2026-05-25** |
| 5 | Wealth-position + income-position + net-worth-trajectory endpoints *(scope expanded)* | **Closed 2026-05-25** |
| 6 | Anthropic singleton + retrieval node | **Closed 2026-05-25** |
| 7 | Minimal LangGraph — Retrieval → Synthesizer → Persist | **Closed 2026-05-25** |
| 8 | Analyzer + Strategist + Coach nodes *(scope expanded — arena principles + voice + long-horizon stamping)* | **Closed 2026-05-25** |
| **8b** | **Career + Income-Optimizer + Tax-Optimizer nodes** *(new — 2026-05-24 pivot)* | **Closed 2026-05-25** |
| 9 | Decisions persistence + retrieval respects them | **Closed 2026-05-25** |
| 10 | Tracker + Alert nodes *(scope expanded)* | **Closed 2026-05-25** |
| 11 | Scenario modeling engine + endpoint + UI | **Closed 2026-05-25** |
| 12 | Weekly digest cron + email | **Closed 2026-05-25** |
| 13 | Plaid integration | **Deferred indefinitely 2026-05-24** — preserved as escape hatch |
| **15** | **Financial Intake Wizard — backend (models, migration, analysis engine, router)** | **In Progress 2026-05-26** |

## Blocked

_None._

## Next Up

### Gate 2 — Manual browser walkthrough (owner action required)
1. `docker compose up -d` — bring up the full stack locally
2. Open `http://localhost:8000/static/vault.html` in a browser
3. Add at least one account, one debt, one income stream
4. Open chat — ask "where am I financially?" — verify agent responds with a single concrete recommendation
5. Run scenario: "How long to $1M at current trajectory?" — verify months and monthly breakout render
6. Confirm disclaimer visible on every agent response
7. Time the full round-trip — target < 30 min/month workload

### Gate 3 — Vault population (owner action required, before first real session)
Create these rows so Tracker has calibration anchors:
- `goals`: `kind=net_worth`, `target_amount=1000000`, `target_date=2031-05-25`, `label="$1M net worth"`
- `goals`: `kind=income`, `target_amount=200000`, `target_date=2031-05-25`, `label="$200k/yr income"`
- `career_position`: `current_comp=80000`, `target_comp=140000`, `target_date=2029-05-25`, `employer="current"`, `role="current"`
- SMTP: fill real credentials in `.env` for weekly digest — `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

### Gate 4 — Production deploy (after Gates 2 & 3)
1. Provision Oracle Cloud Free ARM VM (if not already done)
2. Update `CLAUDE.md` placeholders: target host, SSH user, domain
3. Set GitHub Actions secrets: `SSH_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` (see `.github/workflows/deploy.yml`)
4. `git push origin main` — CI runs automatically
5. SSH to host: `git pull && docker compose pull && docker compose up -d`
6. Configure Cloudflare Tunnel to forward to `localhost:8000`
