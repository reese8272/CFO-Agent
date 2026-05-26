"""Tracker node — computes net-worth pace vs goals and writes trajectory_note + net_worth_pace."""
from __future__ import annotations
import logging
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.state import AgentState
from db import get_sessionmaker

logger = logging.getLogger(__name__)


async def tracker_node(state: AgentState) -> dict:
    snapshot = state.get("vault_snapshot", {})
    wealth_pos = state.get("wealth_position", {})
    income_pos = state.get("income_position", {})

    current_nw = Decimal(str(snapshot.get("net_worth", "0")))
    total_monthly_income = Decimal(str(snapshot.get("total_monthly_income", "0")))

    async with get_sessionmaker()() as session:
        net_worth_pace = await _compute_pace(session, current_nw)

    trajectory_note = _build_note(wealth_pos, income_pos, net_worth_pace, total_monthly_income)
    result: dict = {"trajectory_note": trajectory_note}
    if net_worth_pace:
        result["net_worth_pace"] = net_worth_pace
    return result


async def _compute_pace(session: AsyncSession, current_nw: Decimal) -> dict:
    """Return net_worth_pace dict or empty dict if insufficient data."""
    from vault.models import NetWorthSnapshot, Goal

    snap_result = await session.execute(
        select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_at.asc()).limit(12)
    )
    snaps = list(snap_result.scalars().all())

    goal_result = await session.execute(
        select(Goal)
        .where(Goal.kind == "net_worth", Goal.status == "active")
        .order_by(Goal.priority.asc().nullslast())
        .limit(1)
    )
    goal = goal_result.scalar_one_or_none()

    today = date.today()

    if goal and goal.target_amount and goal.deadline:
        first_nw = Decimal(str(snaps[0].net_worth or 0)) if snaps else Decimal("0")
        return _pace_from_goal(current_nw, first_nw, goal, today)

    if len(snaps) >= 2:
        first_nw = Decimal(str(snaps[0].net_worth or 0))
        first_ts = snaps[0].snapshot_at
        first_date = first_ts.date() if hasattr(first_ts, "date") else first_ts
        return _pace_from_snapshots(current_nw, first_nw, first_date, today)

    return {}


def _pace_from_goal(
    current_nw: Decimal, first_nw: Decimal, goal: object, today: date
) -> dict:
    """Compute pace vs a user-defined net-worth goal using linear interpolation."""
    start_date: date = getattr(goal, "created_at", None)
    if start_date is None:
        start_date = today
    elif hasattr(start_date, "date"):
        start_date = start_date.date()

    target = Decimal(str(goal.target_amount))  # type: ignore[union-attr]
    deadline: date = goal.deadline  # type: ignore[union-attr]

    total_days = max((deadline - start_date).days, 1)
    elapsed_days = max((today - start_date).days, 0)
    fraction = Decimal(str(elapsed_days)) / Decimal(str(total_days))

    target_at_now = first_nw + (target - first_nw) * fraction
    delta = current_nw - target_at_now
    return {
        "current": str(round(current_nw, 0)),
        "target_at_now": str(round(target_at_now, 0)),
        "delta": str(round(delta, 0)),
        "on_pace": bool(delta >= 0),
    }


def _pace_from_snapshots(
    current_nw: Decimal, first_nw: Decimal, first_date: date, today: date
) -> dict:
    """Estimate pace from first snapshot to now; on_pace if net worth is growing."""
    span_days = max((today - first_date).days, 1)
    monthly_rate = (current_nw - first_nw) / Decimal(str(span_days)) * Decimal("30")
    projected_12mo = current_nw + monthly_rate * 12
    return {
        "current": str(round(current_nw, 0)),
        "target_at_now": str(round(projected_12mo, 0)),
        "delta": str(round(monthly_rate, 0)),
        "on_pace": bool(monthly_rate > 0),
    }


def _build_note(
    wealth_pos: dict,
    income_pos: dict,
    pace: dict,
    monthly_income: Decimal,
) -> str:
    w_step = wealth_pos.get("step", 0)
    i_step = income_pos.get("step", 0)
    w_name = wealth_pos.get("step_name", f"Step {w_step}")
    i_name = income_pos.get("step_name", f"Step {i_step}")

    parts = [
        f"Allocation track: Step {w_step}/6 ({w_name}).",
        f"Income track: Step {i_step}/5 ({i_name}).",
    ]
    if monthly_income > 0:
        parts.append(f"Monthly income: ~${monthly_income:,.0f}.")
    if pace:
        delta = pace.get("delta", "0")
        if pace.get("on_pace", True):
            parts.append(f"Net-worth trajectory: on pace (monthly delta: ${delta}).")
        else:
            parts.append(f"Net-worth trajectory: behind pace (monthly delta: ${delta}).")
    return " ".join(parts)
