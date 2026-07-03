"""Canonical cadence → monthly conversion, shared across snapshot + position math.

This was previously duplicated in `financial_snapshot`, `income_position`, and
`wealth_position` with divergent constants (weekly 4.333 vs 4.33; `financial_snapshot`
missing `semimonthly`/`annually`/`yearly` and case-folding), so the same input
produced different monthly figures depending on which module computed it
(assessment 2026-07-02). One source of truth removes that drift.
"""
from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

# Baseline monthly expenses assumed when the Expense table is empty. Shared by
# the snapshot and both position ladders so they never disagree (a prior
# divergence left the snapshot at savings_rate=100% while the wealth ladder
# showed an emergency-fund gap off this same floor — assessment 2026-07-03).
DEFAULT_MONTHLY_EXPENSES = Decimal("3000")

# Monthly-equivalent multipliers. Uses the more precise weekly/biweekly factors
# (52/12 ≈ 4.333, 26/12 ≈ 2.167) and the full cadence vocabulary + case-folding.
_MONTHLY_FACTORS: dict[str, Decimal] = {
    "weekly": Decimal("4.333"),
    "biweekly": Decimal("2.167"),
    "semimonthly": Decimal("2"),
    "monthly": Decimal("1"),
    "quarterly": Decimal("0.333"),
    "annual": Decimal("0.0833"),
    "annually": Decimal("0.0833"),
    "yearly": Decimal("0.0833"),
    "irregular": Decimal("1"),
}


def to_monthly(amount: Decimal, cadence: str) -> Decimal:
    """Convert an amount at the given pay cadence to its monthly equivalent.

    Unknown/blank cadences fall back to ×1 (treated as already monthly).
    """
    return amount * _MONTHLY_FACTORS.get((cadence or "").lower(), Decimal("1"))


async def sum_monthly_expenses(
    session: "AsyncSession", *, fallback: Decimal = DEFAULT_MONTHLY_EXPENSES
) -> Decimal:
    """Canonical total monthly expenses from the Expense table.

    The one source of truth for "how much does this person spend per month",
    used by the snapshot and both position ladders. Returns `fallback` when
    there are no expense rows or they sum to zero, so all three agree.
    """
    from sqlalchemy import select

    from vault.models import Expense

    rows = (await session.execute(select(Expense))).scalars().all()
    total = Decimal("0")
    for row in rows:
        amount = getattr(row, "typical_amount", None)
        if amount is not None:
            total += to_monthly(Decimal(str(amount)), getattr(row, "cadence", "monthly") or "monthly")
    return total if total > Decimal("0") else fallback
