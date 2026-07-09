# LEFT_OFF — Session Handoff Contract

> **Read this first.** Living "where we are right now" file — NOT a source of truth (those live in
> `docs/`). Update whenever the active goal changes; run `/close-out` at the end of every session.

**Last updated:** 2026-07-09 (session 3 close — backlog fully cleared, Gate 2 done, prod demoable)
**Branch:** `main` HEAD `860d017`. Working tree clean; in sync with origin. CI/Deploy all green.
**Site:** ✅ `https://cfo.agenticlips.com` — `/health` ok; **owner confirmed they know the prod
login password → the app is fully demoable in prod today.**

---

## 1. CURRENT FOCUS

**Nothing is in flight.** Session 3 shipped six PRs (#41 #42 #43 #45 #46 #47) that cleared the
entire post-YES backlog: the 2026-07-03 assessment SEV2 register, Phase 4b, both observability
activations, issue #44, and the Gate 2 browser walkthrough (which found and fixed 3 more real
bugs). The only deferred work is **Road B (multi-tenant)** — by explicit decision.

### → NEXT ACTION (when a next session starts)

1. `git fetch origin && git rev-list --left-right --count origin/main...HEAD` — verify main
   currency first (parallel sessions merge to main).
2. Pick up whatever the owner asks; there is no queued work. Candidate next arcs, in rough value
   order:
   - **Password-reset path** for the single prod user (none exists; owner knows the password
     today, but recovery = pipeline-driven DB edit if ever lost).
   - **Auto-refresh the financial snapshot on vault mutations** (today: agent reasons over the
     intake-time snapshot until `POST /intake/snapshot/refresh`; demo tip documented below).
   - **Road B** — tenant isolation (`user_id` + RLS), cursor pagination, licensed market data,
     full CLAUDE.md Pre-GA block (`docs/DECISIONS.md` 2026-07-02 scope decision).

---

## 2. WHAT WORKS NOW (verified — do not re-investigate)

- ✅ **Prod demoable end-to-end**: login → vault HTMX forms (creates fixed via `json-enc` — they
  had NEVER worked, see ISSUE-2026-07-09-01) → chat returns ONE principle-cited, vision-stamped,
  disclaimer-carrying recommendation in ~30 s → `$1M` scenario renders months + compounding trace.
  Walked through with Playwright + real Anthropic key; all 7 Gate 2 checks pass
  (`docs/PROJECT_STATE.md` → Gate 2).
