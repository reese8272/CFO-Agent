# LEFT_OFF — Session Handoff Contract

> **Read this first.** This is the living "where we are right now" file. It is NOT a source-of-truth
> doc — those live in `docs/`. Update this whenever the active goal changes, and run `/close-out`
> at the end of every session.

**Last updated:** 2026-05-28
**Branch:** `main` — HEAD `2d8f700` ("fix(deploy): always restart cloudflared after docker compose up")
**Working tree:** clean
**CI/Deploy:** both ✅ green on `main`

---

## 1. CURRENT FOCUS

**`https://cfo.agenticlips.com` is LIVE and healthy. ✅**

The Cloudflare tunnel issue is fully resolved. The site serves the app end-to-end.

### → NEXT ACTION

**Gate 2 — Manual browser walkthrough (owner action required):**
1. Open `https://cfo.agenticlips.com` in a browser
2. Register an account, then log in
3. Add at least one account, one debt, one income stream in the vault
4. Open chat — ask "where am I financially?" — verify agent responds with a single concrete recommendation
5. Run scenario: "How long to $1M at current trajectory?" — verify months and monthly breakout render
6. Confirm disclaimer visible on every agent response

After Gate 2 passes, move on to **Gate 3 — Vault population** (see `docs/PROJECT_STATE.md`).

---

## 2. WHAT WORKS NOW (do not re-investigate)

- ✅ **`https://cfo.agenticlips.com` is live** — `/health` returns `{"status":"ok","postgres":"ok","redis":"ok"}`
- ✅ **Cloudflare tunnel** — CFO-Agent tunnel healthy; CNAME points to correct tunnel UUID; token rotated and secured
- ✅ **CI green** — full pytest suite on `main` (153 tests, 0 failures)
- ✅ **Deploy pipeline green** — validate-secrets → GHCR build → SSH deploy → `/health` 200 gate → Alembic migrations
- ✅ **cloudflared always restarts on deploy** — `docker compose restart cloudflared` added to step 4 of deploy script; stale token can never persist across deploys again
- ✅ **App is up on the Oracle VM** — postgres, redis, autoheal, cloudflared all healthy
- ✅ **Issue 16 fully closed** — secrets registry, deploy gate, container auto-recovery, `check_env.py --live`, `docs/DEPLOYMENT.md`, `LEFT_OFF.md`, `/close-out` command
- ✅ **`VAULT_ENCRYPTION_KEY`** — regenerated fresh; owner still needs to copy `~/cfo-vault-key-BACKUP.txt` to Bitwarden + paper, then `shred -u` the file

---

## 3. THE ARC THAT LED HERE

1. Session started on Issue 16 — secrets & deploy operations hardening.
2. Fixed 9 failing CI tests; fixed deploy gate; added container auto-recovery; merged PR #24.
3. App went live on Oracle VM but `https://cfo.agenticlips.com` returned Cloudflare 1033.
4. Root cause: DNS CNAME for `cfo.agenticlips.com` pointed to an old tunnel UUID (`a439dd38...`) from a previous tunnel creation. The running tunnel (`d06fc391...`) had the public hostname configured but the CNAME never updated.
5. During diagnosis, the old tunnel was accidentally deleted. A new tunnel was created (`daba5893...`).
6. New token set as GitHub secret; deploy restarted cloudflared; public hostname re-added in dashboard; CNAME manually updated to new tunnel UUID.
7. Site came up. Token then rotated for security (was briefly exposed in chat); redeployed with rotated token.
8. Site confirmed live with rotated token.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` ✅ LIVE |
| **Cloudflare Tunnel ID** | `daba5893-bdc4-4104-bb9c-90668bbd85a6` |
| **DNS CNAME target** | `daba5893-bdc4-4104-bb9c-90668bbd85a6.cfargotunnel.com` |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Deploy user** | `ubuntu` on Oracle Cloud ARM VM (`129.80.102.20`) |
| **GitHub secrets (repo-level)** | `VAULT_ENCRYPTION_KEY`, `GH_PAT` |
| **GitHub secrets (Production env)** | `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `SSH_PUBLIC_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` |
| **Not yet set** | `SMTP_*` (digest emails off), `HEALTHCHECK_PING_URL` (no external watchdog) |
| **Key backup file** | `~/cfo-vault-key-BACKUP.txt` (owner action: copy to Bitwarden + paper, then `shred -u`) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — run `git fetch origin && git rev-list --left-right --count origin/main...HEAD` before planning anything
- **Cloudflare service URL must be `app:8000`** — not `localhost:8000`; `cloudflared` uses Docker Compose networking
- **cloudflared always restarts on deploy now** — `docker compose restart cloudflared` is in step 4 of deploy script
- **If tunnel is ever deleted/recreated**: update `CLOUDFLARE_TUNNEL_TOKEN` secret, re-add public hostname in dashboard (`cfo → agenticlips.com → http → app:8000`), and manually update DNS CNAME to the new tunnel UUID — Cloudflare does NOT auto-update the CNAME when you re-add a hostname to a different tunnel
- **SSH key for Oracle VM** is GitHub-secret-only (RSA 2048, fingerprint `SHA256:2FueIWfNzYJzu/P9zEu6USU6ZUkz15fly2qblR154y0`) — not in `~/.ssh/` locally
- **Owner is solo, $0 budget** — always recommend the simplest/free option first

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/DEPLOYMENT.md` | Full ops runbook: secrets sync map, SSH key map, Oracle/Cloudflare setup, deploy pipeline, key-rotation, troubleshooting |
| `docs/ENV_CHECKLIST.md` | Every env var: what it is, where to get it, format, tiered by importance |
| `docs/DECISIONS.md` | All architecture decisions including Issue 16 |
| `docs/PROJECT_STATE.md` | Issue table + owner follow-ups (Gates 2 & 3 remaining) |
| `docs/SOT.md` | Architecture, stack, file tree, Known Production Gaps |
| `docs/THREAT_MODEL.md` | Security posture, key-handling rules |
