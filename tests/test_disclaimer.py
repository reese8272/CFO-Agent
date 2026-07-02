"""Structural: disclaimer present on every tax/legal/investment response."""
import pytest
from unittest.mock import AsyncMock, MagicMock

from agent.prompts import CFO_SYSTEM_PROMPT
from disclaimer import DISCLAIMER, get_disclaimer


def test_disclaimer_text_in_system_prompt():
    """The disclaimer must appear verbatim in the CFO system prompt."""
    assert DISCLAIMER in CFO_SYSTEM_PROMPT


def test_get_disclaimer_returns_default():
    import os
    os.environ.pop("WEALTH_DISCLAIMER_TEXT", None)
    assert get_disclaimer() == DISCLAIMER


@pytest.mark.asyncio
async def test_requires_disclaimer_propagates(monkeypatch):
    """synthesizer_node attaches disclaimer text when requires_disclaimer=True."""
    from agent.nodes.synthesizer import synthesizer_node

    tool_input = {
        "recommendation": "Max your Roth IRA immediately.",
        "reasoning": "Tax-free compounding is the highest-leverage move.",
        "principle": "roth_ira_first",
        "requires_disclaimer": True,
        "vision_stamp": "Freedom 2045",
        "is_decision": False,
        "decision_summary": None,
    }
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    fake_response = MagicMock()
    fake_response.content = [tool_block]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)

    monkeypatch.setattr("agent.nodes.synthesizer.get_anthropic", lambda: fake_client)

    state = {
        "user_message": "Should I do a Roth?",
        "conversation_id": None,
        "vault_snapshot": {},
        "wealth_position": {"step": 3, "step_name": "Roth IRA", "rationale": "", "next_move": ""},
        "income_position": {"step": 2, "step_name": "Core expenses", "rationale": "", "next_move": ""},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "financial_snapshot": None,
        "turn_kind": "allocation",
        "routes": [],
        "proposals": [],
        "trajectory_note": "",
        "tokens_in": 0,
        "tokens_out": 0,
    }

    result = await synthesizer_node(state)
    assert result["disclaimer"] == get_disclaimer()


def _synthesizer_state(proposals: list[dict]) -> dict:
    return {
        "user_message": "What should I do about my 1099 taxes?",
        "conversation_id": None,
        "vault_snapshot": {},
        "wealth_position": {"step": 3, "step_name": "Roth IRA", "rationale": "", "next_move": ""},
        "income_position": {"step": 2, "step_name": "Core expenses", "rationale": "", "next_move": ""},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "financial_snapshot": None,
        "turn_kind": "income",
        "routes": [],
        "proposals": proposals,
        "trajectory_note": "",
        "tokens_in": 0,
        "tokens_out": 0,
    }


@pytest.mark.asyncio
async def test_disclaimer_forced_by_proposal_even_when_llm_omits_it(monkeypatch):
    """BLOCKER regression (assessment 2026-07-02): when a contributing proposal
    set requires_disclaimer=True, the disclaimer must attach even if the final
    Synthesizer LLM returns requires_disclaimer=false. CONTRACTS.md §2."""
    from agent.nodes.synthesizer import synthesizer_node

    tool_input = {
        "recommendation": "Set aside 30% of 1099 income for quarterly estimates.",
        "reasoning": "Self-employment tax plus federal bracket.",
        "principle": "pay_quarterly_estimates",
        "requires_disclaimer": False,  # LLM omits it — must NOT be trusted alone
        "vision_stamp": "Freedom 2045",
        "is_decision": False,
        "decision_summary": None,
    }
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    fake_response = MagicMock()
    fake_response.content = [tool_block]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("agent.nodes.synthesizer.get_anthropic", lambda: fake_client)

    tax_proposal = {
        "node": "tax_optimizer",
        "move": "Pay quarterly estimates",
        "principle": "pay_quarterly_estimates",
        "leverage_score": 0.8,
        "rationale": "Avoid underpayment penalty.",
        "requires_disclaimer": True,  # tax_optimizer always sets this
    }

    result = await synthesizer_node(_synthesizer_state([tax_proposal]))
    assert result["disclaimer"] == get_disclaimer()


@pytest.mark.asyncio
async def test_no_disclaimer_when_neither_llm_nor_proposals_require_it(monkeypatch):
    """The inverse: a general, non-tax/investment turn with no requiring proposal
    leaves disclaimer None (we do not spuriously stamp every response)."""
    from agent.nodes.synthesizer import synthesizer_node

    tool_input = {
        "recommendation": "Rename your emergency fund account so it feels off-limits.",
        "reasoning": "Behavioral friction reduces raids on the buffer.",
        "principle": "behavioral_guardrails",
        "requires_disclaimer": False,
        "vision_stamp": "Freedom 2045",
        "is_decision": False,
        "decision_summary": None,
    }
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.input = tool_input

    fake_response = MagicMock()
    fake_response.content = [tool_block]
    fake_response.usage = MagicMock(input_tokens=100, output_tokens=50)

    fake_client = MagicMock()
    fake_client.messages = MagicMock()
    fake_client.messages.create = AsyncMock(return_value=fake_response)
    monkeypatch.setattr("agent.nodes.synthesizer.get_anthropic", lambda: fake_client)

    general_proposal = {
        "node": "coach",
        "move": "Rename the account",
        "principle": "behavioral_guardrails",
        "leverage_score": 0.4,
        "rationale": "Friction helps.",
        "requires_disclaimer": False,
    }

    result = await synthesizer_node(_synthesizer_state([general_proposal]))
    assert result["disclaimer"] is None
