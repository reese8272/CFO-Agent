"""Retrieval node context builder.

Pulls vault aggregates + positions + active decisions + recent patterns,
assembles a deterministic 'User Profile' block for the Anthropic prompt cache.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_CEILING

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

import logging

from vault.wealth_position import WealthLadder as VaultWealthPosition
from vault.income_position import IncomeLadder as VaultIncomePosition
from memory.models import Decision, Pattern
from vault.income_position import compute_income_position
from vault.wealth_position import compute_wealth_position
from vault.models import FinancialSnapshot

logger = logging.getLogger(__name__)

_EMPTY_WEALTH: dict = {
    "open_gaps": [], "allocation_ladder": [],
    "net_worth": Decimal("0"), "total_assets": Decimal("0"), "total_liabilities": Decimal("0"),
}
_EMPTY_INCOME: dict = {
    "open_gaps": [], "income_ladder": [], "total_monthly_income": Decimal("0"),
}


# These TypedDicts match CONTRACTS.md §1 — different from the vault-layer TypedDicts.
# We bridge from vault shapes to these contract shapes below.
class _WealthPositionContract:
    """Structural type for the CONTRACTS.md WealthPosition (step, step_name, rationale, next_move)."""


class _IncomePositionContract:
    """Structural type for the CONTRACTS.md IncomePosition (step, step_name, rationale, next_move)."""


async def build_retrieval_context(session: AsyncSession, user_id: str) -> dict:
    """Return the full retrieval payload for AgentState.

    All dollar values are rounded to the nearest $100 to limit precision exposure
    in the LLM prompt (see THREAT_MODEL §4).
    """
    # --- wealth + income positions (safe: sparse vault after first intake must not crash chat) ---
    try:
        full_wealth: VaultWealthPosition = await compute_wealth_position(session, user_id)
    except Exception as exc:
        logger.warning("compute_wealth_position failed, using empty defaults: %s", exc)
        full_wealth = _EMPTY_WEALTH

    try:
        full_income: VaultIncomePosition = await compute_income_position(session, user_id)
    except Exception as exc:
        logger.warning("compute_income_position failed, using empty defaults: %s", exc)
        full_income = _EMPTY_INCOME

    wealth_pos = _bridge_wealth(full_wealth)
    income_pos = _bridge_income(full_income)

    # --- vault snapshot (redacted aggregates) ---
    vault_snapshot = _build_vault_snapshot(full_wealth, full_income)

    # --- active decisions ---
    result = await session.execute(
        select(Decision)
        .where(Decision.status == "active")
        .order_by(Decision.decided_at.desc())
        .limit(10)
    )
    decisions = result.scalars().all()
    active_decisions = [
        {
            "id": d.id,
            "summary": d.summary,
            "principle": d.principle,
            "status": d.status,
            "expires_at": d.expires_at.isoformat() if d.expires_at else None,
        }
        for d in decisions
    ]

    # --- recent patterns (last 30 days) ---
    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    result = await session.execute(
        select(Pattern)
        .where(Pattern.detected_at >= cutoff)
        .order_by(Pattern.detected_at.desc())
        .limit(5)
    )
    patterns = result.scalars().all()
    recent_patterns = [
        {
            "kind": p.kind,
            "severity": p.severity,
            "summary": p.summary,
            "detected_at": p.detected_at.isoformat(),
        }
        for p in patterns
    ]

    # --- financial snapshot (pre-computed analytical SOT) ---
    snap_result = await session.execute(
        select(FinancialSnapshot).order_by(FinancialSnapshot.computed_at.desc()).limit(1)
    )
    latest_snap = snap_result.scalar_one_or_none()
    financial_snapshot: dict | None = None
    if latest_snap and latest_snap.analysis_jsonb:
        analysis = latest_snap.analysis_jsonb
        financial_snapshot = {
            "computed_at": latest_snap.computed_at.isoformat(),
            "net_worth": str(latest_snap.net_worth) if latest_snap.net_worth else None,
            "allocation_step": latest_snap.allocation_step,
            "income_step": latest_snap.income_step,
            "savings_rate_pct": str(latest_snap.savings_rate_pct) if latest_snap.savings_rate_pct else None,
            "debt_to_income_ratio": str(latest_snap.debt_to_income_ratio) if latest_snap.debt_to_income_ratio else None,
            "emergency_months_covered": str(latest_snap.emergency_months_covered) if latest_snap.emergency_months_covered else None,
            "roth_utilization_pct": str(latest_snap.roth_utilization_pct) if latest_snap.roth_utilization_pct else None,
            "risk_flags": analysis.get("risk_flags", []),
            "opportunity_flags": analysis.get("opportunity_flags", []),
            "goals_progress": analysis.get("goals_progress", []),
            "life_context": analysis.get("life_context", {}),
        }

    return {
        "vault_snapshot": vault_snapshot,
        "wealth_position": wealth_pos,
        "income_position": income_pos,
        "active_decisions": active_decisions,
        "recent_patterns": recent_patterns,
        "memory_summary": None,  # populated by Issue 9 memory compaction
        "financial_snapshot": financial_snapshot,
    }


def build_profile_block(ctx: dict) -> str:
    """Build the deterministic text block that goes into the Anthropic prompt cache.

    Sorted keys + compact JSON → same input always produces the same string,
    which is required for the cache to hit.
    """
    def _default(obj: object) -> str:
        if isinstance(obj, Decimal):
            return str(obj)
        raise TypeError(f"not serializable: {type(obj)}")

    lines = [
        "## User Financial Profile (redacted aggregates)",
        "",
        "### Wealth Position",
        f"Step {ctx['wealth_position']['step']} — {ctx['wealth_position']['step_name']}",
        f"Rationale: {ctx['wealth_position']['rationale']}",
        f"Next move: {ctx['wealth_position']['next_move']}",
        "",
        "### Income Position",
        f"Step {ctx['income_position']['step']} — {ctx['income_position']['step_name']}",
        f"Rationale: {ctx['income_position']['rationale']}",
        f"Next move: {ctx['income_position']['next_move']}",
        "",
        "### Vault Summary (rounded to nearest $100)",
        json.dumps(ctx["vault_snapshot"], default=_default, sort_keys=True, indent=2),
        "",
        "### Active Decisions",
        json.dumps(ctx["active_decisions"], default=_default, sort_keys=True, indent=2),
        "",
        "### Recent Alerts / Patterns",
        json.dumps(ctx["recent_patterns"], default=_default, sort_keys=True, indent=2),
        "",
        "### Financial Snapshot (Pre-computed Analytical SOT)",
        json.dumps(ctx.get("financial_snapshot"), default=_default, sort_keys=True, indent=2),
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _bridge_wealth(full: VaultWealthPosition) -> dict:
    """Bridge the vault WealthPosition to the CONTRACTS.md shape.

    Extracts the lowest unfunded AllocationGap as the current position.
    Keys returned: step, step_name, rationale, next_move.
    """
    open_gaps = full.get("open_gaps", [])
    if open_gaps:
        first = open_gaps[0]
        step: int = first["step"]
        step_name: str = first["label"]
        gap_amt: Decimal = first.get("gap", Decimal("0"))
        current: Decimal = first.get("current", Decimal("0"))
        rationale = (
            f"{step_name} is underfunded by ~${_round100(gap_amt):,.0f} "
            f"(current: ${_round100(current):,.0f})."
        )
        next_move: str = first.get("target", f"Fund {step_name}")
    else:
        step = 6
        step_name = "All steps funded"
        rationale = "All allocation gates are met."
        next_move = "Continue investing in taxable brokerage."
    return {"step": step, "step_name": step_name, "rationale": rationale, "next_move": next_move}


def _bridge_income(full: VaultIncomePosition) -> dict:
    """Bridge the vault IncomePosition to the CONTRACTS.md shape.

    Extracts the lowest unfunded IncomeStep as the current position.
    Keys returned: step, step_name, rationale, next_move.
    """
    open_gaps = full.get("open_gaps", [])
    if open_gaps:
        first = open_gaps[0]
        step: int = first["step"]
        step_name: str = first["label"]
        actual: Decimal = first.get("monthly_actual", Decimal("0"))
        target: Decimal | None = first.get("monthly_target", None)
        if target is not None:
            rationale = (
                f"{step_name}: earning ${_round100(actual):,.0f}/mo "
                f"vs ${_round100(target):,.0f}/mo target."
            )
        else:
            rationale = f"{step_name}: not yet started."
        next_move = f"Address: {step_name}"
    else:
        step = 5
        step_name = "All income steps funded"
        rationale = "Passive income covers expenses."
        next_move = "Scale passive income sources."
    return {"step": step, "step_name": step_name, "rationale": rationale, "next_move": next_move}


def _build_vault_snapshot(full_wealth: VaultWealthPosition, full_income: VaultIncomePosition) -> dict:
    """Build a redacted aggregate snapshot from the position objects."""
    wealth_open = full_wealth.get("open_gaps", [])
    income_open = full_income.get("open_gaps", [])
    wealth_ladder = full_wealth.get("allocation_ladder", [])
    income_ladder = full_income.get("income_ladder", [])

    allocation_step: int
    if wealth_open:
        allocation_step = wealth_open[0].get("step", 0)
    elif wealth_ladder:
        allocation_step = 6  # all funded
    else:
        allocation_step = 0

    income_step: int
    if income_open:
        income_step = income_open[0].get("step", 0)
    elif income_ladder:
        income_step = 5  # all funded
    else:
        income_step = 0

    return {
        "net_worth": str(_round100(full_wealth.get("net_worth", Decimal("0")))),
        "total_assets": str(_round100(full_wealth.get("total_assets", Decimal("0")))),
        "total_liabilities": str(_round100(full_wealth.get("total_liabilities", Decimal("0")))),
        "total_monthly_income": str(_round100(full_income.get("total_monthly_income", Decimal("0")))),
        "allocation_step": allocation_step,
        "income_step": income_step,
    }


def _round100(val: object) -> Decimal:
    """Round up to the next 100 for prompt safety (never understate a figure)."""
    d = Decimal(str(val))
    return (d / Decimal("100")).quantize(Decimal("1"), rounding=ROUND_CEILING) * Decimal("100")
