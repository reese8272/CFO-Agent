"""Compute the user's current position on the 5-step income track.

Steps (from docs/WEALTH_PRINCIPLES.md):
  1 — Net Hourly Truth: compute true $/hr for every income stream
  2 — Cut the Bottom: drop lowest-margin stream when >30% below top
  3 — Career Velocity: comp benchmark; switch if delta beats internal raise by >7%
  4 — Deduction Discipline: every 1099 deduction captured
  5 — Negotiation Practice: anchor high, ask in writing, track milestones

No LLM calls — pure deterministic data logic.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import TypedDict

from vault._money import to_monthly as _to_monthly


class IncomeStep(TypedDict):
    step: int
    label: str
    monthly_target: "Decimal | None"
    monthly_actual: "Decimal"
    funded: bool


class IncomeLadder(TypedDict):
    total_monthly_income: "Decimal"
    income_ladder: list
    open_gaps: list
    timestamp: str


async def compute_income_position(session: AsyncSession, user_id: str) -> IncomeLadder:
    ladder, total = await _build_income_ladder(session)
    open_gaps = [s for s in ladder if not s["funded"]]

    return IncomeLadder(
        total_monthly_income=total,
        income_ladder=ladder,
        open_gaps=open_gaps,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def _build_income_ladder(session: AsyncSession) -> tuple[list[IncomeStep], Decimal]:
    from vault.models import IncomeStream, Expense, SideIncomeEconomics, TaxDeduction1099, NegotiationMilestone

    # Monthly expenses baseline
    result = await session.execute(select(Expense))
    expense_rows = result.scalars().all()
    monthly_expenses = Decimal("0")
    for r in expense_rows:
        amt = getattr(r, "typical_amount", None)
        cadence = getattr(r, "cadence", "monthly") or "monthly"
        if amt is not None:
            monthly_expenses += _to_monthly(Decimal(str(amt)), cadence)
    if monthly_expenses == Decimal("0"):
        monthly_expenses = Decimal("3000")

    # Income streams
    result = await session.execute(select(IncomeStream))
    streams = result.scalars().all()

    stream_monthlies: list[Decimal] = []
    for s in streams:
        amt = getattr(s, "typical_gross_amount", None)
        if amt is None:
            amt = getattr(s, "rolling_4wk_avg", None)
        cadence = getattr(s, "cadence", "monthly") or "monthly"
        if amt is None:
            continue
        monthly = _to_monthly(Decimal(str(amt)), cadence)
        stream_monthlies.append(monthly)

    # Step 1: Net Hourly Truth — funded if at least one active income stream exists
    # and we have side_income_economics data to compute net hourly
    result = await session.execute(select(SideIncomeEconomics))
    economics_rows = result.scalars().all()
    has_net_hourly_data = len(economics_rows) > 0
    total_monthly = sum(stream_monthlies, Decimal("0"))

    step1 = IncomeStep(
        step=1,
        label="Net Hourly Truth",
        monthly_target=None,
        monthly_actual=total_monthly,
        funded=has_net_hourly_data and len(streams) > 0,
    )

    # Step 2: Cut the Bottom — funded if only one stream or net hourly ranked and bottom cut
    # Conservative: funded if we have economics data and only 1 stream (no cutting needed)
    # or if multiple streams and we have economics data to rank them
    if len(stream_monthlies) <= 1:
        step2_funded = True  # nothing to cut
        step2_actual = total_monthly
    else:
        # Check if any stream is >30% below the top by monthly amount (proxy without full hourly data)
        if stream_monthlies:
            top = max(stream_monthlies)
            bottom = min(stream_monthlies)
            gap_pct = (top - bottom) / top if top > Decimal("0") else Decimal("0")
            step2_funded = gap_pct <= Decimal("0.3") or has_net_hourly_data
        else:
            step2_funded = True
        step2_actual = total_monthly

    step2 = IncomeStep(
        step=2,
        label="Cut the Bottom (lowest-margin stream)",
        monthly_target=None,
        monthly_actual=step2_actual,
        funded=step2_funded,
    )

    # Step 3: Career Velocity — funded if comp benchmark data exists
    from vault.models import CompBenchmark, CareerPosition
    result = await session.execute(select(CompBenchmark))
    benchmarks = result.scalars().all()
    result = await session.execute(select(CareerPosition))
    career_rows = result.scalars().all()

    career_monthly = Decimal("0")
    if career_rows:
        career = career_rows[0]
        comp = getattr(career, "current_comp_total", None)
        if comp is not None:
            career_monthly = Decimal(str(comp)) / Decimal("12")

    step3 = IncomeStep(
        step=3,
        label="Career Velocity (comp benchmark)",
        monthly_target=None,
        monthly_actual=career_monthly,
        funded=len(benchmarks) > 0 and len(career_rows) > 0,
    )

    # Step 4: Deduction Discipline — funded if any 1099 deductions recorded
    result = await session.execute(select(TaxDeduction1099))
    deduction_rows = result.scalars().all()
    deduction_total = Decimal("0")
    for r in deduction_rows:
        amt = getattr(r, "amount", None)
        if amt is not None:
            deduction_total += Decimal(str(amt))

    step4 = IncomeStep(
        step=4,
        label="Deduction Discipline (1099 deductions captured)",
        monthly_target=None,
        monthly_actual=deduction_total / Decimal("12"),
        funded=len(deduction_rows) > 0,
    )

    # Step 5: Negotiation Practice — funded if negotiation milestones tracked
    result = await session.execute(select(NegotiationMilestone))
    milestone_rows = result.scalars().all()

    step5 = IncomeStep(
        step=5,
        label="Negotiation Practice (milestones tracked)",
        monthly_target=None,
        monthly_actual=Decimal("0"),
        funded=len(milestone_rows) > 0,
    )

    # total monthly income is the actual income-stream sum; ladder steps are
    # analytical stages that restate the same income and must not be summed.
    return [step1, step2, step3, step4, step5], total_monthly


