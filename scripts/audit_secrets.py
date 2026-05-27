#!/usr/bin/env python3
"""
Audit all deployment secrets and environment variables.

Usage:
    # Local — reads .env automatically
    python scripts/audit_secrets.py

    # Local — explicit env file
    python scripts/audit_secrets.py --env-file /path/to/.env

    # Post results as a GitHub issue (needs GITHUB_TOKEN in env)
    python scripts/audit_secrets.py --post-issue

    # SSH to server and audit remotely (needs SSH key available)
    python scripts/audit_secrets.py --ssh user@host --remote-path /srv/cfo-agent

    # In GitHub Actions (posts issue, exits non-zero on failures)
    python scripts/audit_secrets.py --post-issue --env-file .env

Exit codes:
    0  All required secrets present and valid
    1  One or more required secrets missing or malformed
    2  Script error (bad args, network failure, etc.)
"""
import argparse
import base64
import json
import os
import subprocess
import sys
import urllib.request
import urllib.error
from dataclasses import dataclass, field
from pathlib import Path

# ── ANSI colours (disabled when not a TTY or when piped) ────────────────────
IS_TTY = sys.stdout.isatty()
GREEN  = "\033[32m" if IS_TTY else ""
RED    = "\033[31m" if IS_TTY else ""
YELLOW = "\033[33m" if IS_TTY else ""
DIM    = "\033[90m" if IS_TTY else ""
RESET  = "\033[0m"  if IS_TTY else ""

OK   = f"{GREEN}✓{RESET}"
FAIL = f"{RED}✗{RESET}"
WARN = f"{YELLOW}⚠{RESET}"
SKIP = f"{DIM}–{RESET}"


# ── Result tracking ──────────────────────────────────────────────────────────
@dataclass
class AuditResult:
    label: str
    status: str          # "ok" | "fail" | "warn" | "skip"
    message: str
    detail: str = ""

    def icon(self) -> str:
        return {
            "ok": OK, "fail": FAIL, "warn": WARN, "skip": SKIP,
        }[self.status]

    def plain(self) -> str:
        icon = {"ok": "✓", "fail": "✗", "warn": "⚠", "skip": "–"}[self.status]
        line = f"{icon}  {self.label:<30} {self.message}"
        if self.detail:
            line += f"\n      └─ {self.detail}"
        return line


results: list[AuditResult] = []


def _record(label: str, status: str, message: str, detail: str = "") -> AuditResult:
    r = AuditResult(label, status, message, detail)
    results.append(r)
    return r


# ── Check helpers ────────────────────────────────────────────────────────────

def check_required(label: str, val: str, min_len: int = 1, hint: str = "") -> AuditResult:
    length = len(val)
    if length == 0:
        return _record(label, "fail", "NOT SET",
                       hint or "See docs/ENV_CHECKLIST.md for acquisition instructions.")
    if length < min_len:
        return _record(label, "fail", f"SET but too short ({length} chars, need ≥{min_len})",
                       hint)
    return _record(label, "ok", f"{length} chars")


def check_prefix(label: str, val: str, expected: str, hint: str = "") -> AuditResult:
    length = len(val)
    if length == 0:
        return _record(label, "fail", "NOT SET",
                       hint or "See docs/ENV_CHECKLIST.md.")
    if val.startswith(expected):
        return _record(label, "ok", f"{length} chars  prefix={expected}✓")
    return _record(label, "warn",
                   f"{length} chars but unexpected prefix (expected '{expected}')",
                   hint)


def check_fernet(label: str, val: str) -> AuditResult:
    length = len(val)
    if length == 0:
        return _record(label, "fail", "NOT SET — encrypted vault data would be unreadable",
                       'Generate: python -c "from cryptography.fernet import Fernet; '
                       'print(Fernet.generate_key().decode())"')
    try:
        raw = base64.urlsafe_b64decode(val.encode())
        if len(raw) != 32:
            return _record(label, "warn",
                           f"SET ({length} chars) but decodes to {len(raw)} bytes (need 32)",
                           "Re-generate with the command in docs/ENV_CHECKLIST.md.")
        return _record(label, "ok", f"{length} chars  valid Fernet key ✓")
    except Exception:
        return _record(label, "fail",
                       f"SET ({length} chars) but not valid base64",
                       "Re-generate with the Fernet.generate_key() command.")


