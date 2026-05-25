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
7. `docs/CONTRACTS.md` — frozen interfaces (agent state, node I/O, endpoints, principle-key registry); do not diverge without amending it first

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
```bash
ssh <user>@<host>
cd ~/personal-cfo
git pull origin main
docker compose pull && docker compose up -d
```

Status:
```bash
docker compose ps
docker compose logs --tail 100 app
```

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
