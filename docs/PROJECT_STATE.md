# Project State

Live snapshot of where the build stands. Update at every issue close.

**Last updated**: 2026-05-24

---

## Status

**Phase**: Build. Issue 1 shipped (repo scaffold + Docker Compose + `/health`). Section 5 placeholders resolved except for the 5-year goal (see Open TODOs).

## North Star

> "Tell me where I am in the wealth-building sequence and what my next move is."

This is the day-one indispensable capability — anchored on the six-step sequence in `docs/WEALTH_PRINCIPLES.md`, computed by `vault/wealth_position.py`.

## Open TODOs (Owner Input Required)

- [ ] **5-year goal (`docs/KICKSTART.md` Section 5.1)** — owner to write concrete net worth / passive income / Roth / brokerage / career targets. Strategist (Issue 8) falls back to step-by-step sequence optimization without it, but loses long-horizon calibration. Fill before Issue 8 at the latest.

## Issues

| # | Title | Status |
|---|---|---|
| 1 | Repo scaffold + Docker Compose + health endpoint | **Closed 2026-05-24** |
| 2 | Postgres schema + Alembic + encryption helper | Open (next) |
| 3 | Single-user auth (JWT) | Open |
| 4 | Vault CRUD + minimal HTMX UI | Open |
| 5 | Wealth-position computation + endpoint | Open |
| 6 | Anthropic singleton + retrieval node | Open |
| 7 | Minimal LangGraph — Retrieval → Synthesizer → Persist | Open |
| 8 | Analyzer + Strategist + Coach nodes | Open |
| 9 | Decisions persistence + retrieval respects them | Open |
| 10 | Tracker + Alert nodes | Open |
| 11 | Scenario modeling engine + endpoint + UI | Open |
| 12 | Weekly digest cron + email | Open |
| 13 | Plaid integration (deferred) | Open |

## Blocked

_None._

## Next Up

1. Issue 2 — Postgres schema + Alembic + encryption helper. Phase 1 CHECK brief required before any code.
2. Owner TODO: fill the 5-year goal in `docs/KICKSTART.md` Section 5.1 before Issue 8 (Strategist).