def check_optional(label: str, val: str, feature: str) -> AuditResult:
    if val:
        return _record(label, "ok", f"{len(val)} chars")
    return _record(label, "skip", f"not set  (disables: {feature})")


def check_ssh_key(label: str, val: str) -> AuditResult:
    length = len(val)
    if length == 0:
        return _record(label, "fail", "NOT SET")
    key_file = Path("/tmp/_cfo_audit_key")
    try:
        key_file.write_text(val)
        key_file.chmod(0o600)
        lines = len(val.splitlines())
        proc = subprocess.run(
            ["ssh-keygen", "-l", "-f", str(key_file)],
            capture_output=True, text=True,
        )
        key_file.unlink(missing_ok=True)
        if proc.returncode == 0:
            fp = proc.stdout.strip().split("\n")[0]
            if lines < 3:
                return _record(label, "warn",
                               f"{length} chars but only {lines} line(s) — newlines may have been stripped",
                               f"Fingerprint: {fp}")
            return _record(label, "ok", f"{length} chars  {lines} lines  {fp}")
        return _record(label, "warn",
                       f"{length} chars but ssh-keygen could not parse it",
                       "Re-paste the key with newlines intact.")
    except FileNotFoundError:
        key_file.unlink(missing_ok=True)
        return _record(label, "skip", f"{length} chars  (ssh-keygen not available for format check)")
    finally:
        key_file.unlink(missing_ok=True)


# ── Section printer ──────────────────────────────────────────────────────────

def section(title: str) -> None:
    print(f"\n{DIM}── {title} {('─' * (60 - len(title)))}{RESET}")


def flush_section(since: int) -> None:
    for r in results[since:]:
        print(f"  {r.icon()}  {r.label:<30} {r.message}")
        if r.detail:
            print(f"      {DIM}└─ {r.detail}{RESET}")


# ── Core audit ───────────────────────────────────────────────────────────────

