"""Compute the user's current position on the 6-step allocation track.

Steps (from docs/WEALTH_PRINCIPLES.md):
  1 — Emergency Fund: 3-6 months expenses in cash/HYSA
  2 — Eliminate High-Interest Debt: debts > 7% APR
  3 — Tax-Advantaged (Roth IRA + HSA): $7,000 + $4,300 per year (2026)
  4 — Market Exposure: taxable brokerage / index funds
  5 — Leverage: real estate with positive cash flow
  6 — Ownership: business income that doesn't require your time

No LLM calls — pure deterministic data logic.
"""
from __future__ import annotations
from decimal import Decimal
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import TypedDict

from agent.principles import (
    ROTH_IRA_LIMIT_2026,
    HSA_LIMIT_SINGLE_2026,
    K401_EMPLOYEE_LIMIT_2026,
    HIGH_INTEREST_APR_THRESHOLD,
)
from vault._money import sum_monthly_expenses


class AllocationGap(TypedDict):
    step: int
    label: str
    target: str
    current: "Decimal"
    gap: "Decimal"
    funded: bool


class WealthLadder(TypedDict):
    net_worth: "Decimal"
    total_assets: "Decimal"
    total_liabilities: "Decimal"
    allocation_ladder: list
    open_gaps: list
    timestamp: str


# Year-versioned tax constants come from agent/principles.py (single source of
# truth, stamped with the tax year); wrapped as Decimal for money math here.
_IRA_ANNUAL = Decimal(str(ROTH_IRA_LIMIT_2026))
_HSA_ANNUAL_SINGLE = Decimal(str(HSA_LIMIT_SINGLE_2026))
_401K_ANNUAL = Decimal(str(K401_EMPLOYEE_LIMIT_2026))
_HIGH_INTEREST_THRESHOLD = Decimal(str(HIGH_INTEREST_APR_THRESHOLD))
_MONTHS_EMERGENCY = Decimal("3")   # conservative policy floor (not a tax constant)


async def compute_wealth_position(session: AsyncSession, user_id: str) -> WealthLadder:
    assets = await _sum_assets(session)
    liabilities = await _sum_liabilities(session)
    net_worth = assets - liabilities

    ladder = await _build_allocation_ladder(session, assets, liabilities)
    open_gaps = [step for step in ladder if not step["funded"]]

    return WealthLadder(
        net_worth=net_worth,
        total_assets=assets,
        total_liabilities=liabilities,
        allocation_ladder=ladder,
        open_gaps=open_gaps,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )


async def _sum_assets(session: AsyncSession) -> Decimal:
    """Sum all assets: Account balances + Asset values + RealEstate current_value."""
    from vault.models import Account, Asset, RealEstate, RetirementAccount

    total = Decimal("0")

    # Checking/savings/cash accounts
    result = await session.execute(select(Account))
    for row in result.scalars().all():
        bal = getattr(row, "current_balance", None)
        if bal is not None:
            total += Decimal(str(bal))

    # Physical assets (vehicles, equipment, other)
    result = await session.execute(select(Asset))
    for row in result.scalars().all():
        val = getattr(row, "value_estimate", None)
        if val is not None:
            total += Decimal(str(val))

    # Real estate current value
    result = await session.execute(select(RealEstate))
    for row in result.scalars().all():
        val = getattr(row, "current_value", None)
        if val is not None:
            total += Decimal(str(val))

    # Retirement account balances
    result = await session.execute(select(RetirementAccount))
    for row in result.scalars().all():
        bal = getattr(row, "balance", None)
        if bal is not None:
            total += Decimal(str(bal))

    return total


async def _sum_liabilities(session: AsyncSession) -> Decimal:
    """Sum all liabilities: Debt balances + RealEstate mortgage balances."""
    from vault.models import Debt, RealEstate

    total = Decimal("0")

    result = await session.execute(select(Debt))
    for row in result.scalars().all():
        bal = getattr(row, "balance", None)
        if bal is not None:
            total += Decimal(str(bal))

    # Mortgage balances
    result = await session.execute(select(RealEstate))
    for row in result.scalars().all():
        mort = getattr(row, "mortgage_balance", None)
        if mort is not None:
            total += Decimal(str(mort))

    return total


