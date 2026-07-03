# LEFT_OFF — Session Handoff Contract

> **Read this first.** Living "where we are right now" file — NOT a source of truth (those live in
> `docs/`). Update whenever the active goal changes; run `/close-out` at the end of every session.

**Last updated:** 2026-07-03 (session 2 — Phase 5b shipped + prod outage recovered)
**Branch:** `main` HEAD `8fcd3b5` (Phase 5b #38). Working tree clean.
**CI/Deploy:** **Phase 5b is LIVE + verified** (`x-frame-options: DENY` header confirmed on prod).
Site ✅ `/health` ok, stable. Survived a full prod outage this session (see §5 — Oracle VM OOM-thrash,
recovered by `oci` reboot). **Open prevention item: swap on the Oracle VM (129.80.102.20) — see §1.**

---

## 1. CURRENT FOCUS

**The Road-A production-hardening roadmap is COMPLETE.** A full `/assess` (Phases 0–6) took the app
from **VERDICT: NO** (1 BLOCKER + ~20 SEV1) to **PRODUCTION-READY: YES (Road A)** — see
`docs/assessment/REPORT.md`. Phases 0–6 are all merged to `main` and **live in production**. Only
housekeeping + optional polish remains.

### → NEXT ACTION

1. ✅ **DONE this session** — merged PR #37 + #36; closed stale #29. Built, merged, and **DEPLOYED
   Phase 5b (#38)** — response_model on bare-dict endpoints, security-headers middleware, slim
   `migrations/env.py`. Suite 177 passed / 4 skipped. **Confirmed live in prod.** Then recovered a
   full outage that hit mid-deploy (§5).
2. ✅ **DONE — swap now auto-ensured by the deploy.** `deploy.yml` gained an idempotent, non-fatal
   `[0/6] Ensuring swap` step that creates + persists a 2G `/swapfile` before the container rollover.
   Verified live on `129.80.102.20`: deploy log showed `no swap present — creating 2G /swapfile` →
   `/swapfile file 2G` active, and the rollover reached HTTP 200 with no OOM. Self-heals every deploy.
   (Direct SSH + OCI Run Command were both unavailable to local ops — the pipeline was the way in.)
3. **(Optional) Phase 4b polish** — SEV2, none gate the YES verdict: `limit` cap on the ~17 vault GET
   list endpoints; encrypt `Account.plaid_account_id`. (5b is done — #38.)
4. **Doc reconcile (small):** the prod-host docs are actually *correct* (Oracle `129.80.102.20`); the
   confusion today was a second, unrelated box. No doc change needed beyond this note — but consider
   adding "there are TWO boxes" to `docs/DEPLOYMENT.md` so a future session doesn't SSH the wrong one.
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
5. Phase 7 re-assessment → **VERDICT: YES (Road A)**.
6. Session 2 (2026-07-03): merged #37/#36, closed #29, shipped Phase 5b (#38, live). **Mid-session prod
   outage** — the Oracle VM OOM-thrashed → cloudflared unregistered (site 530/502), SSH unresponsive.
   Recovered by rebooting the VM via the `oci` API (SOFTRESET hung → OCI force-completed). Logged
   ISSUE-2026-07-03-01. Root prevention (swap on the Oracle VM) still open.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE (Phase 5b) |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **Open PRs** | none — #37/#36/#38 merged, #29 closed |
| **Prod host (CFO)** | Oracle VM **`129.80.102.20`** = `instance-20260526-0052` (US-Ashburn). SSH `ubuntu@` — but the working key is the GitHub `SSH_PRIVATE_KEY` secret, **not** in local `~/.oci`/`~/.ssh` (local `~/.oci/vm-key*` get permission-denied). **Reboot/manage via `oci` CLI** (`~/.oci/config` works): `oci compute instance action --instance-id <ocid> --action SOFTRESET`. |
| **⚠️ NOT the CFO host** | `ssh creatorclip-vm` (DigitalOcean `ubuntu-s-4vcpu-8gb-nyc1`) runs **AutoClip/CreatorClip**, not CFO. Don't apply CFO swap/reboot there (that mistake happened this session). Its tunnel is `db79b904-…`. |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Cloudflare Tunnel ID (CFO)** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **Assessment output** | `docs/assessment/REPORT.md` + `modules/*.md` + `history/2026-07-02-REPORT-post-remediation.md` |
| **Secrets (names only)** | repo: `VAULT_ENCRYPTION_KEY`, `GH_PAT`; Prod env: `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `DEPLOY_*`, `SMTP_*`. New (optional): `VAULT_ENCRYPTION_KEYS` (comma-sep, for rotation) |
| **Local test venv** | `/tmp/cfo_venv` (py3.13; cleared on reboot — rebuild from `requirements.txt`). Playwright: `~/playwright-venv` (persistent) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — parallel Claude branches merge to main; run `git fetch origin && git rev-list --left-right --count origin/main...HEAD` before planning.
- **Pushing to `main` triggers Deploy** — EXCEPT doc-only pushes (`**.md`, `docs/**` are `paths-ignore`d). PRs #36/#37 are doc-only → safe to merge with no deploy.
- **Deploy can transiently 502 (ARM-VM OOM)** — ISSUE-2026-07-02-02: a rollout OOM-kills the app (`status 137` + "name resolution" in the deploy log) → 502. **Recover: `gh run rerun <run-id> --failed`. Prevent: add VM swap (`docs/DEPLOYMENT.md §7.1`) — still pending.** Distinguish from ISSUE-2026-07-02-01 (command_timeout; app stays up).
- **Full outage = Oracle VM OOM-thrash (ISSUE-2026-07-03-01)** — if the site flaps `530`/`1033`/"unregistered from Argo Tunnel" ↔ `502` ↔ `000` AND `ssh ubuntu@129.80.102.20` banner-times-out, the VM is thrashing (not a network/code fault). **Recover out-of-band via `oci` (SSH is unusable): `oci compute instance action --instance-id <ocid> --action SOFTRESET`** (find OCID via `oci compute instance list -c <tenancy> --all`). SOFTRESET may hang in STOPPING ~5min (OS wedged) — OCII force-completes it to RUNNING; containers auto-start, tunnel re-registers, `/health` green ~2min. Then re-run the deploy. **Mitigated 2026-07-03:** `deploy.yml`'s `[0/6] Ensuring swap` now guarantees 2G swap on the host, so the rollover has headroom (recurrence risk much lower).
- **TWO boxes exist — don't confuse them.** Prod CFO = Oracle `129.80.102.20`. `ssh creatorclip-vm` = a *different* DigitalOcean box (AutoClip/CreatorClip). Verify a host runs CFO (checkout dir + `*cfo*` container + tunnel `daba5893-…`) before touching it.
- **Local pytest needs a real DB** — no local Postgres role exists. Spin a throwaway: `initdb -D /tmp/cfo_pg -U cfo --auth=trust`; `pg_ctl -D /tmp/cfo_pg -o "-p 5433 -k /tmp" start`; `createdb -h localhost -p 5433 -U cfo personal_cfo`; then `DATABASE_URL=postgresql+psycopg://cfo:cfo@localhost:5433/personal_cfo REDIS_URL=redis://localhost:6379/15 TESTING=true` + the conftest env defaults, `alembic upgrade head`, `pytest`. Build the venv with `python3.13` (system python is 3.14 → no psycopg wheel).
- **SSH to the Oracle VM is GitHub-secret-only** — local `~/.oci/vm-key*` are not authorized (`ubuntu@` → permission denied), so the swap must be applied by the owner or baked into `deploy.yml`. BUT VM power management works via the `oci` CLI locally (reboot without SSH — see the outage gotcha above).
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
