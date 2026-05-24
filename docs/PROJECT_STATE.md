# Project State

Live snapshot of where the build stands. Update at every issue close.

**Last updated**: 2026-05-24

---

## Status

**Phase**: Build. Issue 1 shipped (repo scaffold + Docker Compose + `/health`). **Pivot landed 2026-05-24** — v1 reframed to "Personal CFO + Career Strategist" per `docs/DECISIONS.md`; PRD, SOT, WEALTH_PRINCIPLES, and issues all updated. Section 5 placeholders resolved except for the 5-year goal (see Open TODOs).

## North Star

> "Tell me where I am — across allocation AND income — and what my single highest-leverage next move is."

The agent reasons across two parallel tracks every turn:
- **Allocation track** — 6-step sequence in `docs/WEALTH_PRINCIPLES.md`, computed by `vault/wealth_position.py`
- **Income track** — 5-step sequence in `docs/WEALTH_PRINCIPLES.md`, computed by `vault/income_position.py`

Synthesizer commits to ONE move across both tracks.

## Open TODOs (Owner Input Required)

- [ ] **5-year goal (`docs/KICKSTART.md` Section 5.1)** — owner to write concrete net worth / passive income / Roth / brokerage / career targets. Strategist (Issue 8) falls back to step-by-step sequence optimization without it, but loses long-horizon calibration. Fill before Issue 8 at the latest.

## Issues

| # | Title | Status |
|---|---|---|
| 1 | Repo scaffold + Docker Compose + health endpoint | **Closed 2026-05-24** |
| 2 | Postgres schema + Alembic + encryption helper *(scope expanded)* | Open (next) |
| 3 | Single-user auth (JWT) | Open |
| 4 | Vault CRUD + minimal HTMX UI *(scope expanded)* | Open |
| 5 | Wealth-position + income-position computation + endpoints *(scope expanded)* | Open |
| 6 | Anthropic singleton + retrieval node | Open |
| 7 | Minimal LangGraph — Retrieval → Synthesizer → Persist | Open |
| 8 | Analyzer + Strategist + Coach nodes | Open |
| **8b** | **Career + Income-Optimizer + Tax-Optimizer nodes** *(new — 2026-05-24 pivot)* | Open |
| 9 | Decisions persistence + retrieval respects them | Open |
| 10 | Tracker + Alert nodes *(scope expanded)* | Open |
| 11 | Scenario modeling engine + endpoint + UI | Open |
| 12 | Weekly digest cron + email | Open |
| 13 | Plaid integration (deferred) | Open |

## Blocked

_None._

## Next Up

1. Issue 2 — Postgres schema + Alembic + encryption helper. Phase 1 CHECK brief required before any code.
2. Owner TODO: fill the 5-year goal in `docs/KICKSTART.md` Section 5.1 before Issue 8 (Strategist).
