"""Alert node — fires proactive NodeProposals on 7 deterministic threshold types."""
from __future__ import annotations
import logging
from datetime import date, timedelta
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.state import AgentState, NodeProposal
from agent.principles import TAX_YEAR
from db import get_sessionmaker

logger = logging.getLogger(__name__)

_SURPLUS_MONTHS_IDLE = 3       # alert when idle cash > N × monthly income
_ROTH_WINDOW_DAYS = 90         # alert within N days of Dec 31 if Roth room remains
_DEDUCTION_WINDOW_DAYS = 60    # alert within N days of Dec 31 if categories missing
_MILESTONE_WINDOW_DAYS = 30    # alert when milestone trigger_date within N days
_NW_PACE_ALERT_THRESHOLD = Decimal("-500")  # fire when monthly pace delta < this

_EXPECTED_DEDUCTION_CATEGORIES: frozenset[str] = frozenset({"mileage", "home_office", "equipment"})


async def alert_node(state: AgentState) -> dict:
    snapshot = state.get("vault_snapshot", {})
    net_worth_pace = state.get("net_worth_pace", {})
    today = date.today()
    proposals: list[NodeProposal] = []

    p = _surplus_alert(snapshot)
    if p:
        proposals.append(p)

    p = _net_worth_pace_alert(net_worth_pace)
    if p:
        proposals.append(p)

    async with get_sessionmaker()() as session:
        proposals.extend(await _roth_room_alert(session, today))
        proposals.extend(await _deduction_gap_alert(session, today))
        proposals.extend(await _negotiation_milestone_alert(session, today))
        proposals.extend(await _career_offpace_alert(session, today))

    if proposals:
        logger.info("alert: fired %d proactive alert(s)", len(proposals))
    return {"proposals": proposals}


# ── Pure-state alerts ─────────────────────────────────────────────────────────

def _surplus_alert(snapshot: dict) -> NodeProposal | None:
    """Fire when idle cash exceeds 3× monthly income and there's an unfunded step."""
    monthly_income = Decimal(str(snapshot.get("total_monthly_income", "0")))
    allocation_step = int(snapshot.get("allocation_step", 0))
    surplus_monthly = Decimal(str(snapshot.get("surplus_monthly", "0")))

    if allocation_step >= 6 or monthly_income <= 0:
        return None
    if surplus_monthly <= monthly_income * _SURPLUS_MONTHS_IDLE:
        return None

    return NodeProposal(
        node="alert",
        move=(
            f"Deploy the ${surplus_monthly:,.0f} monthly surplus — it's sitting above "
            f"the 3-month idle threshold. Fund Step {allocation_step + 1} next."
        ),
        principle="assets_over_liabilities",
        leverage_score=0.75,
        rationale=(
            f"Surplus ${surplus_monthly:,.0f} > {_SURPLUS_MONTHS_IDLE}× income "
            f"${monthly_income:,.0f}; allocation incomplete at Step {allocation_step}/6."
        ),
        requires_disclaimer=False,
    )


def _net_worth_pace_alert(net_worth_pace: dict) -> NodeProposal | None:
    """Fire when monthly net-worth delta is significantly negative."""
    if not net_worth_pace or net_worth_pace.get("on_pace", True):
        return None
    delta = Decimal(str(net_worth_pace.get("delta", "0")))
    if delta >= _NW_PACE_ALERT_THRESHOLD:
        return None

    return NodeProposal(
        node="alert",
        move=(
            f"Net worth is behind pace by ${abs(delta):,.0f}/month. "
            "Identify one budget cut or income lever to reverse the trend."
        ),
        principle="assets_over_liabilities",
        leverage_score=0.7,
        rationale=f"Monthly net-worth delta ${delta:,.0f} is below the pace threshold.",
        requires_disclaimer=False,
    )


# ── DB-backed alerts ──────────────────────────────────────────────────────────

async def _roth_room_alert(session: AsyncSession, today: date) -> list[NodeProposal]:
    """Fire within 90 days of Dec 31 when Roth IRA room remains unfunded."""
    dec31 = date(today.year, 12, 31)
    if (dec31 - today).days > _ROTH_WINDOW_DAYS:
        return []

    from vault.models import RetirementAccount

    result = await session.execute(
        select(RetirementAccount).where(RetirementAccount.kind == "roth_ira")
    )
    accounts = list(result.scalars().all())
    total_remaining = sum(
        Decimal(str(a.ytd_contribution_limit_remaining or 0)) for a in accounts
    )
    if total_remaining <= 0:
        return []

    days_left = (dec31 - today).days
    return [NodeProposal(
        node="alert",
        move=(
            f"${total_remaining:,.0f} of Roth IRA room expires Dec 31 "
            f"({days_left} days). Contribute now — unused room is gone forever."
        ),
        principle="tax_arbitrage",
        leverage_score=0.85,
        rationale=f"{days_left} days to year-end; ${total_remaining:,.0f} Roth room unfunded.",
        requires_disclaimer=True,
    )]


