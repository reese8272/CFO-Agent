#!/usr/bin/env python3
"""Pre-flight env check. Run before `docker compose up` or any deployment.

Usage:
    python scripts/check_env.py           # reads .env automatically
    python scripts/check_env.py --strict  # treat optional-but-recommended as failures
    python scripts/check_env.py --live    # also verify each credential actually works
    ENV_FILE=.env.staging python scripts/check_env.py
"""
import base64
import os
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Load .env into os.environ (without requiring the full app stack)
# ---------------------------------------------------------------------------
env_file = Path(os.environ.get("ENV_FILE", ".env"))
if env_file.exists():
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value

STRICT = "--strict" in sys.argv
LIVE = "--live" in sys.argv

# ---------------------------------------------------------------------------
# Check definitions
# ---------------------------------------------------------------------------
OK = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m~\033[0m"

failures: list[str] = []
warnings: list[str] = []


def require(var: str, hint: str = "", fmt_check=None) -> None:
    val = os.environ.get(var, "").strip()
    if not val:
        failures.append(f"  {FAIL}  {var} — not set. {hint}")
        return
    if fmt_check:
        err = fmt_check(val)
        if err:
            failures.append(f"  {FAIL}  {var} — set but {err}. {hint}")
            return
    print(f"  {OK}  {var}")


def recommend(var: str, feature: str, hint: str = "") -> None:
    val = os.environ.get(var, "").strip()
    if not val:
        msg = f"  {WARN}  {var} — not set (disables: {feature}). {hint}"
        if STRICT:
            failures.append(msg)
        else:
            warnings.append(msg)
    else:
        print(f"  {OK}  {var}")


def optional(var: str, default: str = "") -> None:
    val = os.environ.get(var, "").strip()
    display = val if val else f"(default: {default})"
    print(f"  {OK}  {var} = {display}")


# --- Format validators ---

def check_jwt_key(val: str):
    if len(val) < 32:
        return f"too short ({len(val)} chars, need ≥ 32)"
    return None


def check_fernet_key(val: str):
    try:
        raw = base64.urlsafe_b64decode(val.encode())
        if len(raw) != 32:
            return f"decoded to {len(raw)} bytes, expected 32"
    except Exception:
        return "not valid base64 — re-generate with: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
    return None


def check_db_url(val: str):
    if not val.startswith("postgresql+psycopg://"):
        return "must start with postgresql+psycopg://"
    return None


def check_redis_url(val: str):
    if not val.startswith("redis://"):
        return "must start with redis://"
    return None


def check_email(val: str):
    if "@" not in val or "." not in val.split("@")[-1]:
        return "does not look like a valid email address"
    return None


def check_anthropic_key(val: str):
    if not val.startswith("sk-ant-"):
        return "expected to start with sk-ant-"
    return None


# ---------------------------------------------------------------------------
# Run checks
# ---------------------------------------------------------------------------

print("\n── Tier 1: App won't start without these ──────────────────────────────")
require("ANTHROPIC_API_KEY", hint="console.anthropic.com → API Keys", fmt_check=check_anthropic_key)
require("DATABASE_URL", fmt_check=check_db_url)
require("REDIS_URL", fmt_check=check_redis_url)
require("JWT_SECRET_KEY", hint="generate: openssl rand -hex 32", fmt_check=check_jwt_key)
require("VAULT_ENCRYPTION_KEY",
        hint='generate: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"',
        fmt_check=check_fernet_key)
require("DIGEST_RECIPIENT", hint="email address for weekly digest", fmt_check=check_email)

print("\n── Tier 2: SMTP (digest emails) ────────────────────────────────────────")
smtp_vars = [os.environ.get(v, "").strip() for v in ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]]
smtp_configured = any(smtp_vars)
if smtp_configured:
    require("SMTP_HOST")
    optional("SMTP_PORT", default="587")
    require("SMTP_USER")
    require("SMTP_PASSWORD")
    require("SMTP_FROM", fmt_check=check_email)
else:
    msg = f"  {WARN}  SMTP_* — none set; digest emails will be silently skipped (see docs/ENV_CHECKLIST.md)"
    if STRICT:
        failures.append(msg)
    else:
        warnings.append(msg)

print("\n── Tier 3: Production deployment ───────────────────────────────────────")
recommend("CLOUDFLARE_TUNNEL_TOKEN",
          feature="Cloudflare Tunnel (required in production)",
          hint="Zero Trust → Networks → Tunnels → your tunnel → Docker install command")
