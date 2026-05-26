"""Agent eval harness — canned scenarios with expected facts.

Each scenario provides a deterministic AgentState and asserts that the node
produces the correct principle, move direction, and disclaimer behaviour.
No LLM calls in scenarios 1 and 4 (pure logic nodes); scenarios 2 and 3
mock the Anthropic client.

Run with: pytest tests/eval/
"""
from __future__ import annotations
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from agent.nodes.income_optimizer import income_optimizer_node
from agent.state import AgentState


# ---------------------------------------------------------------------------
# Shared state builder
# ---------------------------------------------------------------------------

def _base_state(**overrides) -> AgentState:
    state: AgentState = {
        "user_message": "What should I do?",
        "conversation_id": None,
        "vault_snapshot": {},
        "wealth_position": {"step": 2, "step_name": "Emergency fund", "rationale": "", "next_move": ""},
        "income_position": {"step": 1, "step_name": "Cover basics", "rationale": "", "next_move": ""},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "financial_snapshot": None,
        "turn_kind": "general",
        "routes": [],
        "proposals": [],
        "trajectory_note": "",
        "tokens_in": 0,
        "tokens_out": 0,
    }
    state.update(overrides)
    return state


# ---------------------------------------------------------------------------
# Scenario 1: Emergency fund gap → income_optimizer recommends logging streams
# ---------------------------------------------------------------------------

def test_income_optimizer_no_streams_returns_log_prompt():
    """With no income streams, income_optimizer should request data entry."""
    state = _base_state(vault_snapshot={"income_streams": []})
    result = income_optimizer_node(state)
    proposals = result["proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["principle"] == "side_income_hourly_truth"
    assert p["requires_disclaimer"] is False
    assert "log" in p["move"].lower() or "stream" in p["move"].lower()


# ---------------------------------------------------------------------------
# Scenario 2: High-margin vs low-margin streams → cut recommendation
# ---------------------------------------------------------------------------

def test_income_optimizer_cuts_bottom_stream_when_gap_exceeds_30pct():
    """With a >30% net-hourly gap, income_optimizer should recommend cutting the bottom stream."""
    streams = [
        {"source": "Consulting", "net_hourly": "100.00"},
        {"source": "Etsy shop", "net_hourly": "20.00"},
    ]
    state = _base_state(vault_snapshot={"income_streams": streams})
    result = income_optimizer_node(state)
    proposals = result["proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["principle"] == "side_income_hourly_truth"
    assert "etsy shop" in p["move"].lower() or "cut" in p["move"].lower()
    assert p["leverage_score"] > 0.5


# ---------------------------------------------------------------------------
# Scenario 3: Tax optimizer — disclaimer always present
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tax_optimizer_always_sets_requires_disclaimer(monkeypatch):
    """tax_optimizer_node must set requires_disclaimer=True on every output."""
    from agent.nodes.tax_optimizer import tax_optimizer_node

    tool_input = {
        "move": "Max your Roth IRA now.",
        "principle": "roth_ira_first",
        "leverage_score": 0.9,
        "rationale": "Roth is highest leverage for your income.",
        "requires_disclaimer": True,
    }
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    fake_response = MagicMock()
    fake_response.content = [tool_block]
    fake_response.usage = MagicMock(input_tokens=80, output_tokens=40)

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    monkeypatch.setattr("agent.nodes.tax_optimizer.get_anthropic", lambda: fake_client)

    state = _base_state(
        vault_snapshot={"income_streams": []},
        income_position={"step": 2, "step_name": "Roth IRA", "rationale": "", "next_move": ""},
        financial_snapshot=None,
    )
    result = await tax_optimizer_node(state)
    proposals = result["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["requires_disclaimer"] is True


# ---------------------------------------------------------------------------
# Scenario 4: Surplus idle — income optimizer with near-equal streams
# ---------------------------------------------------------------------------

def test_income_optimizer_no_cut_when_streams_within_30pct():
    """When streams are within 30% of each other, income_optimizer should recommend scaling, not cutting."""
    streams = [
        {"source": "Freelance", "net_hourly": "80.00"},
        {"source": "Tutoring", "net_hourly": "70.00"},
    ]
    state = _base_state(vault_snapshot={"income_streams": streams})
    result = income_optimizer_node(state)
    proposals = result["proposals"]
    assert len(proposals) == 1
    p = proposals[0]
    assert p["principle"] == "side_income_hourly_truth"
    # Gap is 12.5% — below 30% threshold → scaling recommendation, not cut
    assert p["leverage_score"] == pytest.approx(0.4)
    assert "scale" in p["move"].lower() or "within" in p["move"].lower()
