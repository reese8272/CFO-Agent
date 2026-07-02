"""Canonical cadence → monthly conversion, shared across snapshot + position math.

This was previously duplicated in `financial_snapshot`, `income_position`, and
`wealth_position` with divergent constants (weekly 4.333 vs 4.33; `financial_snapshot`
missing `semimonthly`/`annually`/`yearly` and case-folding), so the same input
produced different monthly figures depending on which module computed it
(assessment 2026-07-02). One source of truth removes that drift.
"""
from decimal import Decimal

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
