"""Scenario engine — deterministic forward-projection math.

Two scenario types:
  time_to_target: months until a growing balance hits a goal (compound interest)
  income_change:  impact of a monthly income change on annual totals and trajectory
"""
from __future__ import annotations
from decimal import Decimal, ROUND_HALF_UP

from scenarios.models import ScenarioInput, ScenarioOutput, ScenarioKind

_MAX_MONTHS = 600  # 50-year ceiling


def run_scenario(inp: ScenarioInput) -> ScenarioOutput:
    """Dispatch to the correct computation and wrap in ScenarioOutput."""
    if inp.kind == ScenarioKind.time_to_target:
        return _time_to_target(inp)
    return _income_change(inp)


# ── time_to_target ─────────────────────────────────────────────────────────────

def _time_to_target(inp: ScenarioInput) -> ScenarioOutput:
    current = inp.current_amount or Decimal("0")
    contribution = inp.monthly_contribution or Decimal("0")
    annual_pct = inp.annual_return_pct or Decimal("0")
    target = inp.target_amount

    if target is None or target <= 0:
        raise ValueError("target_amount is required and must be positive")
    if current >= target:
        months = 0
    else:
        months = time_to_target(current, contribution, annual_pct, target)

    r_monthly = annual_pct / 100 / 12
    requires_disclaimer = annual_pct > 0

    if months is None:
        result = {
            "months": None,
            "years": None,
            "not_reachable": True,
            "message": (
                f"At ${contribution:,.0f}/month and {annual_pct}% annual return, "
                f"${target:,.0f} is not reachable within {_MAX_MONTHS // 12} years."
            ),
        }
        reasoning = result["message"]
    elif months == 0:
        result = {"months": 0, "years": 0, "not_reachable": False, "message": "Already at or above target."}
        reasoning = result["message"]
    else:
        years = months / 12
        result = {
            "months": months,
            "years": round(years, 1),
            "not_reachable": False,
            "message": (
                f"Starting at ${current:,.0f}, adding ${contribution:,.0f}/month "
                f"at {annual_pct}% annual return: ${target:,.0f} reached in "
                f"{months} months ({years:.1f} years)."
            ),
        }
        reasoning = (
            f"Compounded monthly at r={float(r_monthly):.4f}/month. "
            f"Each month: balance = balance × (1 + r) + contribution. "
            f"Iterates until balance ≥ target or {_MAX_MONTHS} months elapsed."
        )

    return ScenarioOutput(
        kind=ScenarioKind.time_to_target,
        result=result,
        reasoning_trace=reasoning,
        assumed_constants={
            "annual_return_pct": str(annual_pct),
            "monthly_rate": f"{float(r_monthly):.6f}",
            "max_months_ceiling": _MAX_MONTHS,
        },
        requires_disclaimer=requires_disclaimer,
        disclaimer=(
            "Investment growth projections assume a constant annual return rate. "
            "Actual returns vary. This is not investment advice — consult a licensed advisor."
            if requires_disclaimer else None
        ),
    )


def time_to_target(
    current: Decimal,
    monthly_contribution: Decimal,
    annual_return_pct: Decimal,
    target: Decimal,
    max_months: int = _MAX_MONTHS,
) -> int | None:
    """Return months until balance ≥ target, or None if unreachable within max_months.

    Uses month-by-month compounding: balance = balance * (1 + r) + contribution.
    r = annual_return_pct / 100 / 12.
    """
    r = annual_return_pct / Decimal("100") / Decimal("12")
    balance = current
    for month in range(1, max_months + 1):
        balance = balance * (1 + r) + monthly_contribution
        if balance >= target:
            return month
    return None


# ── income_change ──────────────────────────────────────────────────────────────

def _income_change(inp: ScenarioInput) -> ScenarioOutput:
    current_monthly = inp.current_monthly_income or Decimal("0")
    delta = inp.delta_monthly or Decimal("0")

    result = income_change(current_monthly, delta)
    direction = "increase" if delta >= 0 else "reduction"
    abs_delta = abs(delta)

    reasoning = (
        f"Monthly income changes by ${delta:+,.0f} ({direction} of ${abs_delta:,.0f}/month). "
        f"Annualised: ${delta * 12:+,.0f}. "
        f"New monthly total: ${result['new_monthly']:,.0f}."
    )

    return ScenarioOutput(
        kind=ScenarioKind.income_change,
        result={k: str(v) if isinstance(v, Decimal) else v for k, v in result.items()},
        reasoning_trace=reasoning,
        assumed_constants={"projection_period_months": 12},
        requires_disclaimer=False,
        disclaimer=None,
    )


def income_change(
    current_monthly: Decimal,
    delta_monthly: Decimal,
) -> dict:
    """Return the impact of a monthly income change.

    Returns current_monthly, new_monthly, new_annual, annual_delta, change_pct.
    """
    new_monthly = current_monthly + delta_monthly
    annual_delta = delta_monthly * 12
    new_annual = new_monthly * 12
    change_pct = (
        (delta_monthly / current_monthly * Decimal("100")).quantize(Decimal("0.1"), rounding=ROUND_HALF_UP)
        if current_monthly != 0 else Decimal("0")
    )
    return {
        "current_monthly": current_monthly,
        "new_monthly": new_monthly,
        "new_annual": new_annual,
        "monthly_delta": delta_monthly,
        "annual_delta": annual_delta,
        "change_pct": change_pct,
    }
