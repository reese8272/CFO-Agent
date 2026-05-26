"""Retrieval node unit tests — no live DB required."""
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from memory.retrieval import (
    _bridge_income,
    _bridge_wealth,
    _round100,
    build_profile_block,
)


def _make_full_wealth(funded: bool = False) -> dict:
    gap = {
        "step": 1,
        "label": "Emergency Fund",
        "gap": Decimal("9000"),
        "current": Decimal("0"),
        "target": "3 months",
        "funded": funded,
    }
    return {
        "net_worth": Decimal("50000"),
        "total_assets": Decimal("60000"),
        "total_liabilities": Decimal("10000"),
        "allocation_ladder": [gap],
        "open_gaps": [] if funded else [gap],
        "timestamp": "2026-05-25T00:00:00+00:00",
    }


def _make_full_income(funded: bool = False) -> dict:
    step = {
        "step": 1,
        "label": "Active Income Stability",
        "monthly_actual": Decimal("2000"),
        "monthly_target": Decimal("3000"),
        "funded": funded,
    }
    return {
        "total_monthly_income": Decimal("2000"),
        "income_ladder": [step],
        "open_gaps": [] if funded else [step],
        "timestamp": "2026-05-25T00:00:00+00:00",
    }


def test_bridge_wealth_unfunded() -> None:
    pos = _bridge_wealth(_make_full_wealth(funded=False))
    assert pos["step"] == 1
    assert "Emergency Fund" in pos["step_name"]
    assert pos["next_move"] != ""
    assert pos["rationale"] != ""


def test_bridge_wealth_all_funded() -> None:
    pos = _bridge_wealth(_make_full_wealth(funded=True))
    assert pos["step"] == 6
    assert pos["step_name"] == "All steps funded"


def test_bridge_income_unfunded() -> None:
    pos = _bridge_income(_make_full_income(funded=False))
    assert pos["step"] == 1
    assert "Active Income Stability" in pos["step_name"]
    assert "2,000" in pos["rationale"] or "2000" in pos["rationale"]


def test_bridge_income_all_funded() -> None:
    pos = _bridge_income(_make_full_income(funded=True))
    assert pos["step"] == 5
    assert pos["step_name"] == "All income steps funded"


def test_round100_rounds_up() -> None:
    assert _round100(Decimal("9001")) == Decimal("9100")
    assert _round100(Decimal("9000")) == Decimal("9000")
    assert _round100(Decimal("0")) == Decimal("0")
    assert _round100(Decimal("50")) == Decimal("100")


def test_profile_block_deterministic() -> None:
    ctx = {
        "wealth_position": {
            "step": 1,
            "step_name": "Emergency Fund",
            "rationale": "x",
            "next_move": "y",
        },
        "income_position": {
            "step": 1,
            "step_name": "Active Income",
            "rationale": "a",
            "next_move": "b",
        },
        "vault_snapshot": {"net_worth": "50000"},
        "active_decisions": [],
        "recent_patterns": [],
    }
    block1 = build_profile_block(ctx)
    block2 = build_profile_block(ctx)
    assert block1 == block2
    assert "Emergency Fund" in block1
    assert "## User Financial Profile" in block1


@pytest.mark.asyncio
async def test_retrieval_context_has_required_keys() -> None:
    from memory.retrieval import build_retrieval_context

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    mock_wealth = _make_full_wealth()
    mock_income = _make_full_income()
    with (
        patch("memory.retrieval.compute_wealth_position", return_value=mock_wealth),
        patch("memory.retrieval.compute_income_position", return_value=mock_income),
    ):
        ctx = await build_retrieval_context(session, "user1")

    required_keys = {
        "vault_snapshot",
        "wealth_position",
        "income_position",
        "active_decisions",
        "recent_patterns",
        "memory_summary",
    }
    assert required_keys.issubset(ctx.keys())


@pytest.mark.asyncio
async def test_retrieval_context_memory_summary_is_none() -> None:
    """memory_summary is None until Issue 9 compaction lands."""
    from memory.retrieval import build_retrieval_context

    session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    session.execute = AsyncMock(return_value=mock_result)

    mock_wealth = _make_full_wealth()
    mock_income = _make_full_income()
    with (
        patch("memory.retrieval.compute_wealth_position", return_value=mock_wealth),
        patch("memory.retrieval.compute_income_position", return_value=mock_income),
    ):
        ctx = await build_retrieval_context(session, "user1")

    assert ctx["memory_summary"] is None
