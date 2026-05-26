"""Chat endpoint unit tests — Anthropic call mocked at client level."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from agent.prompts import CFO_SYSTEM_PROMPT, RESPONSE_TOOL, PRINCIPLE_KEYS


# --- Pure unit tests (no I/O) ---

def test_cfo_system_prompt_contains_disclaimer():
    assert "licensed financial advisor" in CFO_SYSTEM_PROMPT


def test_cfo_system_prompt_contains_all_principle_keys():
    for key in PRINCIPLE_KEYS:
        assert key in CFO_SYSTEM_PROMPT, f"missing principle key: {key}"


def test_response_tool_schema_has_required_fields():
    props = RESPONSE_TOOL["input_schema"]["properties"]
    assert "recommendation" in props
    assert "reasoning" in props
    assert "principle" in props
    assert "requires_disclaimer" in props
    assert "vision_stamp" in props


def test_response_tool_principle_enum_matches_registry():
    enum_vals = RESPONSE_TOOL["input_schema"]["properties"]["principle"]["enum"]
    assert set(enum_vals) == set(PRINCIPLE_KEYS)


# --- Synthesizer unit test with mocked Anthropic client ---

@pytest.mark.asyncio
async def test_synthesizer_sets_disclaimer_when_required():
    """When requires_disclaimer=True in tool output, disclaimer field is non-null."""
    from agent.nodes.synthesizer import synthesizer_node

    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.input = {
        "recommendation": "Max your Roth IRA this year.",
        "reasoning": "Tax arbitrage wins in your bracket.",
        "principle": "tax_arbitrage",
        "requires_disclaimer": True,
        "vision_stamp": "This advances your 10-year goal of $500k net worth.",
    }

    mock_usage = MagicMock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 50
    mock_usage.cache_read_input_tokens = 80
    mock_usage.cache_creation_input_tokens = 0

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    state = {
        "user_message": "Should I max my Roth?",
        "conversation_id": None,
        "wealth_position": {"step": 4, "step_name": "Tax-Advantaged", "rationale": "IRA not maxed", "next_move": "Max Roth IRA"},
        "income_position": {"step": 1, "step_name": "Active Income", "rationale": "Covers expenses", "next_move": "Maintain"},
        "vault_snapshot": {},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
    }

    with patch("agent.nodes.synthesizer.get_anthropic", return_value=mock_client):
        result = await synthesizer_node(state)

    assert result["recommendation"] == "Max your Roth IRA this year."
    assert result["disclaimer"] is not None
    assert "licensed financial advisor" in result["disclaimer"]
    assert result["principle"] == "tax_arbitrage"


@pytest.mark.asyncio
async def test_synthesizer_no_disclaimer_when_not_required():
    from agent.nodes.synthesizer import synthesizer_node

    mock_tool_block = MagicMock()
    mock_tool_block.type = "tool_use"
    mock_tool_block.input = {
        "recommendation": "Build your emergency fund to $9,000.",
        "reasoning": "You have no emergency fund yet.",
        "principle": "emergency_fund_first",
        "requires_disclaimer": False,
        "vision_stamp": "This is step 1 of your wealth-building sequence.",
    }

    mock_usage = MagicMock()
    mock_usage.input_tokens = 90
    mock_usage.output_tokens = 40
    mock_usage.cache_read_input_tokens = 0
    mock_usage.cache_creation_input_tokens = 90

    mock_response = MagicMock()
    mock_response.content = [mock_tool_block]
    mock_response.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_response)

    state = {
        "user_message": "What should I do first?",
        "conversation_id": None,
        "wealth_position": {"step": 1, "step_name": "Emergency Fund", "rationale": "No cash buffer", "next_move": "Save 3 months expenses"},
        "income_position": {"step": 1, "step_name": "Active Income", "rationale": "ok", "next_move": "maintain"},
        "vault_snapshot": {},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
    }

    with patch("agent.nodes.synthesizer.get_anthropic", return_value=mock_client):
        result = await synthesizer_node(state)

    assert result["disclaimer"] is None
    assert result["tokens_in"] == 90