def run_audit(env: dict[str, str]) -> bool:
    """Run all checks. Returns True if no failures."""
    g = env.get

    print(f"\n{'='*64}")
    print("  CFO-Agent  —  Environment & Secrets Audit")
    print(f"{'='*64}")

    # Tier 1
    section("Tier 1: Required — app won't start without these")
    s = len(results)
    check_prefix("ANTHROPIC_API_KEY", g("ANTHROPIC_API_KEY", ""), "sk-ant-",
                 hint="console.anthropic.com → API Keys")
    check_required("DATABASE_URL", g("DATABASE_URL", ""), 1)
    check_required("REDIS_URL", g("REDIS_URL", ""), 1)
    check_required("JWT_SECRET_KEY", g("JWT_SECRET_KEY", ""), 32,
                   hint="Generate: openssl rand -hex 32")
    check_fernet("VAULT_ENCRYPTION_KEY", g("VAULT_ENCRYPTION_KEY", ""))
    check_required("DIGEST_RECIPIENT", g("DIGEST_RECIPIENT", ""))
    flush_section(s)

    # Tier 2
    section("Tier 2: SMTP — required for digest emails")
    s = len(results)
    smtp_vars = ["SMTP_HOST", "SMTP_USER", "SMTP_PASSWORD", "SMTP_FROM"]
    any_smtp = any(g(v, "") for v in smtp_vars)
    if any_smtp:
        for v in smtp_vars:
            check_required(v, g(v, ""))
        check_optional("SMTP_PORT", g("SMTP_PORT", ""), "override default 587")
    else:
        _record("SMTP_*", "warn", "none set — digest emails will be silently skipped",
                "Set SMTP_HOST, SMTP_USER, SMTP_PASSWORD, SMTP_FROM together.")
    flush_section(s)

    # Tier 3
    section("Tier 3: Deployment")
    s = len(results)
    check_required("CLOUDFLARE_TUNNEL_TOKEN", g("CLOUDFLARE_TUNNEL_TOKEN", ""),
                   hint="Zero Trust → Networks → Tunnels → Docker install command")
    check_ssh_key("SSH_PRIVATE_KEY", g("SSH_PRIVATE_KEY", ""))
    check_required("DEPLOY_HOST", g("DEPLOY_HOST", ""))
    check_required("DEPLOY_USER", g("DEPLOY_USER", ""))
    check_required("DEPLOY_PATH", g("DEPLOY_PATH", ""))
    check_required("GH_PAT", g("GH_PAT", ""))
    check_optional("POSTGRES_USER", g("POSTGRES_USER", ""), "override default 'cfo'")
    check_optional("POSTGRES_PASSWORD", g("POSTGRES_PASSWORD", ""), "override default 'cfo'")
    check_optional("POSTGRES_DB", g("POSTGRES_DB", ""), "override default 'personal_cfo'")
    flush_section(s)

    # Tier 4
    section("Tier 4: Optional feature gates")
    s = len(results)
    check_optional("RENTCAST_API_KEY", g("RENTCAST_API_KEY", ""),
                   "POST /vault/real-estate/refresh-values")
    check_optional("ALPHA_VANTAGE_KEY", g("ALPHA_VANTAGE_KEY", ""),
                   "Alpha Vantage fallback for stock prices")
    check_optional("ALLOWED_ORIGINS", g("ALLOWED_ORIGINS", ""),
                   "CORS — set to production domain before going live")
    flush_section(s)

    # Tier 5
    section("Tier 5: Tuning (defaults are fine)")
    s = len(results)
    defaults = {
        "JWT_EXPIRY_MINUTES": "60",
        "LLM_TIMEOUT_SECONDS": "120",
        "ENV": "development",
        "LANGGRAPH_CHECKPOINT_BACKEND": "redis",
        "ALERT_DRIFT_PCT_THRESHOLD": "25",
        "ALERT_INCOME_DROP_PCT_THRESHOLD": "30",
    }
    for var, default in defaults.items():
        val = g(var, "")
        display = val if val else f"(default: {default})"
        _record(var, "ok", display)
    flush_section(s)

    # Tier 6
    section("Tier 6: Phase 2 / Plaid — deferred, do not wire yet")
    s = len(results)
    for v in ["PLAID_CLIENT_ID", "PLAID_SECRET", "PLAID_ENV"]:
        val = g(v, "")
        _record(v, "skip" if not val else "ok",
                "(not set — expected)" if not val else f"{len(val)} chars")
    flush_section(s)

    # Summary
    failures = [r for r in results if r.status == "fail"]
    warnings = [r for r in results if r.status == "warn"]
    print(f"\n{'='*64}")
    if failures:
        print(f"  {FAIL} {RED}{len(failures)} failure(s){RESET}  "
              f"{WARN} {len(warnings)} warning(s)")
        print()
        for r in failures:
            print(f"  {FAIL} {r.label}: {r.message}")
            if r.detail:
                print(f"      └─ {r.detail}")
        print()
        print("  See docs/ENV_CHECKLIST.md for acquisition instructions.")
    elif warnings:
        print(f"  {OK} Required secrets OK  |  {WARN} {len(warnings)} warning(s)")
        for r in warnings:
            print(f"  {WARN} {r.label}: {r.message}")
    else:
        print(f"  {OK} {GREEN}All checks passed.{RESET}")
    print(f"{'='*64}\n")

    return len(failures) == 0


# ── Remote SSH audit ─────────────────────────────────────────────────────────

def run_remote_audit(ssh_target: str, remote_path: str) -> int:
    """SSH to server, run this script there, stream output back."""
    script_path = Path(__file__).resolve()
    remote_script = f"{remote_path}/scripts/audit_secrets.py"

    print(f"  Uploading audit script to {ssh_target}:{remote_script}...")
    scp = subprocess.run(
        ["scp", "-o", "StrictHostKeyChecking=no",
         str(script_path), f"{ssh_target}:{remote_script}"],
        capture_output=True, text=True,
    )
    if scp.returncode != 0:
        print(f"  {FAIL} scp failed: {scp.stderr.strip()}")
        return 2

    print(f"  Running remote audit on {ssh_target}...")
    print()
    ssh = subprocess.run(
        ["ssh", "-o", "StrictHostKeyChecking=no", ssh_target,
         f"cd {remote_path} && python3 {remote_script} --env-file .env"],
    )
    return ssh.returncode


# ── GitHub issue poster ───────────────────────────────────────────────────────

