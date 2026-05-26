"""Wealth and income position unit tests — no live DB required."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock
import pytest

from vault.income_position import _to_monthly


def test_to_monthly_weekly():
    result = _to_monthly(Decimal("500"), "weekly")
    assert result == Decimal("500") * Decimal("4.33")


def test_to_monthly_annual():
    result = _to_monthly(Decimal("60000"), "annual")
    assert result == Decimal("60000") * Decimal("0.0833")


def test_to_monthly_unknown_cadence_defaults_to_monthly():
    result = _to_monthly(Decimal("5000"), "unknown")
    assert result == Decimal("5000")


@pytest.mark.asyncio
async def test_emergency_fund_unfunded_with_no_data():
    from vault.wealth_position import _estimate_monthly_expenses, _sum_cash
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    expenses = await _estimate_monthly_expenses(session)
    cash = await _sum_cash(session)
    assert expenses == Decimal("3000")
    assert cash == Decimal("0")
    assert cash < expenses * Decimal("3")


@pytest.mark.asyncio
async def test_income_position_empty_db():
    from vault.income_position import compute_income_position
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    pos = await compute_income_position(session, "user1")
    assert pos["total_monthly_income"] == Decimal("0")
    assert len(pos["income_ladder"]) == 5
    assert not pos["income_ladder"][0]["funded"]


@pytest.mark.asyncio
async def test_wealth_position_empty_db():
    from vault.wealth_position import compute_wealth_position
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    pos = await compute_wealth_position(session, "user1")
    assert pos["net_worth"] == Decimal("0")
    assert len(pos["allocation_ladder"]) == 6
    assert not pos["allocation_ladder"][0]["funded"]


def test_income_position_step_count():
    """Income ladder always has exactly 5 steps."""
    import asyncio
    from vault.income_position import compute_income_position
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    pos = asyncio.run(compute_income_position(session, "u"))
    assert len(pos["income_ladder"]) == 5


def test_wealth_ladder_step_count():
    """Allocation ladder always has exactly 6 steps."""
    import asyncio
    from vault.wealth_position import compute_wealth_position
    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)
    pos = asyncio.run(compute_wealth_position(session, "u"))
    assert len(pos["allocation_ladder"]) == 6
