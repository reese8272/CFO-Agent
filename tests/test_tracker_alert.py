"""Tracker + Alert node unit tests — all DB calls mocked, time frozen with freezegun."""
from __future__ import annotations
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from freezegun import freeze_time


# ── Tracker: pure helpers ──────────────────────────────────────────────────────

def test_tracker_build_note_contains_steps():
    from agent.nodes.tracker import _build_note

    wealth_pos = {"step": 3, "step_name": "Tax-Advantaged", "rationale": "", "next_move": ""}
    income_pos = {"step": 2, "step_name": "Side Income", "rationale": "", "next_move": ""}
    note = _build_note(wealth_pos, income_pos, {}, Decimal("4500"))

    assert "Step 3/6" in note
    assert "Step 2/5" in note
    assert "4,500" in note


@freeze_time("2026-07-01")
def test_tracker_pace_from_goal_on_pace():
    from agent.nodes.tracker import _pace_from_goal

    class FakeGoal:
        target_amount = Decimal("100000")
        deadline = date(2027, 1, 1)
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # At 2026-07-01: elapsed ~181 days / 365 total → expected ~49.6k; current=60k → on pace
    result = _pace_from_goal(Decimal("60000"), Decimal("0"), FakeGoal(), date(2026, 7, 1))

    assert result["on_pace"] is True
    assert Decimal(result["delta"]) > 0


@freeze_time("2026-07-01")
def test_tracker_pace_from_goal_behind():
    from agent.nodes.tracker import _pace_from_goal

    class FakeGoal:
        target_amount = Decimal("100000")
        deadline = date(2027, 1, 1)
        created_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # At 2026-07-01: expected ~49.6k; current=30k → behind
    result = _pace_from_goal(Decimal("30000"), Decimal("0"), FakeGoal(), date(2026, 7, 1))

    assert result["on_pace"] is False
    assert Decimal(result["delta"]) < 0


def test_tracker_pace_from_snapshots_on_pace():
    from agent.nodes.tracker import _pace_from_snapshots

    first_date = date(2026, 1, 1)
    today = date(2026, 7, 1)
    result = _pace_from_snapshots(Decimal("60000"), Decimal("40000"), first_date, today)

    assert result["on_pace"] is True
    assert Decimal(result["delta"]) > 0


def test_tracker_pace_from_snapshots_behind():
    from agent.nodes.tracker import _pace_from_snapshots

    first_date = date(2026, 1, 1)
    today = date(2026, 7, 1)
    result = _pace_from_snapshots(Decimal("35000"), Decimal("40000"), first_date, today)

    assert result["on_pace"] is False


@pytest.mark.asyncio
async def test_tracker_node_returns_trajectory_note():
    from agent.nodes.tracker import tracker_node

    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    mock_ctx = AsyncMock()
    mock_ctx.__aenter__ = AsyncMock(return_value=mock_session)
    mock_ctx.__aexit__ = AsyncMock(return_value=None)

    state = {
        "vault_snapshot": {
            "net_worth": "15000",
            "total_monthly_income": "4000",
            "allocation_step": 2,
            "income_step": 1,
        },
        "wealth_position": {
            "step": 2, "step_name": "Debt Elimination",
            "rationale": "Has debt", "next_move": "Pay off card",
        },
        "income_position": {
            "step": 1, "step_name": "W-2 Income",
            "rationale": "Primary income", "next_move": "Log side income",
        },
    }

    with patch("agent.nodes.tracker.get_sessionmaker", return_value=lambda: mock_ctx):
        result = await tracker_node(state)

    assert "trajectory_note" in result
    assert "Step 2/6" in result["trajectory_note"]


# ── Alert: surplus (pure state) ────────────────────────────────────────────────

def test_surplus_alert_fires_when_above_threshold():
    from agent.nodes.alert import _surplus_alert

    snapshot = {"total_monthly_income": "3000", "allocation_step": 3, "surplus_monthly": "10000"}
    proposal = _surplus_alert(snapshot)
    assert proposal is not None
    assert proposal["principle"] == "assets_over_liabilities"
    assert proposal["node"] == "alert"


def test_surplus_alert_no_fire_when_below_threshold():
    from agent.nodes.alert import _surplus_alert

    snapshot = {"total_monthly_income": "3000", "allocation_step": 3, "surplus_monthly": "5000"}
    assert _surplus_alert(snapshot) is None


def test_surplus_alert_no_fire_when_step_6():
    from agent.nodes.alert import _surplus_alert

    snapshot = {"total_monthly_income": "3000", "allocation_step": 6, "surplus_monthly": "20000"}
    assert _surplus_alert(snapshot) is None


# ── Alert: net-worth pace (pure state) ────────────────────────────────────────

def test_net_worth_pace_alert_fires_when_significantly_behind():
    from agent.nodes.alert import _net_worth_pace_alert

    pace = {"current": "10000", "target_at_now": "15000", "delta": "-1000", "on_pace": False}
    proposal = _net_worth_pace_alert(pace)
    assert proposal is not None
    assert proposal["node"] == "alert"


def test_net_worth_pace_alert_no_fire_when_on_pace():
    from agent.nodes.alert import _net_worth_pace_alert

    pace = {"current": "15000", "target_at_now": "12000", "delta": "300", "on_pace": True}
    assert _net_worth_pace_alert(pace) is None


def test_net_worth_pace_alert_no_fire_when_slightly_behind():
    from agent.nodes.alert import _net_worth_pace_alert

    # delta = -100, threshold is -500 — not bad enough to alert
    pace = {"current": "9900", "target_at_now": "10000", "delta": "-100", "on_pace": False}
    assert _net_worth_pace_alert(pace) is None