optional("POSTGRES_USER", default="cfo")
optional("POSTGRES_PASSWORD", default="cfo")
optional("POSTGRES_DB", default="personal_cfo")

print("\n── Tier 4: Optional feature gates ──────────────────────────────────────")
recommend("RENTCAST_API_KEY",
          feature="POST /vault/real-estate/refresh-values",
          hint="app.rentcast.io/register (free, no credit card)")
recommend("ALPHA_VANTAGE_KEY",
          feature="Alpha Vantage fallback for stock prices",
          hint="alphavantage.co/support/#api-key (free)")
recommend("ALLOWED_ORIGINS",
          feature="CORS (set to your production domain before going live)",
          hint='e.g. ["https://cfo.yourdomain.com"]')

print("\n── Tier 5: Tuning (defaults are fine) ──────────────────────────────────")
optional("JWT_EXPIRY_MINUTES", default="60")
optional("LLM_TIMEOUT_SECONDS", default="120")
optional("ENV", default="development")
optional("LANGGRAPH_CHECKPOINT_BACKEND", default="redis")
optional("ALERT_DRIFT_PCT_THRESHOLD", default="25")
optional("ALERT_INCOME_DROP_PCT_THRESHOLD", default="30")

print("\n── Tier 6: Phase 2 / Plaid (deferred — do not wire yet) ────────────────")
for v in ["PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV"]:
    val = os.environ.get(v, "")
    status = OK if val else f"\033[90m-\033[0m"
    print(f"  {status}  {v} {'(set)' if val else '(not set — expected, phase 2)'}")

# ---------------------------------------------------------------------------
# Live connectivity (opt-in via --live): prove each credential actually works.
# Reports PASS/FAIL only — never echoes the secret. Run it where the app runs
# (inside the container or with host-resolvable DATABASE_URL / REDIS_URL).
# ---------------------------------------------------------------------------

def live(label: str, fn) -> None:
    try:
        detail = fn()
        print(f"  {OK}  {label}{(' — ' + detail) if detail else ''}")
    except Exception as exc:
        msg = f"{type(exc).__name__}: {exc}".replace("\n", " ").strip()[:140]
        failures.append(f"  {FAIL}  {label} — {msg}")


if LIVE:
    print("\n── Live connectivity (does each credential actually work?) ─────────────")

    def _live_fernet() -> str:
        from cryptography.fernet import Fernet
        f = Fernet(os.environ.get("VAULT_ENCRYPTION_KEY", "").encode())
        if f.decrypt(f.encrypt(b"ping")) != b"ping":
            raise ValueError("round-trip mismatch")
        return "encrypt/decrypt round-trip OK"
    live("VAULT_ENCRYPTION_KEY (Fernet)", _live_fernet)

    def _live_postgres() -> str:
        import psycopg
        url = os.environ.get("DATABASE_URL", "").replace("+psycopg", "")
        with psycopg.connect(url, connect_timeout=5) as conn:
            conn.execute("SELECT 1")
        return "connected; SELECT 1 OK"
    live("DATABASE_URL (Postgres)", _live_postgres)

    def _live_redis() -> str:
        import redis
        redis.from_url(os.environ.get("REDIS_URL", ""), socket_connect_timeout=5).ping()
        return "PING OK"
    live("REDIS_URL (Redis)", _live_redis)

    def _live_anthropic() -> str:
        import anthropic
        anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY", ""), timeout=10).models.list()
        return "authenticated"
    live("ANTHROPIC_API_KEY (Anthropic)", _live_anthropic)

    if os.environ.get("SMTP_HOST", "").strip():
        def _live_smtp() -> str:
            import smtplib
            port = int(os.environ.get("SMTP_PORT", "587") or "587")
            with smtplib.SMTP(os.environ["SMTP_HOST"].strip(), port, timeout=10) as s:
                s.starttls()
                s.login(os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASSWORD", ""))
            return "STARTTLS + login OK"
        live("SMTP (login)", _live_smtp)

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
print()
if warnings:
    print("Warnings (non-blocking):")
    for w in warnings:
        print(w)
    print()

if failures:
    print(f"\033[31mFAILED — {len(failures)} problem(s):\033[0m")
    for f in failures:
        print(f)
    print()
    print("See docs/ENV_CHECKLIST.md for acquisition instructions.")
    sys.exit(1)
else:
    print(f"\033[32mAll required vars present.\033[0m Run `docker compose up -d` when ready.")
    sys.exit(0)
