"""Agent node unit tests — all Anthropic calls mocked."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

import agent.principles as p


# --- Principles registry ---

def test_all_principle_keys_present():
    from agent.prompts import PRINCIPLE_KEYS
    for key in PRINCIPLE_KEYS:
        assert key in p.PRINCIPLES, f"missing from PRINCIPLES: {key}"


def test_get_principle_returns_string():
    cite = p.get_principle("emergency_fund_first")
    assert isinstance(cite, str) and len(cite) > 10


def test_get_principle_unknown_key_raises():
    with pytest.raises(KeyError):
        p.get_principle("not_a_real_key")


def test_coach_tool_principle_enum_pinned_and_resolvable():
    """Coach's tool schema must pin `principle` to the registry, and every key
    in that enum (universal + arena) must resolve via get_principle()."""
    from agent.nodes.coach import _TOOL

    enum = _TOOL["input_schema"]["properties"]["enriched_proposals"]["items"][
        "properties"]["principle"]["enum"]
    assert set(enum) == set(p.get_all_keys())
    assert "house_hacking" in enum  # arena keys are registered
    for key in enum:
        assert isinstance(p.get_principle(key), str)


def test_tax_constants_are_positive():
    assert p.ROTH_IRA_LIMIT_2026 > 0
    assert p.K401_EMPLOYEE_LIMIT_2026 > 0
    assert p.MILEAGE_RATE_2026 > 0
    assert p.SE_TAX_RATE > 0


def test_arena_principles_importable():
    from agent.principles_real_estate import ARENA_PRINCIPLES as re
    from agent.principles_saas import ARENA_PRINCIPLES as saas
    from agent.principles_investing import ARENA_PRINCIPLES as inv
    assert len(re) >= 5
    assert len(saas) >= 5
    assert len(inv) >= 5


# --- Analyzer node ---

@pytest.mark.asyncio
async def test_analyzer_allocation_routing():
    from agent.nodes.analyzer import analyzer_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {"turn_kind": "allocation", "routes": ["allocation"]}

    mock_usage = MagicMock()
    mock_usage.input_tokens = 50
    mock_usage.output_tokens = 20

    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "Where should I put my $500 surplus?",
        "proposals": [],
        "routes": [],
        "turn_kind": "general",
    }

    with patch("agent.nodes.analyzer.get_anthropic", return_value=mock_client):
        result = await analyzer_node(state)

    assert result["turn_kind"] == "allocation"
    assert "allocation" in result["routes"]


# --- Strategist node ---

@pytest.mark.asyncio
async def test_strategist_emits_proposal():
    from agent.nodes.strategist import strategist_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "move": "Open a Roth IRA and contribute $583/month to hit the $7k annual limit.",
        "principle": "tax_arbitrage",
        "leverage_score": 0.85,
        "rationale": "Your IRA is unfunded while you're in a low bracket.",
        "requires_disclaimer": True,
    }

    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = MagicMock(input_tokens=100, output_tokens=50)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "What should I do with $500/month?",
        "wealth_position": {
            "step": 3,
            "step_name": "Tax-Advantaged",
            "rationale": "IRA not funded",
            "next_move": "Max Roth IRA",
        },
        "active_decisions": [],
        "proposals": [],
    }

    with patch("agent.nodes._llm.get_anthropic", return_value=mock_client):
        result = await strategist_node(state)

    assert len(result["proposals"]) == 1
    proposal = result["proposals"][0]
    assert proposal["node"] == "strategist"
    assert proposal["principle"] == "tax_arbitrage"
    assert 0.0 <= proposal["leverage_score"] <= 1.0
    assert isinstance(proposal["requires_disclaimer"], bool)
    # token usage flows back into state (accumulated across nodes via the reducer)
    assert result["tokens_in"] == 100
    assert result["tokens_out"] == 50


@pytest.mark.asyncio
async def test_proposal_node_survives_max_tokens_truncation():
    """A response with no tool_use block (max_tokens truncation) must NOT raise
    StopIteration — the specialist skips its proposal and the turn continues,
    still accounting the tokens it spent."""
    from agent.nodes.strategist import strategist_node

    text_block = MagicMock()
    text_block.type = "text"  # no tool_use block at all
    mock_resp = MagicMock()
    mock_resp.content = [text_block]
    mock_resp.stop_reason = "max_tokens"
    mock_resp.usage = MagicMock(input_tokens=120, output_tokens=512)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "?",
        "wealth_position": {"step": 3, "step_name": "x", "rationale": "", "next_move": ""},
        "active_decisions": [],
        "proposals": [],
    }
    with patch("agent.nodes._llm.get_anthropic", return_value=mock_client):
        result = await strategist_node(state)

    assert result["proposals"] == []          # skipped, not crashed
    assert result["tokens_in"] == 120         # tokens still counted
    assert result["tokens_out"] == 512


# --- Coach node ---

@pytest.mark.asyncio
async def test_coach_enriches_proposals():
    from agent.nodes.coach import coach_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "enriched_proposals": [{
            "node": "strategist",
            "move": "Max Roth IRA — $583/month.",
            "principle": "tax_arbitrage",
            "leverage_score": 0.88,
            "rationale": "Tax arbitrage at your bracket.",
            "requires_disclaimer": True,
            "principle_cite": "Tax arbitrage: Roth wins when current bracket < expected retirement bracket.",
        }]
    }

    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = MagicMock(input_tokens=150, output_tokens=60)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "Should I max my Roth?",
        "proposals": [{
            "node": "strategist",
            "move": "Max Roth IRA.",
            "principle": "tax_arbitrage",
            "leverage_score": 0.85,
            "rationale": "IRA unfunded.",
            "requires_disclaimer": True,
        }],
        "routes": [],
    }

    with patch("agent.nodes.coach.get_anthropic", return_value=mock_client):
        result = await coach_node(state)

    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["principle"] == "tax_arbitrage"


# --- Graph compilation ---

def test_graph_compiles():
    """Graph must compile without error after Issue 8 node additions."""
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
    from agent.graph import get_graph
    g = get_graph()
    assert g is not None


# ============================================================
# Issue 8b: Career, Income-Optimizer, Tax-Optimizer
# ============================================================

def test_income_optimizer_cuts_bottom_stream():
    from agent.nodes.income_optimizer import income_optimizer_node
    state = {
        "user_message": "Which side gig should I drop?",
        "vault_snapshot": {
            "income_streams": [
                {"source": "Coaching", "net_hourly": "45.00"},
                {"source": "DoorDash", "net_hourly": "8.50"},
            ]
        },
        "proposals": [],
    }
    result = income_optimizer_node(state)
    assert len(result["proposals"]) == 1
    p = result["proposals"][0]
    assert p["node"] == "income_optimizer"
    assert "DoorDash" in p["move"]
    assert p["principle"] == "side_income_hourly_truth"
    assert p["requires_disclaimer"] is False


def test_income_optimizer_no_streams_returns_proposal():
    from agent.nodes.income_optimizer import income_optimizer_node
    state = {
        "user_message": "Which gig should I cut?",
        "vault_snapshot": {},
        "proposals": [],
    }
    result = income_optimizer_node(state)
    assert len(result["proposals"]) == 1
    assert result["proposals"][0]["principle"] == "side_income_hourly_truth"


def test_income_optimizer_within_threshold_no_cut():
    from agent.nodes.income_optimizer import income_optimizer_node
    state = {
        "user_message": "How are my streams doing?",
        "vault_snapshot": {
            "income_streams": [
                {"source": "Coaching", "net_hourly": "40.00"},
                {"source": "DoorDash", "net_hourly": "32.00"},
            ]
        },
        "proposals": [],
    }
    result = income_optimizer_node(state)
    p = result["proposals"][0]
    # Gap is 20% (< 30% threshold) — should suggest scaling, not cutting
    assert "scale" in p["move"].lower() or "range" in p["move"].lower() or "within" in p["move"].lower()


@pytest.mark.asyncio
async def test_career_node_emits_proposal():
    from agent.nodes.career import career_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "move": "Apply to 3 senior roles in your metro with 15% comp bump target.",
        "principle": "job_switch_comp_arbitrage",
        "leverage_score": 0.90,
        "rationale": "Internal raise trajectory is 3%; external market offers 12-15%.",
        "requires_disclaimer": False,
    }
    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = MagicMock(input_tokens=80, output_tokens=40)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "Should I take the Stripe contract or stay at Cognizant?",
        "income_position": {"step": 3, "step_name": "Career Velocity", "rationale": "Comp below market", "next_move": "Switch or negotiate"},
        "vault_snapshot": {"career": {}},
        "proposals": [],
    }

    with patch("agent.nodes._llm.get_anthropic", return_value=mock_client):
        result = await career_node(state)

    assert len(result["proposals"]) == 1
    p = result["proposals"][0]
    assert p["node"] == "career"
    assert p["principle"] == "job_switch_comp_arbitrage"
    assert 0.0 <= p["leverage_score"] <= 1.0


@pytest.mark.asyncio
async def test_tax_optimizer_sets_disclaimer():
    from agent.nodes.tax_optimizer import tax_optimizer_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "move": "Log 847 DoorDash miles for 2026 at $0.70/mile = $592.90 deduction.",
        "principle": "deduction_discipline_1099",
        "leverage_score": 0.80,
        "rationale": "Mileage category is empty; this is the highest-value missing deduction.",
        "requires_disclaimer": True,
    }
    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = MagicMock(input_tokens=90, output_tokens=45)

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "Did I cover all my DoorDash mileage this year?",
        "vault_snapshot": {"tax_deductions": [], "income_1099_ytd": 8000},
        "proposals": [],
    }

    with patch("agent.nodes._llm.get_anthropic", return_value=mock_client):
        result = await tax_optimizer_node(state)

    assert len(result["proposals"]) == 1
    p = result["proposals"][0]
    assert p["requires_disclaimer"] is True
    assert p["principle"] == "deduction_discipline_1099"


def test_graph_compiles_with_8b_nodes():
    import os
    os.environ.setdefault("ANTHROPIC_API_KEY", "dummy")
    from importlib import reload
    import agent.graph
    reload(agent.graph)
    g = agent.graph.build_graph()
    assert g is not None