# ── Alert: Roth room (DB-backed, time-frozen) ──────────────────────────────────

@pytest.mark.asyncio
async def test_roth_room_alert_fires_within_90_days():
    from agent.nodes.alert import _roth_room_alert

    class FakeRoth:
        kind = "roth_ira"
        ytd_contribution_limit_remaining = Decimal("2000")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [FakeRoth()]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-10-10"):
        result = await _roth_room_alert(mock_session, date(2026, 10, 10))

    assert len(result) == 1
    assert result[0]["principle"] == "tax_arbitrage"
    assert result[0]["requires_disclaimer"] is True
    assert "2,000" in result[0]["move"]


@pytest.mark.asyncio
async def test_roth_room_alert_no_fire_far_from_yearend():
    from agent.nodes.alert import _roth_room_alert

    mock_session = AsyncMock()

    with freeze_time("2026-06-01"):
        result = await _roth_room_alert(mock_session, date(2026, 6, 1))

    assert result == []


# ── Alert: deduction gap (DB-backed, time-frozen) ──────────────────────────────

@pytest.mark.asyncio
async def test_deduction_gap_alert_fires_within_60_days():
    from agent.nodes.alert import _deduction_gap_alert

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [("mileage",)]  # only mileage populated
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-11-15"):
        result = await _deduction_gap_alert(mock_session, date(2026, 11, 15))

    assert len(result) == 1
    assert result[0]["principle"] == "deduction_discipline_1099"
    assert result[0]["requires_disclaimer"] is True
    move = result[0]["move"]
    assert "home_office" in move or "equipment" in move


@pytest.mark.asyncio
async def test_deduction_gap_alert_no_fire_far_from_yearend():
    from agent.nodes.alert import _deduction_gap_alert

    mock_session = AsyncMock()

    with freeze_time("2026-06-01"):
        result = await _deduction_gap_alert(mock_session, date(2026, 6, 1))

    assert result == []


@pytest.mark.asyncio
async def test_deduction_gap_alert_no_fire_all_populated():
    from agent.nodes.alert import _deduction_gap_alert

    mock_result = MagicMock()
    mock_result.fetchall.return_value = [
        ("mileage",), ("home_office",), ("equipment",)
    ]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-11-15"):
        result = await _deduction_gap_alert(mock_session, date(2026, 11, 15))

    assert result == []


# ── Alert: negotiation milestone (DB-backed, time-frozen) ─────────────────────

@pytest.mark.asyncio
async def test_negotiation_milestone_alert_fires_within_30_days():
    from agent.nodes.alert import _negotiation_milestone_alert

    class FakeMilestone:
        kind = "annual_review"
        trigger_date = date(2026, 6, 20)
        status = "upcoming"

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [FakeMilestone()]
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-06-01"):
        result = await _negotiation_milestone_alert(mock_session, date(2026, 6, 1))

    assert len(result) == 1
    assert result[0]["principle"] == "comp_negotiation_anchor_high"
    assert "19 day" in result[0]["move"]


@pytest.mark.asyncio
async def test_negotiation_milestone_alert_no_fire_when_empty():
    from agent.nodes.alert import _negotiation_milestone_alert

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-06-01"):
        result = await _negotiation_milestone_alert(mock_session, date(2026, 6, 1))

    assert result == []


# ── Alert: career off-pace (DB-backed, time-frozen) ──────────────────────────

@pytest.mark.asyncio
async def test_career_offpace_alert_fires_when_behind():
    from agent.nodes.alert import _career_offpace_alert

    class FakeCareer:
        target_date = date(2027, 1, 1)
        target_comp_total = Decimal("120000")
        current_comp_total = Decimal("80000")
        updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = FakeCareer()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # At 2026-10-01: elapsed=273/365=74.8%, achieved=80k/120k=66.7% → off-pace
    with freeze_time("2026-10-01"):
        result = await _career_offpace_alert(mock_session, date(2026, 10, 1))

    assert len(result) == 1
    assert result[0]["principle"] == "career_income_as_wealth_lever"


@pytest.mark.asyncio
async def test_career_offpace_alert_no_fire_when_on_pace():
    from agent.nodes.alert import _career_offpace_alert

    class FakeCareer:
        target_date = date(2027, 1, 1)
        target_comp_total = Decimal("120000")
        current_comp_total = Decimal("90000")   # achieved=75%
        updated_at = datetime(2026, 1, 1, tzinfo=timezone.utc)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = FakeCareer()
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    # At 2026-07-01: elapsed=181/365=49.6%, achieved=90k/120k=75% → on-pace
    with freeze_time("2026-07-01"):
        result = await _career_offpace_alert(mock_session, date(2026, 7, 1))

    assert result == []


@pytest.mark.asyncio
async def test_career_offpace_alert_no_fire_no_data():
    from agent.nodes.alert import _career_offpace_alert

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session = AsyncMock()
    mock_session.execute = AsyncMock(return_value=mock_result)

    with freeze_time("2026-10-01"):
        result = await _career_offpace_alert(mock_session, date(2026, 10, 1))

    assert result == []


# ── Graph compiles with new nodes ──────────────────────────────────────────────

def test_graph_compiles_with_tracker_and_alert():
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
    # Reset cached graph so build_graph() runs fresh with the new nodes
    import agent.graph as ag
    ag._graph = None
    g = ag.get_graph()
    assert g is not None
