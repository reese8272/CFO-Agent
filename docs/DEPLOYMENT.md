# Deployment & Operations Runbook

> **Disclaimer**: This tool is for financial education and personal organization. It is not a
> licensed financial advisor. For tax strategy, real estate transactions, and investment
> decisions, consult a licensed professional.

The end-to-end guide for getting `personal-cfo` running in production and keeping it healthy.
Single-user v1. Everything here assumes the owner is the only operator.

**Companion docs:**
- `docs/ENV_CHECKLIST.md` — per-secret acquisition instructions (what each key is, where to get it)
- `docs/THREAT_MODEL.md` — security posture and key-handling rules
- `docs/SOT.md` — architecture and stack

---

## 1. Architecture at a glance

```
        you ──HTTPS──► Cloudflare edge ──tunnel──► cloudflared container ──► app:8000
                                                                              │
                                          ┌───────────────────────────────────┤
                                          ▼                                   ▼
                                     postgres:5432                       redis:6379
```

All services run as Docker Compose containers on one host (Oracle Cloud Free ARM VM).
No inbound ports are opened on the VM — Cloudflare Tunnel dials *out*, so the only
public surface is your Cloudflare domain.

| Container | Image | Purpose |
|---|---|---|
| `app` | `ghcr.io/reese8272/cfo-agent` (built in CI) | FastAPI + agent |
| `postgres` | `postgres:16-alpine` | vault + memory |
| `redis` | `redis:7-alpine` | agent state / cache |
| `cloudflared` | `cloudflare/cloudflared` | tunnel to Cloudflare edge |
| `autoheal` | `willfarrell/autoheal` | restarts unhealthy containers |

---

## 2. Secrets: where they live (source of truth)

**Rule of thumb:** GitHub Actions secrets are *write-only* — you cannot read them back.
So GitHub is **not** your system of record; it is a delivery copy. Your readable master
copy lives in a password manager.

### The sync map

| Secret | Master copy (read-back) | Used by CI/deploy | Lands on VM as |
|---|---|---|---|
| `VAULT_ENCRYPTION_KEY` 🔴 | **Bitwarden + paper** | GitHub repo secret | `.env` (written by deploy) |
| `ANTHROPIC_API_KEY` | Bitwarden | GitHub *Production* env secret | `.env` |
| `CLOUDFLARE_TUNNEL_TOKEN` | Bitwarden | GitHub *Production* env secret | `.env` |
| `GH_PAT` | Bitwarden | GitHub repo secret | (used to clone + GHCR login) |
| `SSH_PRIVATE_KEY` | Bitwarden (or `~/.ssh`) | GitHub *Production* env secret | (used to SSH in) |
| `DEPLOY_HOST` / `DEPLOY_USER` / `DEPLOY_PATH` | Bitwarden / this doc | GitHub *Production* env secret | (SSH target) |
| `SMTP_HOST/USER/PASSWORD/FROM` | Bitwarden | GitHub *Production* env secret (optional) | `.env` |
| `JWT_SECRET_KEY` | — (not stored) | — | generated fresh each deploy |

🔴 = **irreplaceable.** If `VAULT_ENCRYPTION_KEY` is lost, every encrypted column
(balances, account numbers, addresses) becomes permanently unreadable. Keep **three**
copies in **two** formats: Bitwarden, a second password-manager entry or file, and a
printed paper copy stored physically.

> `JWT_SECRET_KEY` is intentionally **not** a stored secret — the deploy script generates a
> fresh one with `openssl rand -hex 32` every run. Each deploy logs you out; acceptable for
> single-user. For local dev only, put one in your `.env`.

### Where to set them on GitHub

- **Repo-level** (Settings → Secrets and variables → Actions → *Repository secrets*):
  `VAULT_ENCRYPTION_KEY`, `GH_PAT`
- **Production environment** (Settings → Environments → `Production` → *Environment secrets*):
  `ANTHROPIC_API_KEY`, `CLOUDFLARE_TUNNEL_TOKEN`, `SSH_PRIVATE_KEY`, `DEPLOY_HOST`,
  `DEPLOY_USER`, `DEPLOY_PATH`, and the four `SMTP_*` (optional)

Repo-level secrets are visible to environment-scoped jobs, which is why
`VAULT_ENCRYPTION_KEY` / `GH_PAT` can live at repo level and still be read by the
Production deploy job.

---