async def _build_allocation_ladder(
    session: AsyncSession, assets: Decimal, liabilities: Decimal
) -> list[AllocationGap]:
    # Step 1: Emergency fund
    monthly_expenses = await _estimate_monthly_expenses(session)
    emergency_target = monthly_expenses * _MONTHS_EMERGENCY
    cash_balance = await _sum_cash(session)
    step1 = AllocationGap(
        step=1,
        label="Emergency Fund",
        target=f"3 months expenses (~${emergency_target:,.0f})",
        current=cash_balance,
        gap=max(Decimal("0"), emergency_target - cash_balance),
        funded=cash_balance >= emergency_target,
    )

    # Step 2: High-interest debt (>7% APR)
    high_interest_debt = await _sum_high_interest_debt(session)
    step2 = AllocationGap(
        step=2,
        label="High-Interest Debt",
        target="$0 remaining at >7% APR",
        current=Decimal("0"),
        gap=high_interest_debt,
        funded=high_interest_debt == Decimal("0"),
    )

    # Step 3: Tax-advantaged accounts (Roth IRA + HSA)
    ira_ytd = await _ira_contributions_ytd(session)
    hsa_ytd = await _hsa_contributions_ytd(session)
    tax_adv_target = _IRA_ANNUAL + _HSA_ANNUAL_SINGLE
    tax_adv_current = ira_ytd + hsa_ytd
    step3 = AllocationGap(
        step=3,
        label="Tax-Advantaged Accounts (IRA + HSA)",
        target=f"Max IRA (${_IRA_ANNUAL:,}/yr) + HSA (${_HSA_ANNUAL_SINGLE:,}/yr)",
        current=tax_adv_current,
        gap=max(Decimal("0"), tax_adv_target - tax_adv_current),
        funded=tax_adv_current >= tax_adv_target,
    )

    # Step 4: Market exposure — taxable brokerage / index funds
    # Check Account table for brokerage-type accounts
    taxable_balance = await _sum_taxable_brokerage(session)
    step4 = AllocationGap(
        step=4,
        label="Market Exposure (Taxable Brokerage)",
        target="Invest surplus in index funds after steps 1-3",
        current=taxable_balance,
        gap=Decimal("0") if taxable_balance > Decimal("0") else Decimal("1"),
        funded=taxable_balance > Decimal("0"),
    )

    # Step 5: Real estate leverage
    real_estate_equity = await _sum_real_estate_equity(session)
    step5 = AllocationGap(
        step=5,
        label="Leverage (Real Estate)",
        target="Cash-flowing real estate or investment property",
        current=real_estate_equity,
        gap=Decimal("0") if real_estate_equity > Decimal("0") else Decimal("1"),
        funded=real_estate_equity > Decimal("0"),
    )

    # Step 6: Business ownership
    business_net = await _sum_business_net_income(session)
    step6 = AllocationGap(
        step=6,
        label="Ownership (Business Income)",
        target="Business income that doesn't require your time",
        current=business_net,
        gap=Decimal("0") if business_net > Decimal("0") else Decimal("1"),
        funded=business_net > Decimal("0"),
    )

    return [step1, step2, step3, step4, step5, step6]


async def _estimate_monthly_expenses(session: AsyncSession) -> Decimal:
    """Estimate total monthly expenses (delegates to the shared canonical helper)."""
    return await sum_monthly_expenses(session)


async def _sum_cash(session: AsyncSession) -> Decimal:
    """Sum checking/savings/cash account balances."""
    from vault.models import Account

    result = await session.execute(select(Account))
    rows = result.scalars().all()
    total = Decimal("0")
    for row in rows:
        account_type = getattr(row, "type", "") or ""
        # Include cash-equivalent accounts; exclude credit/loan types
        if account_type.lower() in ("checking", "savings", "cash", "hysa", "money_market", ""):
            bal = getattr(row, "current_balance", None)
            if bal is not None:
                total += Decimal(str(bal))
    return total


async def _sum_high_interest_debt(session: AsyncSession) -> Decimal:
    """Sum debt balances with APR > 7%."""
    from vault.models import Debt

    result = await session.execute(select(Debt))
    rows = result.scalars().all()
    total = Decimal("0")
    for row in rows:
        apr = getattr(row, "apr", None)
        bal = getattr(row, "balance", None)
        if apr is not None and bal is not None:
            if Decimal(str(apr)) > _HIGH_INTEREST_THRESHOLD:
                total += Decimal(str(bal))
    return total


async def _ira_contributions_ytd(session: AsyncSession) -> Decimal:
    """Sum YTD contributions to IRA accounts (roth_ira, traditional_ira)."""
    from vault.models import RetirementAccount

    result = await session.execute(
        select(RetirementAccount).where(
            RetirementAccount.kind.in_(["roth_ira", "traditional_ira", "ira"])
        )
    )
    rows = result.scalars().all()
    return sum(
        (Decimal(str(r.ytd_contribution)) for r in rows if getattr(r, "ytd_contribution", None)),
        Decimal("0"),
    )


async def _hsa_contributions_ytd(session: AsyncSession) -> Decimal:
    """Sum YTD contributions to HSA accounts."""
    from vault.models import RetirementAccount

    result = await session.execute(
        select(RetirementAccount).where(
            RetirementAccount.kind.in_(["hsa"])
        )
    )
    rows = result.scalars().all()
    return sum(
        (Decimal(str(r.ytd_contribution)) for r in rows if getattr(r, "ytd_contribution", None)),
        Decimal("0"),
    )


async def _sum_taxable_brokerage(session: AsyncSession) -> Decimal:
    """Sum brokerage account balances from Account table."""
    from vault.models import Account

    result = await session.execute(select(Account))
    rows = result.scalars().all()
    total = Decimal("0")
    for row in rows:
        account_type = getattr(row, "type", "") or ""
        if account_type.lower() in ("brokerage", "taxable", "investment"):
            bal = getattr(row, "current_balance", None)
            if bal is not None:
                total += Decimal(str(bal))
    return total


async def _sum_real_estate_equity(session: AsyncSession) -> Decimal:
    """Sum real estate equity estimates."""
    from vault.models import RealEstate

    result = await session.execute(select(RealEstate))
    rows = result.scalars().all()
    total = Decimal("0")
    for row in rows:
        equity = getattr(row, "equity_estimate", None)
        if equity is not None:
            total += Decimal(str(equity))
        else:
            # Compute from current_value - mortgage_balance if equity_estimate absent
            val = getattr(row, "current_value", None)
            mort = getattr(row, "mortgage_balance", None)
            if val is not None:
                mort_dec = Decimal(str(mort)) if mort is not None else Decimal("0")
                computed_equity = Decimal(str(val)) - mort_dec
                if computed_equity > Decimal("0"):
                    total += computed_equity
    return total


async def _sum_business_net_income(session: AsyncSession) -> Decimal:
    """Sum monthly net income from business_income table."""
    from vault.models import BusinessIncome

    result = await session.execute(select(BusinessIncome))
    rows = result.scalars().all()
    total = Decimal("0")
    for row in rows:
        net = getattr(row, "net_margin", None)
        if net is not None and Decimal(str(net)) > Decimal("0"):
            total += Decimal(str(net))
    return total