- ✅ **Observability LIVE + verified**: healthchecks.io dead-man's-switch (check "CFO prod ping",
  5 min period/grace, email alerts; dashboard showed pings arriving) and Sentry (DSN set, inert
  until first unhandled error). Both delivered via deploy.yml → prod `.env` (#45).
- ✅ **Assessment SEV2 register: cleared** (#41 six correctness fixes, #42 pagination caps on 20
  endpoints + `plaid_account_id_encrypted`, #43 no-store/annotations/yfinance-TOS). Itemized in
  `docs/PROJECT_STATE.md`.
- ✅ **Disclaimer enforcement is now layered**: LLM flags OR proposals OR the deterministic keyword
  backstop `disclaimer.text_requires_disclaimer()` (#47 — added after Gate 2 caught a real miss).
- ✅ **Error states on all vault forms** (#46): inline dismissible banners, input preserved on
  failure, busy state; silent failures are no longer possible.
- ✅ Tests **193 passed / 3 skipped** (py3.13 + live PG/Redis), `tests/eval/` 4/4, ruff clean.
  Alembic head `b9d3e6f1a825` applied in prod.

---

## 3. THE ARC THAT LED HERE

1. Sessions 1–2: build (Issues 1–19) → `/assess` NO → 8-phase Road-A hardening → **YES** →
   Top-5 fixes + Sentry code (#39/#40).
2. Session 3 (2026-07-09): severity-ordered the leftovers, then shipped ALL of it — #41 SEV2
   batch → #42 Phase 4b → #43 sweep (closed GH #28) → #45 secrets plumbing → activated
   healthchecks.io (automated via Playwright + Gmail magic-link) & Sentry (owner did captcha) →
   #46 error states, which exposed that vault creates never worked (json-enc fix) → Gate 2
   walkthrough, which caught a disclaimer miss (keyword backstop) + scenario step-grid bug (#47).
3. Pattern that worked: every PR = local suite → CI → owner-approved merge → deploy → live
   verification; every non-obvious root cause → `~/.claude/ISSUES_LOG.md`.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` — no open PRs, no open issues |
| **Prod host (CFO)** | Oracle VM **`129.80.102.20`** (`instance-20260526-0052`, US-Ashburn). SSH only via the GitHub `SSH_PRIVATE_KEY` secret; power-manage via `oci` CLI (`~/.oci/config`). |
| **⚠️ NOT the CFO host** | `ssh creatorclip-vm` (DigitalOcean) = AutoClip/CreatorClip. Verify before touching. |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Cloudflare Tunnel ID (CFO)** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **Alembic head** | `b9d3e6f1a825` ← `f2c8a1b7d403` |
| **healthchecks.io** | account = owner Gmail (passwordless login); project `7db194d0-f8c1-43ff-8eba-a3e355323770`, check `31c1d142-e68d-4e5b-b747-ae23a5f0315a` ("CFO prod ping") |
| **Sentry** | org `o4511706759888896` (US), owner-created; DSN in GitHub secret |
| **Secrets (names only)** | repo: `VAULT_ENCRYPTION_KEY`, `GH_PAT`, `HEALTHCHECK_PING_URL`, `SENTRY_DSN`; Prod env: `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `DEPLOY_*`, `SMTP_*` |
| **Local test env** | venv `/tmp/cfo_venv` (py3.13; rebuild after reboot), throwaway PG on 5433, Redis 6379; Playwright at `~/playwright-venv` (persistent) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — parallel Claude branches merge to main.
- **Pushing to `main` triggers Deploy** — except doc-only (`**.md`, `docs/**` paths-ignore'd);
  `.github/**` DOES deploy. Deploy also supports `workflow_dispatch`.
- **Merging PRs needs explicit per-PR owner approval** (permission gate blocks self-merge).
- **Prod login**: single user, registration closed (409), **no password-reset endpoint** — owner
  knows the credential (confirmed 2026-07-09). If ever lost: pipeline-driven DB hash reset.
- **Snapshot freshness**: agent reasons over the intake-time `financial_snapshot`; after direct
  vault edits call `POST /intake/snapshot/refresh` (settings) or the agent won't see the change.
- **Digest idempotency semantics are intentional** (cron skips a sent week; `/run-now` always
  sends but logs) — DECISIONS 2026-07-09; don't "fix" one to match the other.
- **yfinance is personal-use only** (Yahoo TOS) — second user/commercial ⇒ Alpha Vantage/paid API.
- **Deploy OOM lore**: transient 502 → `gh run rerun <id> --failed`; full outage (site flaps
  530/502/000 + SSH banner-timeout) → `oci ... --action SOFTRESET`. Swap auto-ensured by deploy.
- **Local pytest needs real PG**: `initdb -D /tmp/cfo_pg -U cfo --auth=trust`; `pg_ctl -D
  /tmp/cfo_pg -o "-p 5433 -k /tmp" start`; `createdb -h localhost -p 5433 -U cfo personal_cfo`;
  build venv with **python3.13**; `DATABASE_URL=postgresql+psycopg://cfo:cfo@localhost:5433/personal_cfo
  REDIS_URL=redis://localhost:6379/15 alembic upgrade head && pytest`. Stale rows from a prior
  key → Fernet `InvalidToken` 500s: truncate, don't debug (it's not a code bug).

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/PROJECT_STATE.md` | Issue table + Gate 2 walkthrough record (refreshed 2026-07-09) |
| `docs/assessment/REPORT.md` | YES (Road A) verdict; SEV2 register (now fully cleared) |
| `docs/DECISIONS.md` | 2026-07-09 entries: SEV2 semantics, 4b pagination/encryption, yfinance TOS |
| `docs/CONTRACTS.md` | Frozen contracts — §4 includes arena principle keys |
| `docs/SOT.md` · `docs/THREAT_MODEL.md` · `docs/DEPLOYMENT.md` | Architecture / security / ops runbook |
| `~/.claude/ISSUES_LOG.md` | ISSUE-2026-07-09-01 (json-enc), outage + deploy lore |
| `~/.claude/projects/-home-reese-workspace-CFO-analyzer/memory/MEMORY.md` | User profile + workflow prefs |
