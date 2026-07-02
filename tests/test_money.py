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


def test_all_three_modules_share_one_impl():
    """Regression: the snapshot + position modules must resolve `_to_monthly` to
    the same shared function so the same input never yields divergent figures."""
    from vault import financial_snapshot, income_position, wealth_position
    assert financial_snapshot._to_monthly is to_monthly
    assert income_position._to_monthly is to_monthly
    assert wealth_position._to_monthly is to_monthly