def post_github_issue(token: str, repo: str, passed: bool) -> None:
    """Create or update a GitHub issue with the audit report."""
    status_icon = "✅" if passed else "❌"
    status_text = "PASSED" if passed else "FAILED"

    lines = [f"## {status_icon} Secret Audit — {status_text}\n"]
    lines.append("_Auto-generated by `scripts/audit_secrets.py`. "
                 "Run `python scripts/audit_secrets.py` locally to reproduce._\n")

    current_section = None
    for r in results:
        # Group by tier based on insertion order
        icon = {"ok": "✅", "fail": "❌", "warn": "⚠️", "skip": "➖"}[r.status]
        line = f"| {icon} | `{r.label}` | {r.message} |"
        if r.detail:
            line += f" {r.detail}"
        lines.append(line)

    lines.append("\n---")
    lines.append("| Status | Label | Detail |")
    lines.append("|---|---|---|")

    # Rebuild as a proper table
    body_lines = [
        f"## {status_icon} Secret Audit — {status_text}\n",
        "_Auto-generated by `scripts/audit_secrets.py`._\n",
        "| Status | Variable | Result |",
        "|--------|----------|--------|",
    ]
    for r in results:
        icon = {"ok": "✅", "fail": "❌", "warn": "⚠️", "skip": "➖"}[r.status]
        detail = f" `{r.detail}`" if r.detail else ""
        body_lines.append(f"| {icon} | `{r.label}` | {r.message}{detail} |")

    failures = [r for r in results if r.status == "fail"]
    if failures:
        body_lines.append("\n### ❌ Action required\n")
        for r in failures:
            body_lines.append(f"- **`{r.label}`**: {r.message}")
            if r.detail:
                body_lines.append(f"  - {r.detail}")

    body_lines.append("\n_See `docs/ENV_CHECKLIST.md` for acquisition instructions._")
    body = "\n".join(body_lines)

    api_base = "https://api.github.com"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
    }

    # Check for an existing open audit issue to update rather than spam new ones
    search_url = (f"{api_base}/repos/{repo}/issues"
                  f"?state=open&labels=secret-audit&per_page=1")
    try:
        req = urllib.request.Request(search_url, headers=headers)
        with urllib.request.urlopen(req) as resp:
            existing = json.loads(resp.read())
    except urllib.error.URLError as e:
        print(f"  {WARN} GitHub API error (search): {e}")
        existing = []

    payload = json.dumps({
        "title": f"Secret Audit — {status_text}",
        "body": body,
        "labels": ["secret-audit"],
    }).encode()

    if existing:
        issue_num = existing[0]["number"]
        issue_url = existing[0]["html_url"]
        url = f"{api_base}/repos/{repo}/issues/{issue_num}"
        req = urllib.request.Request(url, data=payload, headers=headers, method="PATCH")
        action = "Updated"
    else:
        url = f"{api_base}/repos/{repo}/issues"
        req = urllib.request.Request(url, data=payload, headers=headers, method="POST")
        action = "Created"

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read())
        issue_url = data["html_url"]
        print(f"  {OK} {action} GitHub issue: {issue_url}")
    except urllib.error.URLError as e:
        print(f"  {WARN} Could not post to GitHub: {e}")


# ── .env loader ───────────────────────────────────────────────────────────────

def load_env_file(path: Path) -> dict[str, str]:
    env: dict[str, str] = {}
    if not path.exists():
        return env
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            env[key] = value
    return env


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit CFO-Agent deployment secrets.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    parser.add_argument("--env-file", default=".env",
                        help="Path to .env file (default: .env)")
    parser.add_argument("--post-issue", action="store_true",
                        help="Post results as a GitHub issue "
                             "(needs GITHUB_TOKEN + GITHUB_REPOSITORY in env)")
    parser.add_argument("--ssh", metavar="USER@HOST",
                        help="SSH target: run the audit remotely on this host")
    parser.add_argument("--remote-path", default="/srv/cfo-agent",
                        help="Path to the app on the remote host (default: /srv/cfo-agent)")
    args = parser.parse_args()

    # Remote mode: upload and run there
    if args.ssh:
        return run_remote_audit(args.ssh, args.remote_path)

    # Build env: file values, then real env overrides (real env wins)
    env_file = Path(args.env_file)
    env = load_env_file(env_file)
    env.update({k: v for k, v in os.environ.items() if k not in env})

    if env_file.exists():
        print(f"  Loaded: {env_file.resolve()} ({len(env)} entries)")
    else:
        print(f"  {WARN} {env_file} not found — using only process environment")

    passed = run_audit(env)

    if args.post_issue:
        token = os.environ.get("GITHUB_TOKEN", "")
        repo = os.environ.get("GITHUB_REPOSITORY", "reese8272/CFO-Agent")
        if not token:
            print(f"  {WARN} --post-issue requires GITHUB_TOKEN in environment")
        else:
            print(f"  Posting results to GitHub ({repo})...")
            post_github_issue(token, repo, passed)

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