## 3. SSH keys: one key per purpose

The cause of "which key goes where" confusion is reusing one key everywhere. Don't.
Use **ed25519** (not RSA), name each key for its job, and never copy a *private* key
between machines.

```bash
# On your laptop — generate two keys, one per purpose:
ssh-keygen -t ed25519 -C "laptop→oracle-vm"   -f ~/.ssh/id_ed25519_oracle_vm
ssh-keygen -t ed25519 -C "github-actions→vm"  -f ~/.ssh/id_ed25519_gh_deploy
```

| Key | Private half lives | Public half goes to |
|---|---|---|
| `id_ed25519_oracle_vm` | your laptop `~/.ssh/` only | VM `~/.ssh/authorized_keys` |
| `id_ed25519_gh_deploy` | GitHub `SSH_PRIVATE_KEY` secret (paste full file) | VM `~/.ssh/authorized_keys` |

Add the public keys to the VM:
```bash
ssh-copy-id -i ~/.ssh/id_ed25519_oracle_vm.pub  <user>@<vm-ip>   # your interactive access
# For the CI key, append its .pub to the VM's authorized_keys the same way:
cat ~/.ssh/id_ed25519_gh_deploy.pub | ssh <user>@<vm-ip> 'cat >> ~/.ssh/authorized_keys'
```