async def _deduction_gap_alert(session: AsyncSession, today: date) -> list[NodeProposal]:
    """Fire within 60 days of Dec 31 when expected 1099 deduction categories are missing."""
    dec31 = date(today.year, 12, 31)
    if (dec31 - today).days > _DEDUCTION_WINDOW_DAYS:
        return []

    from vault.models import TaxDeduction1099

    result = await session.execute(
        select(TaxDeduction1099.category)
        .where(TaxDeduction1099.tax_year == TAX_YEAR)
    )
    populated = {row[0] for row in result.fetchall()}
    missing = _EXPECTED_DEDUCTION_CATEGORIES - populated
    if not missing:
        return []

    days_left = (dec31 - today).days
    missing_str = ", ".join(sorted(missing))
    return [NodeProposal(
        node="alert",
        move=(
            f"Log missing 1099 deductions before Dec 31 ({days_left} days): {missing_str}. "
            "Each deduction saves 25–35 cents per dollar at SE-tax rates."
        ),
        principle="deduction_discipline_1099",
        leverage_score=0.8,
        rationale=f"{days_left} days to Dec 31; uncategorised: {missing_str}.",
        requires_disclaimer=True,
    )]


async def _negotiation_milestone_alert(
    session: AsyncSession, today: date
) -> list[NodeProposal]:
    """Fire for each upcoming negotiation milestone within 30 days."""
    from vault.models import NegotiationMilestone

    window_end = today + timedelta(days=_MILESTONE_WINDOW_DAYS)
    result = await session.execute(
        select(NegotiationMilestone).where(
            NegotiationMilestone.status == "upcoming",
            NegotiationMilestone.trigger_date >= today,
            NegotiationMilestone.trigger_date <= window_end,
        )
    )
    milestones = list(result.scalars().all())

    proposals = []
    for m in milestones:
        days_until = (m.trigger_date - today).days
        proposals.append(NodeProposal(
            node="alert",
            move=(
                f"Negotiation milestone '{m.kind}' in {days_until} day(s) "
                f"({m.trigger_date}). Anchor high, get it in writing."
            ),
            principle="comp_negotiation_anchor_high",
            leverage_score=0.9,
            rationale=f"Milestone '{m.kind}' on {m.trigger_date} — {days_until}d to prepare.",
            requires_disclaimer=False,
        ))
    return proposals


async def _career_offpace_alert(session: AsyncSession, today: date) -> list[NodeProposal]:
    """Fire when elapsed-fraction of career target exceeds comp-achieved-fraction."""
    from vault.models import CareerPosition

    result = await session.execute(
        select(CareerPosition)
        .where(
            CareerPosition.target_date.is_not(None),
            CareerPosition.target_comp_total.is_not(None),
            CareerPosition.current_comp_total.is_not(None),
        )
        .limit(1)
    )
    career = result.scalar_one_or_none()
    if career is None:
        return []

    updated_at = career.updated_at
    start_date = updated_at.date() if hasattr(updated_at, "date") else today
    target_date: date = career.target_date
    total_days = max((target_date - start_date).days, 1)
    elapsed_days = max((today - start_date).days, 0)
    elapsed_fraction = elapsed_days / total_days

    current_comp = Decimal(str(career.current_comp_total or 0))
    target_comp = Decimal(str(career.target_comp_total or 0))
    if target_comp <= current_comp or target_comp == 0:
        return []

    achieved_fraction = float(current_comp / target_comp)
    if elapsed_fraction <= achieved_fraction:
        return []

    gap_pp = (elapsed_fraction - achieved_fraction) * 100
    return [NodeProposal(
        node="alert",
        move=(
            f"Career is off-pace: {elapsed_fraction*100:.0f}% through target window, "
            f"{achieved_fraction*100:.0f}% of comp gap closed. "
            "Start job search or push for internal promotion."
        ),
        principle="career_income_as_wealth_lever",
        leverage_score=0.85,
        rationale=(
            f"Elapsed {elapsed_fraction*100:.0f}% vs achieved {achieved_fraction*100:.0f}% "
            f"— {gap_pp:.0f}pp behind."
        ),
        requires_disclaimer=False,
    )]
