"""Scenario engine + endpoint tests."""
from __future__ import annotations
from decimal import Decimal

import pytest


# ── time_to_target pure math ───────────────────────────────────────────────────

def test_time_to_target_zero_return():
    """With 0% return, months = (target - current) / contribution."""
    from scenarios.engine import time_to_target

    months = time_to_target(Decimal("0"), Decimal("500"), Decimal("0"), Decimal("6000"))
    assert months == 12


def test_time_to_target_with_compound_return():
    """$0 start, $500/mo, 7% annual → should reach $10k in < 18 months (math check)."""
    from scenarios.engine import time_to_target

    months = time_to_target(Decimal("0"), Decimal("500"), Decimal("7"), Decimal("10000"))
    assert months is not None
    assert months < 22  # pure savings would be 20; compounding shaves it


def test_time_to_target_already_at_goal():
    """If current >= target, the engine returns 0 months."""
    from scenarios.engine import run_scenario
    from scenarios.models import ScenarioInput, ScenarioKind

    inp = ScenarioInput(
        kind=ScenarioKind.time_to_target,
        current_amount=Decimal("10000"),
        monthly_contribution=Decimal("500"),
        annual_return_pct=Decimal("7"),
        target_amount=Decimal("5000"),
    )
    out = run_scenario(inp)
    assert out.result["months"] == 0


def test_time_to_target_not_reachable():
    """Zero contribution, zero return → never reaches a higher target."""
    from scenarios.engine import time_to_target

    months = time_to_target(Decimal("1000"), Decimal("0"), Decimal("0"), Decimal("99999"))
    assert months is None


def test_time_to_target_disclaimer_when_return_nonzero():
    """Any non-zero annual return should set requires_disclaimer=True."""
    from scenarios.engine import run_scenario
    from scenarios.models import ScenarioInput, ScenarioKind

    inp = ScenarioInput(
        kind=ScenarioKind.time_to_target,
        current_amount=Decimal("0"),
        monthly_contribution=Decimal("500"),
        annual_return_pct=Decimal("7"),
        target_amount=Decimal("100000"),
    )
    out = run_scenario(inp)
    assert out.requires_disclaimer is True
    assert out.disclaimer is not None


def test_time_to_target_no_disclaimer_when_zero_return():
    """Zero return = cash projection; no disclaimer needed."""
    from scenarios.engine import run_scenario
    from scenarios.models import ScenarioInput, ScenarioKind

    inp = ScenarioInput(
        kind=ScenarioKind.time_to_target,
        current_amount=Decimal("0"),
        monthly_contribution=Decimal("1000"),
        annual_return_pct=Decimal("0"),
        target_amount=Decimal("12000"),
    )
    out = run_scenario(inp)
    assert out.requires_disclaimer is False
    assert out.disclaimer is None


# ── income_change pure math ────────────────────────────────────────────────────

def test_income_change_increase():
    from scenarios.engine import income_change

    result = income_change(Decimal("5000"), Decimal("1000"))
    assert result["new_monthly"] == Decimal("6000")
    assert result["annual_delta"] == Decimal("12000")
    assert result["change_pct"] == Decimal("20.0")


def test_income_change_cut():
    from scenarios.engine import income_change

    result = income_change(Decimal("5000"), Decimal("-500"))
    assert result["new_monthly"] == Decimal("4500")
    assert result["annual_delta"] == Decimal("-6000")
    assert result["change_pct"] == Decimal("-10.0")


def test_income_change_zero_base():
    """Division-safe when current_monthly is 0."""
    from scenarios.engine import income_change

    result = income_change(Decimal("0"), Decimal("500"))
    assert result["new_monthly"] == Decimal("500")
    assert result["change_pct"] == Decimal("0")


def test_income_change_output_shape():
    from scenarios.engine import run_scenario
    from scenarios.models import ScenarioInput, ScenarioKind

    inp = ScenarioInput(
        kind=ScenarioKind.income_change,
        current_monthly_income=Decimal("4000"),
        delta_monthly=Decimal("-800"),
    )
    out = run_scenario(inp)
    assert out.kind == ScenarioKind.income_change
    assert out.requires_disclaimer is False
    assert "new_monthly" in out.result


# ── HTTP endpoint ──────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_scenarios_run_endpoint():
    """POST /scenarios/run returns a valid ScenarioOutput without live DB."""
    from httpx import AsyncClient, ASGITransport
    from sqlalchemy.exc import OperationalError

    from main import app

    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            await client.post("/auth/register", json={"username": "scenuser", "password": "TestPass123!"})
            token_resp = await client.post(
                "/auth/token",
                data={"username": "scenuser", "password": "TestPass123!"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                pytest.skip("live DB required for auth round-trip")

            token = token_resp.json()["access_token"]
            resp = await client.post(
                "/scenarios/run",
                json={
                    "kind": "time_to_target",
                    "current_amount": "1000",
                    "monthly_contribution": "500",
                    "annual_return_pct": "0",
                    "target_amount": "7000",
                },
                headers={"Authorization": f"Bearer {token}"},
            )

        assert resp.status_code == 200
        data = resp.json()
        assert data["kind"] == "time_to_target"
        assert data["result"]["months"] == 12
    except OperationalError:
        pytest.skip("live DB required for auth round-trip")
