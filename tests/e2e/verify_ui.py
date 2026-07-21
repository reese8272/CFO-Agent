"""Browser-level Gate 2 verification — drives real Chromium via Playwright.

Covers what TestClient structurally cannot (see ISSUE-2026-07-09-01): the actual
browser encoding path — login/register redirects, stale-token handling, HTMX
json-enc form submits, the intake CFO drawer, and a full chat round-trip.

Run via tests/e2e/run_e2e.sh (stands up a throwaway Postgres/Redis/uvicorn stack).
Not collected by pytest — this needs a live server and, for the chat step, a real
ANTHROPIC_API_KEY. Set CFO_E2E_SKIP_CHAT=1 to skip the (token-spending) chat step.
"""
import json
import os
import sys
import urllib.error
import urllib.request

from playwright.sync_api import sync_playwright

BASE = os.environ.get("CFO_E2E_BASE", "http://localhost:8100")
SKIP_CHAT = os.environ.get("CFO_E2E_SKIP_CHAT") == "1"
USER, PW = "uitest", "TestPass123!"

results: list[tuple[str, bool, str]] = []
js_errors: list[str] = []
console_errors: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    results.append((name, bool(cond), detail))
    print(("PASS  " if cond else "FAIL  ") + name + (f"  [{detail}]" if detail else ""))