Put the CI key's **private** half into GitHub (Production env secret `SSH_PRIVATE_KEY`) —
paste the entire file including the `-----BEGIN/END OPENSSH PRIVATE KEY-----` lines and the
trailing newline. (Run `check_env`'s SSH check / `audit_secrets.py` to confirm it parses.)

Add a `~/.ssh/config` block on your laptop so you never type the IP again:
```
Host cfo-vm
    HostName <vm-ip>
    User <user>
    IdentityFile ~/.ssh/id_ed25519_oracle_vm
    IdentitiesOnly yes
```
Then: `ssh cfo-vm`.

> The repo currently also stores an `SSH_PUBLIC_KEY` secret. Public keys aren't secret, so
> it's harmless clutter — safe to delete if you want a cleaner secret list.

---

## 4. One-time setup (interactive checklist)

### 4a. Provision the Oracle Cloud Free ARM VM
- [ ] Sign in at **cloud.oracle.com** → hamburger menu → **Compute → Instances**
- [ ] **Create Instance**. Image: Canonical Ubuntu 22.04 (or 24.04). Shape: **Ampere `VM.Standard.A1.Flex`** (Always Free eligible — give it ~2 OCPU / 12 GB if available)
- [ ] Under **Add SSH keys**, upload `~/.ssh/id_ed25519_oracle_vm.pub`
- [ ] Create. Note the **public IP** → this is `DEPLOY_HOST`. The default user is `ubuntu` → `DEPLOY_USER`
- [ ] Confirm access: `ssh cfo-vm` (using the config block above)

### 4b. Install Docker on the VM
```bash
ssh cfo-vm
curl -fsSL https://get.docker.com | sudo sh
sudo usermod -aG docker $USER && exit   # re-login so the group applies
ssh cfo-vm 'docker compose version'      # confirm compose v2
```
- [ ] Choose a deploy path, e.g. `/home/ubuntu/personal-cfo` → this is `DEPLOY_PATH`

### 4c. Cloudflare Tunnel
- [ ] **one.dash.cloudflare.com** (Zero Trust) → **Networks → Tunnels → Create a tunnel**
- [ ] Connector type: **Cloudflared**. Name it `cfo`. Copy the **token** from the
      `--token <TOKEN>` install command → this is `CLOUDFLARE_TUNNEL_TOKEN`
      (the `cloudflared` container uses it; you do **not** install cloudflared manually)
- [ ] **Public Hostname**: pick your subdomain (e.g. `cfo.yourdomain.com`), service =
      `http://app:8000` (the compose service name + port)
- [ ] Set `ALLOWED_ORIGINS=["https://cfo.yourdomain.com"]` (see ENV_CHECKLIST) before going live

### 4d. Generate the irreplaceable key + back it up
```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```
- [ ] Save the output in **Bitwarden**, a **second** location, and on **paper**
- [ ] Set it as the repo-level GitHub secret `VAULT_ENCRYPTION_KEY`

### 4e. Set all GitHub secrets
Use the lists in §2. Quick CLI alternative (run from the repo):
```bash
gh secret set VAULT_ENCRYPTION_KEY --body "<key>"            # repo-level
gh secret set GH_PAT               --body "<pat>"            # repo-level
gh secret set ANTHROPIC_API_KEY       --env Production --body "<key>"
gh secret set CLOUDFLARE_TUNNEL_TOKEN --env Production --body "<token>"
gh secret set DEPLOY_HOST --env Production --body "<vm-ip>"
gh secret set DEPLOY_USER --env Production --body "ubuntu"
gh secret set DEPLOY_PATH --env Production --body "/home/ubuntu/personal-cfo"
gh secret set SSH_PRIVATE_KEY --env Production < ~/.ssh/id_ed25519_gh_deploy
```
- [ ] Verify: `gh secret list` and `gh secret list --env Production`

`GH_PAT` is a fine-grained or classic PAT with **repo** (clone) + **read:packages** (GHCR
pull) scope. It's used by the deploy script to clone the repo and `docker login ghcr.io`.

---

## 5. How a deploy works (`.github/workflows/deploy.yml`)

Triggered on **push to `main`** or manually (**Actions → Deploy → Run workflow**). Three jobs:

1. **validate-secrets** — runs `scripts/audit_secrets.py` against the Production secrets.
   Fails fast (before building anything) if a required secret is missing or malformed.
2. **build** — `docker buildx` builds the image and pushes
   `ghcr.io/reese8272/cfo-agent:latest` + `:<sha>` to GHCR. (Building happens on GitHub's
   runners, **not** the VM — this is why deploys are fast and don't OOM the little ARM box.)
3. **deploy** — SSHes into the VM and runs a 6-step script:
   1. clone/`git reset --hard origin/main` into `DEPLOY_PATH`
   2. write `.env` from the secrets (generates a fresh `JWT_SECRET_KEY`)
   3. `docker login ghcr.io` + `docker compose pull app`
   4. `docker compose up -d --no-build --remove-orphans`
   5. **health gate** — poll `http://localhost:8000/health` for up to 90s; on failure it
      dumps the app logs and the job **fails** (the containers are left as-is — see rollback)
   6. `alembic upgrade head` if not already at head

**Known limitation — bind mount + `--reload`:** the compose `app` service still bind-mounts
the host repo (`.:/app`) and runs `uvicorn --reload`, so the app executes the host's
git-checked-out code while the GHCR image supplies the installed dependencies. It works, but
a future hardening step is a `docker-compose.prod.yml` override that drops the bind mount and
`--reload` so the prebuilt image is authoritative. Tracked as a follow-up.

---

## 6. Deploying

```bash
# Normal path: merge/push to main → Deploy runs automatically.
git push origin main

# Manual re-deploy of current main (e.g. after rotating a secret):
gh workflow run Deploy
gh run watch "$(gh run list --workflow Deploy --limit 1 --json databaseId -q '.[0].databaseId')"
```

**Rollback** (there is no automatic rollback today):
- Fastest: `git revert <bad-sha> && git push origin main` → redeploys the previous good state.
- Manual on the VM: `ssh cfo-vm`, `cd $DEPLOY_PATH`, then
  `docker compose pull app && docker compose up -d` after checking out a known-good image tag
  (`docker images ghcr.io/reese8272/cfo-agent` lists pulled SHAs).

---

## 7. Operations

```bash
ssh cfo-vm
cd /home/ubuntu/personal-cfo            # = DEPLOY_PATH

docker compose ps                        # container status + health
docker compose logs --tail 100 app       # app logs
docker compose logs --tail 50 cloudflared
curl -sf localhost:8000/health | jq      # {status, postgres, redis}
docker compose restart app               # manual restart
python3 scripts/check_env.py --live      # verify every credential actually works
```

**Auto-recovery (already wired in `docker-compose.yml`):**
- `restart: unless-stopped` on every service → survives crashes and VM reboots.
- `autoheal` watches containers labeled `autoheal=true` (the `app`) and restarts any that
  Docker marks **unhealthy** — covers the hung-but-not-exited case that `restart` misses.
- **External watchdog (optional, recommended):** set `HEALTHCHECK_PING_URL` to a free
  [healthchecks.io](https://healthchecks.io) check. The worker pings it every 5 min; if pings
  stop (whole VM down), you get an email/SMS alert. See `docs/ENV_CHECKLIST.md`.

### 7.1 Deploy OOM / 502 on the ARM VM (ISSUE-2026-07-02-02)

A deploy can transiently return **502** if the `app` container is OOM-killed during rollover
(status `137` + `Temporary failure in name resolution` in the deploy log). The small ARM VM runs
low on RAM when the heavy import graph (langgraph + pandas/numpy) loads while the old and new app
containers briefly coexist. `restart: unless-stopped` + autoheal recover it, but the deploy job
still fails and the site can 502 for a minute.

- **Immediate recovery:** re-run the failed deploy — `gh run rerun <run-id> --failed` (lighter
  recreate, no second rollover). `/health` returns to ok.
- **Prevention (do once, on the VM):** add swap so the OOM has headroom —
  ```bash
  sudo fallocate -l 2G /swapfile && sudo chmod 600 /swapfile
  sudo mkswap /swapfile && sudo swapon /swapfile
  echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab   # persist across reboot
  free -h                                                       # confirm Swap: 2.0Gi
  ```
- **Longer-term:** slim what `migrations/env.py` imports so the migration process doesn't pull the
  full agent graph (ops backlog).

---

## 8. `VAULT_ENCRYPTION_KEY` rotation runbook

`crypto._fernet()` now uses **`MultiFernet`**, so rotation is zero-downtime: the FIRST key in
`VAULT_ENCRYPTION_KEYS` encrypts, and ANY listed key can decrypt. **Never drop the old key until
all ciphertext has been re-encrypted under the new one.**

1. **Back up the database first** (encrypted dump, off-host).
2. Generate a new key:
   `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
3. Set `VAULT_ENCRYPTION_KEYS="<new>,<old>"` (new first) — as a GitHub secret + `.env`. Redeploy.
   New writes now use `<new>`; existing ciphertext still decrypts under `<old>`. No downtime, no
   maintenance window. (Update the Bitwarden/paper sync map for `<new>` too.)
4. Re-encrypt existing rows under the new key: read each encrypted column and write it back
   (a plain `UPDATE ... SET col = col` through the ORM re-encrypts via the `Encrypted*`
   TypeDecorators, since MultiFernet always encrypts with the first key). A one-off
   `scripts/reencrypt_vault.py` should do this; add it before the first real rotation.
5. Verify with `python3 scripts/check_env.py --live` (Fernet round-trip) and read a known record.
6. Once every row is re-encrypted, drop `<old>` from `VAULT_ENCRYPTION_KEYS` (or move back to a
   single `VAULT_ENCRYPTION_KEY=<new>`), redeploy, then destroy the old key copies.

If you are still pre-data (no real records yet), rotation is trivial: set the new key and redeploy.
There is nothing to re-encrypt.

---

## 9. Troubleshooting

| Symptom | First check |
|---|---|
| Deploy fails in seconds at `validate-secrets` | A required Production secret is missing/malformed. The job log lists which. Cross-ref §2. |
| Deploy fails at the 90s health gate | `docker compose logs --tail 80 app` on the VM (the job also dumps these). Usually a bad `.env` value or DB not ready. |
| App returns 503 at `/health` | Postgres or Redis down: `docker compose ps`, `docker compose logs postgres redis`. |
| "invalid x-api-key" / auth errors | `python3 scripts/check_env.py --live` — pinpoints the failing credential without printing it. |
| Can't SSH from CI | `SSH_PRIVATE_KEY` secret lost its newlines on paste, or its public half isn't in the VM `authorized_keys`. Re-paste the full key file. |
| `could not create work tree dir: Permission denied` (step [1/6]) | `DEPLOY_PATH` isn't writable by the deploy user. The deploy script now auto-creates + `chown`s it (using `sudo` when the parent is root-owned), so this needs either passwordless sudo on the VM or a `DEPLOY_PATH` under the user's home (e.g. `/home/ubuntu/personal-cfo`). |
| Health gate: `exec: "curl": executable file not found` | The probes use python `urllib`, not curl (curl isn't in the `python:3.13-slim` image). If you reintroduce a curl-based check, install curl in the Dockerfile runtime stage. |
| Digest emails never arrive | `SMTP_*` not set (non-fatal — silently skipped). Add them in the Production env. |

For format vs. live validation: `check_env.py` (format) → `check_env.py --live` (does it
work?) → `audit_secrets.py` (full secret audit, supports `--ssh user@host` to audit the VM).
