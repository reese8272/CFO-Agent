# LEFT_OFF — Session Handoff Contract

> **Read this first.** This is the living "where we are right now" file. It is NOT a source-of-truth
> doc — those live in `docs/`. Update this whenever the active goal changes, and run `/close-out`
> at the end of every session.

**Last updated:** 2026-05-27
**Branch:** `main` — HEAD `9f300ce` ("chore(ops): close out Issue 16 — deploy live")
**Working tree:** clean (this file + `docs/SOT.md` staged in next commit)
**CI/Deploy:** both ✅ green on `main`

---

## 1. CURRENT FOCUS

**Get `https://cfo.agenticlips.com` serving the app through the Cloudflare Tunnel.**

The app is deployed and healthy on the Oracle Cloud VM; CI and Deploy pipelines are both green.
The public URL still returns **Cloudflare error 1033** — the `cloudflared` connector is not
bridging traffic from the correct tunnel to the app.

### → NEXT ACTION

1. **Check if it's already fixed:**
   ```
   curl -sS https://cfo.agenticlips.com/health
   ```
   If `{"status":"ok",...}` → done, skip the rest.

2. **Cloudflare dashboard** ([one.dash.cloudflare.com](https://one.dash.cloudflare.com) →
   Networks → Tunnels):
   - Is the tunnel that holds `cfo.agenticlips.com` **HEALTHY** or **DOWN/Inactive**?
   - The token shown under "configure connector" for that tunnel **must match** the
     `CLOUDFLARE_TUNNEL_TOKEN` GitHub Production secret.
   - Public Hostname: `cfo.agenticlips.com` → **Service = `http://app:8000`** (compose
     service name — NOT `localhost:8000`, which points at the cloudflared container itself).

3. **If token mismatch / tunnel was recreated:** update the secret and redeploy:
   ```
   gh secret set CLOUDFLARE_TUNNEL_TOKEN --env Production --body "<token>"
   gh workflow run Deploy
   gh run watch $(gh run list --workflow Deploy --limit 1 --json databaseId -q '.[0].databaseId')
   ```

4. **To read cloudflared container logs directly** (needs the Oracle VM IP — see §4):
   ```
   ssh ubuntu@<oracle-ip> 'docker logs --tail 50 cfo-agent-cloudflared-1'
   ```
   Look for `Registered tunnel connection` (healthy) or an auth/not-found error.

**Most likely cause:** The `CLOUDFLARE_TUNNEL_TOKEN` in the secret belongs to one tunnel but
`cfo.agenticlips.com` is attached to a different tunnel (or a refreshed token wasn't synced to
the running container). The owner refreshed the token during the session
(replica `30bbd6ec-d50a-4c69-a17f-dc84471e3ec6`, tunnel `d06fc391-642a-4529-ae9c-f3dadf56a284`)
but the 1033 persisted — meaning either the container wasn't redeployed with the new token, or the
hostname is still on a different tunnel.

---

## 2. WHAT WORKS NOW (do not re-investigate)

- ✅ **CI green** — full pytest suite on `main` (153 tests, 0 failures)
- ✅ **Deploy pipeline green** (validate-secrets → GHCR build → SSH deploy → `/health` 200 gate →
  Alembic migrations). Last two runs both `success`.
- ✅ **App is up and healthy on the VM** — postgres, redis, autoheal, cloudflared all start;
  `/health` returns 200 *locally on the box*; scheduler runs; DB + Redis connect.
- ✅ **GHCR image** builds fine: `ghcr.io/reese8272/cfo-agent:latest`
- ✅ **Issue 16 fully closed** — secrets registry, deploy gate fix, container auto-recovery
  (`autoheal` + `restart: unless-stopped` + healthcheck), `check_env.py --live` doctor,
  `docs/DEPLOYMENT.md` runbook, `LEFT_OFF.md` + `/close-out` command.
- ✅ **`/close-out` command** installed at `~/.claude/commands/close-out.md` (global, works in any repo)
- ✅ **`VAULT_ENCRYPTION_KEY`** regenerated fresh; backed up to `~/cfo-vault-key-BACKUP.txt`
  (owner still needs to copy to Bitwarden + paper, then `shred -u` the file)

The ONLY remaining gap is the Cloudflare tunnel bridge.

---

## 3. THE ARC THAT LED HERE

1. Session started on a question about managing too many secret keys.
2. Opened **Issue 16 — Secrets & Deploy Operations Hardening**; found `main` was 68 commits ahead
   of the working branch, and both CI and Deploy were red.
3. Fixed 9 failing CI tests (Decimal-in-JSON, `_round100` ceiling, `EXPECTED_TABLES`, income
   multi-counting bug in `compute_income_position`).
4. Fixed the deploy gate (audit rejected its own JWT placeholder), cleaned up clutter secrets.
5. Added container auto-recovery, `check_env.py --live` doctor, `docs/DEPLOYMENT.md` runbook.
6. Regenerated + backed up `VAULT_ENCRYPTION_KEY`; merged PR #24.
7. Drove the deploy to green through 3 fixes: DEPLOY_PATH permissions, curl→urllib health probe,
   `paths-ignore` for doc pushes.
8. App is live on VM; public site (`https://cfo.agenticlips.com`) still blocked by Cloudflare 1033.
9. Wrote `LEFT_OFF.md` and created the global `/close-out` command.

---

## 4. KEY COORDINATES & FACTS

| Thing | Value |
|---|---|
| **Public URL** | `https://cfo.agenticlips.com` (only this subdomain has DNS — apex + www don't) |
| **Cloudflare Tunnel ID** | `d06fc391-642a-4529-ae9c-f3dadf56a284` |
| **Last seen connector replica** | `30bbd6ec-d50a-4c69-a17f-dc84471e3ec6` |
| **GitHub repo** | `github.com/reese8272/CFO-Agent` |
| **GHCR image** | `ghcr.io/reese8272/cfo-agent:latest` |
| **Deploy user** | `ubuntu` (Oracle Cloud ARM VM — separate from the DigitalOcean `147.182.136.107` box) |
| **Oracle VM IP** | Unknown locally — `DEPLOY_HOST` is a write-only GitHub secret; find it at cloud.oracle.com → Compute → Instances |
| **GitHub secrets (repo-level)** | `VAULT_ENCRYPTION_KEY`, `GH_PAT` |
| **GitHub secrets (Production env)** | `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `SSH_PUBLIC_KEY`, `DEPLOY_HOST`, `DEPLOY_USER`, `DEPLOY_PATH` |
| **Not yet set** | `SMTP_*` (digest emails off), `HEALTHCHECK_PING_URL` (no external watchdog) |
| **App pages** | `/` → `/static/login.html` (register first, then chat/vault/intake/scenarios) |
| **Key backup file** | `~/cfo-vault-key-BACKUP.txt` (owner action: copy to Bitwarden + paper, then `shred -u`) |

---

## 5. CONSTRAINTS & GOTCHAS

- **Verify `origin/main` first** — parallel Claude branches merge here; `main` is the real trunk
  and can be far ahead of any feature branch. Run `git fetch origin && git rev-list --left-right
  --count origin/main...HEAD` before planning anything.
- **Check `gh run list` early** — CI/Deploy state changes scope entirely.
- **GitHub secrets are write-only** — you can never read a secret value back. Don't try. The owner
  reads values from their local `.env` or Bitwarden.
- **Pushing to `main` triggers Deploy** — EXCEPT doc-only pushes (`**.md`, `docs/**` are
  `paths-ignore`d in `deploy.yml`). So pushing `LEFT_OFF.md` alone won't redeploy.
- **Cloudflare service URL must be `app:8000`** — not `localhost:8000`. The `cloudflared` container
  uses Docker Compose networking; `localhost` inside cloudflared points at itself.
- **Oracle VM ≠ `147.182.136.107`** — that's the existing DigitalOcean CreatorClip box (`root`
  user). CFO is on a separate Oracle Cloud instance (`ubuntu` user). Don't cross them.
- **Owner is solo, $0 budget** — always recommend the simplest/free option first.
- **Deferred hardening:** `docker-compose.prod.yml` override to drop bind-mount + `--reload`
  (app currently runs with `--reload` and a source bind-mount; it works but the GHCR image isn't
  fully authoritative). Tracked in `docs/SOT.md` Known Production Gaps.

---

## 6. POINTERS

| Doc | Purpose |
|---|---|
| `docs/DEPLOYMENT.md` | Full ops runbook: secrets sync map, SSH key map, Oracle/Cloudflare setup, deploy pipeline, key-rotation, troubleshooting (§9 covers 1033, permission denied, curl-not-in-image) |
| `docs/ENV_CHECKLIST.md` | Every env var: what it is, where to get it, format, tiered by importance |
| `docs/DECISIONS.md` | Issue 16 decision entry (2026-05-27) + all architecture decisions |
| `docs/PROJECT_STATE.md` | Issue table (Issue 16 = Closed; Gate 4 = LIVE) + owner follow-ups |
| `docs/SOT.md` | Architecture, stack, file tree, Known Production Gaps |
| `docs/THREAT_MODEL.md` | Security posture, key-handling rules |
| `~/.claude/projects/-home-reese-workspace-CFO-analyzer/memory/MEMORY.md` | User profile + "verify main first" reminder |