def api(path: str, token: str, payload: dict | None = None, method: str = "GET"):
    req = urllib.request.Request(
        BASE + path,
        data=json.dumps(payload).encode() if payload is not None else None,
        headers={"Authorization": "Bearer " + token, "Content-Type": "application/json"},
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


with sync_playwright() as p:
    browser = p.chromium.launch()
    ctx = browser.new_context()
    page = ctx.new_page()
    page.on("pageerror", lambda e: js_errors.append(f"{page.url}: {e}"))
    page.on(
        "console",
        lambda m: console_errors.append(f"{page.url}: {m.text}") if m.type == "error" else None,
    )

    # --- 1. Login page loads with form + disclaimer ---
    page.goto(f"{BASE}/static/login.html")
    check("login: form visible", page.locator("#username").is_visible())
    check(
        "login: disclaimer visible",
        "Not licensed financial advice" in page.locator(".disclaimer").inner_text(),
    )

    # --- 2. PR #48: stale token stays on form and is cleared ---
    page.evaluate("localStorage.setItem('cfo_token', 'stale.dead.token')")
    page.goto(f"{BASE}/static/login.html")
    page.wait_for_timeout(1500)  # let the auto-check round-trip
    check("stale token: stays on login page", "login.html" in page.url)
    check(
        "stale token: token cleared",
        page.evaluate("localStorage.getItem('cfo_token')") is None,
    )
    check("stale token: form still usable", page.locator("#username").is_visible())

    # --- 2b. Stale token on vault: 401 signs out to login, no orphaned banners ---
    page.evaluate("localStorage.setItem('cfo_token', 'stale.dead.token')")
    page.goto(f"{BASE}/static/vault.html")
    page.wait_for_url("**/login.html", timeout=10000)
    check("stale token on vault: redirected to sign-in", True)
    check(
        "stale token on vault: token cleared",
        page.evaluate("localStorage.getItem('cfo_token')") is None,
    )

    # --- 3. Register a new user -> lands on intake (not chat) ---
    page.fill("#username", USER)
    page.fill("#password", PW)
    page.click("#submit-btn")
    page.wait_for_url("**/intake.html", timeout=15000)
    check("register: new user redirected to intake", True)
    token = page.evaluate("localStorage.getItem('cfo_token')")
    check("register: token stored", bool(token))

    # --- 4. Wrong password shows the real error, button recovers ---
    page.evaluate("localStorage.removeItem('cfo_token')")
    page.goto(f"{BASE}/static/login.html")
    page.fill("#username", USER)
    page.fill("#password", "WrongPass999!")
    page.click("#submit-btn")
    page.wait_for_selector("#error-msg", state="visible", timeout=10000)
    err_text = page.locator("#error-msg").inner_text()
    check(
        "wrong password: 'Incorrect username or password' shown",
        "Incorrect username or password" in err_text,
        err_text,
    )
    check("wrong password: button re-enabled", page.locator("#submit-btn").is_enabled())

    # --- 5. Correct login works ---
    page.fill("#password", PW)
    page.click("#submit-btn")
    page.wait_for_url("**/intake.html", timeout=15000)
    token = page.evaluate("localStorage.getItem('cfo_token')")
    check("login: correct password lands on intake with fresh token", bool(token))

    # --- 5b. Intake page: CFO drawer opens, no load-time JS errors ---
    page.click("button.cfo-fab")
    check("intake: CFO drawer opens", page.locator("#cfo-drawer").is_visible())
    page.click("button.cfo-drawer-close")

    # --- 6. Complete intake via API (wizard UI is out of scope here) ---
    status, body = api("/intake/submit", token, method="POST", payload={
        "life_context": {
            "age": 30, "household_size": 1, "dependents": 0, "tax_filing_status": "single",
        },
        "primary_income": {
            "source": "Acme Corp", "source_type": "w2",
            "cadence": "biweekly", "typical_gross_amount": 3200,
        },
        "accounts": [{
            "nickname": "Main checking", "institution": "Test Bank", "type": "checking",
            "current_balance": 12000, "is_emergency_fund": True,
        }],
        "monthly_spend": 2500,
        "goals": [{"title": "Hit $1M", "kind": "net_worth", "target_amount": 1000000}],
    })
    check("intake: submit returns 201", status == 201, f"status={status} body={str(body)[:200]}")
    status, body = api("/intake/status", token)
    check(
        "intake: status now completed",
        status == 200 and body.get("intake_completed") is True,
        str(body)[:200],
    )

    # --- 7. Vault: HTMX list load + add rows through the real forms ---
    page.goto(f"{BASE}/static/vault.html")
    page.wait_for_selector("#list-accounts tbody tr", timeout=10000)
    check(
        "vault: intake-created account listed",
        "Test Bank" in page.locator("#list-accounts").inner_text(),
    )
    check(
        "vault: disclaimer visible",
        "Not licensed financial advice" in page.locator(".disclaimer").inner_text(),
    )

    form = page.locator("#form-accounts")
    form.locator("[name=institution]").fill("E2E Credit Union")
    form.locator("[name=nickname]").fill("Rainy day savings")
    form.locator("[name=type]").select_option("savings")
    form.locator("[name=current_balance]").fill("800.50")
    form.locator("button[type=submit]").click()
    page.wait_for_selector("#list-accounts tbody tr:has-text('E2E Credit Union')", timeout=10000)
    check("vault: account added via HTMX form", True)
    check(
        "vault: form reset after successful add",
        page.locator("#form-accounts [name=institution]").input_value() == "",
    )

    page.click("button.nav-item:has-text('Expenses')")
    exp = page.locator("#form-expenses")
    exp.locator("[name=name]").fill("Rent")
    exp.locator("[name=category]").fill("Housing")
    exp.locator("[name=typical_amount]").fill("1500")
    exp.locator("button[type=submit]").click()
    page.wait_for_selector("#list-expenses tbody tr:has-text('Rent')", timeout=10000)
    check("vault: expense added via HTMX form", True)

    # --- 8. Snapshot refresh picks up the new vault data ---
    status, body = api("/intake/snapshot/refresh", token, method="POST", payload={})
    check("snapshot: refresh returns 201", status == 201, f"status={status}")
    nw = body.get("net_worth")
    check(
        "snapshot: net worth includes new account (>12000)",
        nw is not None and float(nw) > 12000,
        f"net_worth={nw}",
    )

    # --- 9. Chat: full agent round-trip (real Anthropic calls) ---
    page.goto(f"{BASE}/static/chat.html")
    page.wait_for_timeout(1500)
    check("chat: intake-complete user not bounced", "chat.html" in page.url)
    check("chat: starters visible", page.locator("button.starter").count() >= 4)
    if SKIP_CHAT:
        print("SKIP  chat round-trip (CFO_E2E_SKIP_CHAT=1)")
    else:
        page.click("button.starter:has-text('Where do I stand financially')")  # auto-sends
        page.wait_for_selector(".msg-row.user", timeout=10000)
        check("chat: user message rendered", True)
        page.wait_for_selector(".msg-row.agent .agent-recommendation", timeout=240000)
        agent_text = page.locator(".msg-row.agent .agent-recommendation").last.inner_text()
        check("chat: agent replied with substance", len(agent_text) > 100, f"len={len(agent_text)}")
        check(
            "chat: reply is not an error bubble",
            "Something went wrong" not in agent_text
            and "error" not in agent_text[:40].lower(),
            agent_text[:120],
        )

    # --- 10. Sign out returns to login and clears token ---
    page.click("button.btn-signout")
    page.wait_for_url("**/login.html", timeout=10000)
    check("sign out: back at login", True)
    check(
        "sign out: token cleared",
        page.evaluate("localStorage.getItem('cfo_token')") is None,
    )

    browser.close()

# --- JS/console health ---
check("no uncaught JS errors anywhere", not js_errors, "; ".join(js_errors[:5]))
expected_noise = ("401", "409", "Failed to load resource")
unexpected = [e for e in console_errors if not any(n in e for n in expected_noise)]
check("no unexpected console errors", not unexpected, "; ".join(unexpected[:5]))
if console_errors:
    print(f"\n(console noise, expected from negative tests: {len(console_errors)} lines)")

failed = [r for r in results if not r[1]]
print(f"\n{'=' * 60}\n{len(results) - len(failed)}/{len(results)} checks passed")
sys.exit(1 if failed else 0)
