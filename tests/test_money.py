"""Canonical cadence→monthly conversion (unified from 3 divergent copies)."""
from decimal import Decimal

import pytest

from vault._money import to_monthly


@pytest.mark.parametrize("cadence,factor", [
    ("weekly", "4.333"),
    ("biweekly", "2.167"),
    ("semimonthly", "2"),
    ("monthly", "1"),
    ("quarterly", "0.333"),
    ("annual", "0.0833"),
    ("annually", "0.0833"),
    ("yearly", "0.0833"),
    ("irregular", "1"),
])
def test_to_monthly_factors(cadence, factor):
    assert to_monthly(Decimal("100"), cadence) == Decimal("100") * Decimal(factor)


def test_to_monthly_is_case_insensitive():
    assert to_monthly(Decimal("100"), "WEEKLY") == to_monthly(Decimal("100"), "weekly")


def test_to_monthly_unknown_and_blank_fall_back_to_monthly():
    assert to_monthly(Decimal("100"), "fortnightly") == Decimal("100")
    assert to_monthly(Decimal("100"), "") == Decimal("100")


def test_modules_share_one_cadence_and_expense_impl():
    """Regression: cadence math and expense-summing must each have ONE source of
    truth, so the snapshot and both ladders never yield divergent figures
    (assessment 2026-07-03). Stream-level cadence math shares `to_monthly`;
    expense-summing (with the shared fallback floor) shares `sum_monthly_expenses`."""
    from vault import financial_snapshot, income_position, wealth_position
    from vault._money import sum_monthly_expenses

    # cadence math for income streams
    assert financial_snapshot._to_monthly is to_monthly
    assert income_position._to_monthly is to_monthly
    # expense-summing with the shared floor: snapshot + wealth ladder call the one helper
    assert financial_snapshot.sum_monthly_expenses is sum_monthly_expenses
    assert wealth_position.sum_monthly_expenses is sum_monthly_expenses


@pytest.mark.asyncio
async def test_sum_monthly_expenses_falls_back_to_shared_floor(session, clean_db):
    """The empty-Expense fallback is the single DEFAULT_MONTHLY_EXPENSES value —
    this is what keeps the snapshot's savings-rate consistent with the ladder's
    emergency-fund gap instead of reporting a phantom 100% savings rate."""
    from vault._money import sum_monthly_expenses, DEFAULT_MONTHLY_EXPENSES

    assert await sum_monthly_expenses(session) == DEFAULT_MONTHLY_EXPENSES
