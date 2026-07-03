# LEFT_OFF — Session Handoff Contract

> **Read this first.** Living "where we are right now" file — NOT a source of truth (those live in
> `docs/`). Update whenever the active goal changes; run `/close-out` at the end of every session.

**Last updated:** 2026-07-02 (session 2 — Phase 5b)
**Branch:** `hardening/phase-5b-polish` → PR #38 (open, CI green pending). `main` HEAD `d715e67`.
**Working tree:** clean · PRs #36 + #37 merged to `main` this session (docs-only, no deploy).
**CI/Deploy:** live site ✅ healthy. **#38 is a CODE change → merging it triggers a Deploy** (unlike
#36/#37). VM swap still pending → watch the rollout for the OOM 502 (gotchas).

---

## 1. CURRENT FOCUS

**The Road-A production-hardening roadmap is COMPLETE.** A full `/assess` (Phases 0–6) took the app
from **VERDICT: NO** (1 BLOCKER + ~20 SEV1) to **PRODUCTION-READY: YES (Road A)** — see
`docs/assessment/REPORT.md`. Phases 0–6 are all merged to `main` and **live in production**. Only
housekeeping + optional polish remains.

### → NEXT ACTION

1. ✅ **DONE this session** — merged PR #37 (Phase 7 assessment) + #36 (swap runbook) to `main`;
   closed stale PR #29 (superseded by #37). Built + shipped **Phase 5b → PR #38** (response_model on
   bare-dict endpoints, security-headers middleware, slim `migrations/env.py`). Suite 177 passed / 4
   skipped, ruff clean, alembic upgrade verified.
2. **Merge PR #38** once CI is green — ⚠️ this is a CODE change, so it **triggers a Deploy**. VM swap
   is still pending, so watch the rollout; if it 502s, `gh run rerun <run-id> --failed`
   (ISSUE-2026-07-02-02).
3. **Apply the VM swap** (the one action that prevents the deploy-OOM 502 — see gotchas). SSH to the
   Oracle VM (`ubuntu@129.80.102.20`) and run the `fallocate`/`swapon` block in `docs/DEPLOYMENT.md §7.1`.
