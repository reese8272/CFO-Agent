# LEFT_OFF — Session Handoff Contract

> **Read this first.** This is the living "where we are right now" file. It is NOT a source-of-truth
> doc — those live in `docs/`. Update this whenever the active goal changes, and run `/close-out`
> at the end of every session.

**Last updated:** 2026-05-28
**Branch:** `main` — HEAD `d375b50` ("chore(ops): Gate 2 complete — log UX issues for next session")
**Working tree:** clean
**CI/Deploy:** both ✅ green on `main`

---

## 1. CURRENT FOCUS

**Build Issue 17 — UX: global navigation + settings/re-run intake.**

Gate 2 (manual browser walkthrough) is complete. The app is live and working at
`https://cfo.agenticlips.com`. Two UX gaps surfaced that block comfortable daily use.

### → NEXT ACTION

1. Open a GitHub issue: **"UX: global navigation + settings / re-run intake"**
2. Run the issue workflow (`/issue-workflow`) and implement:
   - **Nav:** persistent header/nav bar across all pages (`vault.html`, `intake.html`,
     `scenarios.html`, chat) — user should never be trapped in a section with no way back
   - **Settings:** a settings page or panel with a "Re-run intake wizard" button that clears
     previous intake answers and replays the `intake.html` flow
3. Run full pytest suite before closing
4. Browser-verify: navigate freely between all sections; confirm intake can be redone; confirm
   disclaimer still visible on agent responses

---

## 2. WHAT WORKS NOW (do not re-investigate)

- ✅ **`https://cfo.agenticlips.com` is live** — `/health` returns `{"status":"ok","postgres":"ok","redis":"ok"}`
- ✅ **Gate 2 complete** — HTML renders correctly; login, vault, chat, scenarios all reachable
- ✅ **Cloudflare tunnel** — CFO-Agent tunnel healthy; CNAME → `daba5893-bdc4-4104-bb9c-90668bbd85a6.cfargotunnel.com`; token rotated
- ✅ **CI green** — full pytest suite on `main`
- ✅ **Deploy pipeline green** — validate-secrets → GHCR build → SSH deploy → `/health` gate → Alembic migrations
- ✅ **`cloudflared` always restarts on deploy** — `docker compose restart cloudflared` in step 4; stale token can never persist
- ✅ **Issue 16 closed** — secrets hardening, container auto-recovery, `check_env.py --live`, `docs/DEPLOYMENT.md`

---

## 3. THE ARC THAT LED HERE

1. Issue 16 — secrets & deploy hardening; fixed failing CI + deploy; merged PR #24.
2. App went live on Oracle VM; `https://cfo.agenticlips.com` returned Cloudflare 1033.
3. Root cause: DNS CNAME pointed to an old tunnel UUID. Old tunnel was accidentally deleted; new
   tunnel created (`daba5893...`); CNAME updated manually; token rotated.
4. Site came up. Gate 2 walkthrough completed — HTML good, app functional, two UX gaps noted.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE |
| **Cloudflare Tunnel ID** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **DNS CNAME target** | `daba5893-bdc4-4104-bb9c-90668bbd85a6.cfargotunnel.com` |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Oracle VM** | `ubuntu@129.80.102.20` (SSH key is GitHub-secret-only — not in `~/.ssh/` locally) |
| **GitHub secrets (repo-level)** | `VAULT_ENCRYPTION_KEY`, `GH_PAT` |
| **GitHub secrets (Production env)** | `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `SSH_PUBLIC_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` |
| **Not yet set** | `SMTP_*` (digest emails off), `HEALTHCHECK_PING_URL` (no external watchdog) |
| **Key backup file** | `~/cfo-vault-key-BACKUP.txt` on Oracle VM — copy to Bitwarden + paper, then `shred -u` |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — run `git fetch origin && git rev-list --left-right --count origin/main...HEAD` before planning anything
- **Pushing to `main` triggers Deploy** — EXCEPT doc-only pushes (`**.md`, `docs/**` are `paths-ignore`d in `deploy.yml`)
- **SSH key for Oracle VM is GitHub-secret-only** — cannot SSH directly from local; use `gh workflow run` to run remote commands
- **If tunnel is ever deleted/recreated:** update `CLOUDFLARE_TUNNEL_TOKEN` secret, re-add public hostname in dashboard (`cfo → agenticlips.com → HTTP → app:8000`), manually update DNS CNAME to new tunnel UUID — Cloudflare does NOT auto-update the CNAME
- **Gate 3 (vault population) is still pending** — create goal/career rows in DB before first real session; see `docs/PROJECT_STATE.md`

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/PROJECT_STATE.md` | Issue table + Gates 2/3/4 status |
| `docs/DEPLOYMENT.md` | Full ops runbook: secrets map, SSH, deploy pipeline, Cloudflare troubleshooting |
| `docs/ENV_CHECKLIST.md` | Every env var: what it is, where to get it, format |
| `docs/DECISIONS.md` | All architecture decisions |
| `docs/SOT.md` | Architecture, stack, file tree, Known Production Gaps |
| `docs/WEALTH_PRINCIPLES.md` | Named principles the Coach cites |
| `~/.claude/projects/-home-reese-workspace-CFO-analyzer/memory/MEMORY.md` | User profile + session preferences |
