# LEFT_OFF — Session Handoff Contract

> **Read this first.** Living "where we are right now" file — NOT a source of truth (those live in
> `docs/`). Update whenever the active goal changes; run `/close-out` at the end of every session.

**Last updated:** 2026-07-09 (session 3 — SEV2 register cleared, Phase 4b closed, dead-man's-switch LIVE)
**Branch:** `main` HEAD `b39899f` (deploy-secrets forwarding #45). Working tree clean; in sync with origin.
**CI/Deploy:** all green. Four PRs merged + deployed + verified live this session (#41, #42, #43, #45).
Site ✅ `/health` `{"status":"ok","postgres":"ok","redis":"ok"}`; `cache-control: no-store` confirmed live.

---

## 1. CURRENT FOCUS

**The entire assessment backlog is CLOSED.** Every code SEV2 from the 2026-07-03 `/assess` register
is shipped and live (see `docs/PROJECT_STATE.md` for the itemized list), Phase 4b (pagination +
plaid_account_id encryption) is done, GitHub #28 is closed, and the deploy pipeline now forwards the
two observability secrets. Nothing is in flight; nothing is blocked on code.

### → NEXT ACTION

1. ✅ **DONE — dead-man's-switch LIVE (2026-07-09).** healthchecks.io account created under
   reesepludwick@gmail.com (passwordless magic-link login); check **"CFO prod ping"** period 5 min /
   grace 5 min, email alerts on; `HEALTHCHECK_PING_URL` set as a repo GitHub secret; deploy
   dispatched; **verified: "Last Ping: a minute ago"** on the dashboard. Project id
   `7db194d0-f8c1-43ff-8eba-a3e355323770`, check uuid `31c1d142-e68d-4e5b-b747-ae23a5f0315a`.
2. ✅ **DONE — Sentry error tracking activated (2026-07-09).** Owner created the account
   (Sentry org `o4511706759888896`, US region); `SENTRY_DSN` set as a repo GitHub secret; deploy
   dispatched + green. The Sentry project shows "waiting for events" until the first unhandled
   error occurs — that's expected (init is confirmed by the same .env pipeline that delivers the
   healthcheck ping, which is proven working).
3. ✅ **DONE — Issue #44 shipped (PR #46, 2026-07-09).** Inline dismissible error banners on all
   vault HTMX forms (422 field detail + network errors), input preserved on failure, busy state.
   **Also fixed a latent SEV it exposed: vault HTMX creates NEVER worked** (urlencoded vs Pydantic
   JSON — logged as ISSUE-2026-07-09-01; fixed via `htmx-ext-json-enc@2.0.2` + empty-param strip).
   Verified point-and-click via Playwright (happy/422/dismiss/retry/offline) and live in prod.
4. ✅ **DONE — Gate 2 walkthrough COMPLETE (PR #47, 2026-07-09).** All seven checks pass (login →
   vault forms → chat single-recommendation w/ principle+vision+disclaimer → $1M scenario →
   workload). Caught + fixed two real defects: a **disclaimer miss** (debt-vs-invest turn named
   Roth IRA, all LLM flags false → added deterministic keyword backstop
   `disclaimer.text_requires_disclaimer()`, both synthesizer paths) and **scenario step-grids
   rejecting $1,000,000** (min/step 100-grids → step="0.01"). Details in `docs/PROJECT_STATE.md`.
   **Demo tip:** after editing the vault directly, hit `POST /intake/snapshot/refresh` (settings)
   so the agent reasons over current data — the snapshot is computed at intake time.
5. **(Future) Road B** — multi-tenant: tenant isolation (`user_id` + RLS), cursor pagination,
   licensed market-data path (yfinance is personal-use only — see DECISIONS 2026-07-09), full
   CLAUDE.md Pre-GA block. Deferred by the `docs/DECISIONS.md` 2026-07-02 Road-A scope decision.

---

## 2. WHAT WORKS NOW (do not re-investigate)

- ✅ **`https://cfo.agenticlips.com` live**; `/docs` correctly 404 in prod; security headers incl.
  `Cache-Control: no-store` (non-static) verified on the live origin.
- ✅ **SEV2 register cleared (session 3)** — #41: Coach principle enum pinned (arena keys registered
  in CONTRACTS §4), import 404 validation, idempotent digest (`digest_sent_log`), distinct-ticker
  refresh, defusedxml, async scheduler shutdown. #42: pagination caps on all 20 list endpoints
  (`routers/pagination.py`, default 200 / max 1000), `plaid_account_id_encrypted` (migration
  `b9d3e6f1a825`, in-place-encrypt verified). #43: no-store, `CurrentUser=User` in 8 routers,
  yfinance TOS posture, doc currency (Issue 15 closed). #45: deploy.yml forwards
  `HEALTHCHECK_PING_URL`/`SENTRY_DSN` into the prod `.env` (empty → inert).
- ✅ **Tests: 191 passed / 3 skipped** (py3.13, live PG/Redis); `tests/eval/` 4/4; ruff clean.
- ✅ **Migrations at head `b9d3e6f1a825`** in prod (deploy logs confirmed both new migrations); the
  slim `env.py` means prod migration steps now take ~15 s, not ~5 min.
- ✅ Local test harness recipe (venv + throwaway Postgres on 5433) works — see gotchas §5.

---

## 3. THE ARC THAT LED HERE

1. Issues 1–19: full stack built + first prod deploy. Sessions 1–2: `/assess` NO → 8-phase Road-A
   hardening → re-assess **YES** → Top-5 showcase fixes (#39) + Sentry (#40) (see history in
   `docs/PRODUCTION_ROADMAP.md` / `docs/assessment/`).
2. Session 3 (2026-07-09): severity-ordered the remaining backlog, then shipped it all —
   PR #41 (six code SEV2s) → PR #42 (Phase 4b closeout) → PR #43 (final sweep + doc currency,
   closed GitHub #28, opened #44) → PR #45 (deploy-secrets forwarding, found while writing the
   owner activation steps: setting the secrets would have silently no-op'd).
3. Each PR: local suite green → PR CI green → squash-merge → Deploy green → live verification.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **Open PRs** | none — #41/#42/#43/#45 merged; open issue: **#44** (HTMX error states) |
| **Prod host (CFO)** | Oracle VM **`129.80.102.20`** = `instance-20260526-0052` (US-Ashburn). SSH `ubuntu@` works only with the GitHub `SSH_PRIVATE_KEY` secret (local keys denied). **Manage via `oci` CLI** (`~/.oci/config` works): `oci compute instance action --instance-id <ocid> --action SOFTRESET`. |
| **⚠️ NOT the CFO host** | `ssh creatorclip-vm` (DigitalOcean) runs AutoClip/CreatorClip. Verify before touching. |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Cloudflare Tunnel ID (CFO)** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **Alembic head** | `b9d3e6f1a825` (encrypt plaid_account_id) ← `f2c8a1b7d403` (digest_sent_log) |
| **Assessment output** | `docs/assessment/REPORT.md` (+ `modules/`, `history/`) — register now fully cleared |
| **Secrets (names only)** | repo: `VAULT_ENCRYPTION_KEY`, `GH_PAT`; Prod env: `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `DEPLOY_*`, `SMTP_*`. **`HEALTHCHECK_PING_URL` + `SENTRY_DSN` both set (repo-level, 2026-07-09) and live.** Optional: `VAULT_ENCRYPTION_KEYS` (rotation) |
| **Local test venv** | `/tmp/cfo_venv` (py3.13; cleared on reboot — rebuild from `requirements.txt`). Playwright: `~/playwright-venv` (persistent) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — parallel Claude branches merge to main; run
  `git fetch origin && git rev-list --left-right --count origin/main...HEAD` before planning.
- **Pushing to `main` triggers Deploy** — EXCEPT doc-only pushes (`**.md`, `docs/**` are
  `paths-ignore`d). `.github/**` changes DO deploy (#45 did).
- **Merging PRs needs explicit user approval** — the permission gate blocks self-merge to main;
  this session the owner authorized the merge flow per-PR ("go ahead and merge").
- **Deploy can transiently 502 (ARM-VM OOM)** — ISSUE-2026-07-02-02. Recover:
  `gh run rerun <run-id> --failed`. Swap is auto-ensured by deploy.yml `[0/6]` since 2026-07-03.
- **Full outage = VM OOM-thrash (ISSUE-2026-07-03-01)** — site flaps 530/502/000 AND SSH
  banner-times-out → reboot via `oci` (SOFTRESET; OCI force-completes if it hangs ~5 min).
- **Local pytest needs a real DB** — `initdb -D /tmp/cfo_pg -U cfo --auth=trust`;
  `pg_ctl -D /tmp/cfo_pg -o "-p 5433 -k /tmp" start`; `createdb -h localhost -p 5433 -U cfo
  personal_cfo`; venv from **python3.13** (system 3.14 has no psycopg wheel); then
  `DATABASE_URL=postgresql+psycopg://cfo:cfo@localhost:5433/personal_cfo
  REDIS_URL=redis://localhost:6379/15 alembic upgrade head && pytest`. Redis via
  `redis-server --daemonize yes`.
- **Single-user auth** — registration closes after the first user (409); prod credential
  unrecoverable (no reset endpoint). Local testing uses a fresh throwaway user per run.
- **Digest idempotency semantics** — cron skips a week already in `digest_sent_log`;
  `/digest/run-now` always sends but logs. Don't "fix" one to behave like the other
  (DECISIONS 2026-07-09).
- **yfinance is personal-use only** (Yahoo TOS) — any second user/commercial framing must switch
  to Alpha Vantage or a paid API (`integrations/market_data.py` docstring).

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/PROJECT_STATE.md` | Issue table + status snapshot (refreshed 2026-07-09) |
| `docs/assessment/REPORT.md` | Latest verdict (YES Road A) + the now-cleared SEV2 register |
| `docs/DECISIONS.md` | 3 new 2026-07-09 entries: SEV2 batch semantics, 4b pagination/encryption, yfinance TOS |
| `docs/CONTRACTS.md` | Frozen contracts — §4 now includes the arena principle keys |
| `docs/SOT.md` | Architecture/stack/tree (now incl. `routers/pagination.py`) |
| `docs/THREAT_MODEL.md` | §5 plaid ids encrypted; revisit-triggers incl. yfinance licensing |
| `docs/DEPLOYMENT.md` | Ops runbook — §7.1 deploy-OOM/swap, §8 key rotation |
| `~/.claude/ISSUES_LOG.md` | Cross-project issue log (deploy/outage gotchas) |
| `~/.claude/projects/-home-reese-workspace-CFO-analyzer/memory/MEMORY.md` | User profile + session prefs |