4. **(Optional) Phase 4b polish** — SEV2, none gate the YES verdict: `limit` cap on the ~17 vault GET
   list endpoints; encrypt `Account.plaid_account_id`. (5b is now done — see PR #38.)
5. **(Future) Road B** — real second users needs the full CLAUDE.md Pre-GA block; **tenant isolation**
   (`user_id` on every table + owner filter, ideally Postgres RLS) is the headline. Deferred by the
   `docs/DECISIONS.md` 2026-07-02 Road-A scope decision.

---

## 2. WHAT WORKS NOW (do not re-investigate)

- ✅ **`https://cfo.agenticlips.com` is live** — `/health` `{"status":"ok","postgres":"ok","redis":"ok"}`; `/docs` correctly **404 in prod** (gated).
- ✅ **Phases 0–6 merged + deployed** (PRs #30–#35): assessment+BLOCKER fix, LLM safety (rate limits/timeout/caching), async hygiene, data-layer migration, prod hardening (MultiFernet rotation, /docs gate, graceful shutdown, timing-safe login), agent correctness (multi-specialist routing + no-dup reducer).
- ✅ **Layer 0 clean:** ruff 0 (was 32), bandit 0/0, `requirements.txt` pip-audit clean (7 CVE'd deps bumped: fastapi 0.139, starlette 1.3.1, cryptography 48.0.1, pyjwt 2.13.0, …). mypy 152 (permissive ceiling).
- ✅ **Tests:** 172 passed / 4 skipped in CI and locally (py3.13).
- ✅ **Playwright installed** for point-and-click testing — persistent venv at `~/playwright-venv` (headless Chromium, no sudo needed); verified against live URLs.
- ✅ **Local test harness works** despite the documented starlette pin issue — build a py3.13 venv + a throwaway Postgres on port 5433 (see gotchas). This is how the suite + migrations were run all session.

---

## 3. THE ARC THAT LED HERE

1. Issues 1–19 — full stack built + first production deploy (pre-this-session; see `docs/PROJECT_STATE.md`).
2. This session: ran `/assess` → **VERDICT: NO** (1 BLOCKER: disclaimer drop; ~20 SEV1). Scoped to **Road A** (portfolio/single-user) via `docs/DECISIONS.md`.
3. Built `docs/PRODUCTION_ROADMAP.md` (8 phases) and executed Phases 0–6, each: code → local test → smoke → CI → merge → deploy → verify live.
4. Phase 6 deploy briefly 502'd (ARM-VM OOM, not code) — recovered via re-run; logged ISSUE-2026-07-02-02 + swap runbook.
5. Phase 7 re-assessment → **VERDICT: YES (Road A)**. That's where we are.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **Open PRs (to merge)** | #37 (Phase 7 assessment), #36 (ops swap runbook) — both doc-only |
| **Stale PR (not mine)** | #29 — a parallel-session assessment from 2026-06-28; triage separately |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Oracle VM** | `ubuntu@129.80.102.20` (SSH key is GitHub-secret-only — not in local `~/.ssh/`) |
| **Cloudflare Tunnel ID** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **Assessment output** | `docs/assessment/REPORT.md` + `modules/*.md` + `history/2026-07-02-REPORT-post-remediation.md` |
| **Secrets (names only)** | repo: `VAULT_ENCRYPTION_KEY`, `GH_PAT`; Prod env: `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `DEPLOY_*`, `SMTP_*`. New (optional): `VAULT_ENCRYPTION_KEYS` (comma-sep, for rotation) |
| **Local test venv** | `/tmp/cfo_venv` (py3.13; cleared on reboot — rebuild from `requirements.txt`). Playwright: `~/playwright-venv` (persistent) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — parallel Claude branches merge to main; run `git fetch origin && git rev-list --left-right --count origin/main...HEAD` before planning.
- **Pushing to `main` triggers Deploy** — EXCEPT doc-only pushes (`**.md`, `docs/**` are `paths-ignore`d). PRs #36/#37 are doc-only → safe to merge with no deploy.
- **Deploy can transiently 502 (ARM-VM OOM)** — ISSUE-2026-07-02-02: a rollout OOM-kills the app (`status 137` + "name resolution" in the deploy log) → 502. **Recover: `gh run rerun <run-id> --failed`. Prevent: add VM swap (`docs/DEPLOYMENT.md §7.1`) — still pending.** Distinguish from ISSUE-2026-07-02-01 (command_timeout; app stays up).
- **Local pytest needs a real DB** — no local Postgres role exists. Spin a throwaway: `initdb -D /tmp/cfo_pg -U cfo --auth=trust`; `pg_ctl -D /tmp/cfo_pg -o "-p 5433 -k /tmp" start`; `createdb -h localhost -p 5433 -U cfo personal_cfo`; then `DATABASE_URL=postgresql+psycopg://cfo:cfo@localhost:5433/personal_cfo REDIS_URL=redis://localhost:6379/15 TESTING=true` + the conftest env defaults, `alembic upgrade head`, `pytest`. Build the venv with `python3.13` (system python is 3.14 → no psycopg wheel).
- **SSH to the VM is GitHub-secret-only** — can't SSH from local; the swap must be applied by the owner (or via a `gh workflow run` path).
- **Single-user auth** — registration closes after the first user (409). The prod login credential exists (set at Gate 2) but is **unrecoverable** (bcrypt-hashed); no password-reset endpoint. Local point-and-click uses a fresh throwaway user.
- **Alembic startup is slow (~5min on the VM)** — heavy `env.py` import; `command_timeout` is now 20m and `lock_timeout` bounds locks. A bigger migration should still budget for it.

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/assessment/REPORT.md` | Latest verdict (YES Road A) + module register + scale checklist |
| `docs/PRODUCTION_ROADMAP.md` | The 8-phase plan; Phases 0–6 done, 4b/5b deferred |
| `docs/DECISIONS.md` | Road-A scope decision + per-phase deviations (index scope, reducer amendment, etc.) |
| `docs/CONTRACTS.md` | Frozen agent-state contract (§1 amended 2026-07-02 for the proposals reducer) |
| `docs/DEPLOYMENT.md` | Ops runbook — §7.1 deploy-OOM/swap, §8 MultiFernet key-rotation |
| `docs/PROJECT_STATE.md` · `docs/SOT.md` | Issue table + architecture/stack |
| `~/.claude/ISSUES_LOG.md` | Cross-project issue log — ISSUE-2026-07-02-01/-02 are this project's deploy gotchas |
| `~/.claude/projects/-home-reese-workspace-CFO-analyzer/memory/MEMORY.md` | User profile + session prefs |
