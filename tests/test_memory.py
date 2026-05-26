"""Decisions persistence + memory endpoint tests."""
from __future__ import annotations
from unittest.mock import AsyncMock, MagicMock, patch
import pytest


# --- Synthesizer correctly passes is_decision fields ---

@pytest.mark.asyncio
async def test_synthesizer_passes_is_decision_true():
    from agent.nodes.synthesizer import synthesizer_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "recommendation": "Max Roth IRA before saving for the house down payment.",
        "reasoning": "Tax arbitrage while your bracket is low.",
        "principle": "tax_arbitrage",
        "requires_disclaimer": True,
        "vision_stamp": "This keeps you on track for $500k net worth by 2036.",
        "is_decision": True,
        "decision_summary": "User will prioritize maxing Roth IRA before saving for a house.",
    }
    mock_usage = MagicMock()
    mock_usage.input_tokens = 100
    mock_usage.output_tokens = 60
    mock_usage.cache_read_input_tokens = 80
    mock_usage.cache_creation_input_tokens = 0

    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "I'm maxing Roth before saving for property.",
        "conversation_id": None,
        "wealth_position": {"step": 3, "step_name": "Tax-Advantaged", "rationale": "IRA not maxed", "next_move": "Max Roth"},
        "income_position": {"step": 1, "step_name": "Active Income", "rationale": "ok", "next_move": "maintain"},
        "vault_snapshot": {},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "proposals": [],
    }

    with patch("agent.nodes.synthesizer.get_anthropic", return_value=mock_client):
        result = await synthesizer_node(state)

    assert result["is_decision"] is True
    assert "Roth" in result["decision_summary"]


@pytest.mark.asyncio
async def test_synthesizer_is_decision_false_by_default():
    from agent.nodes.synthesizer import synthesizer_node

    mock_tool = MagicMock()
    mock_tool.type = "tool_use"
    mock_tool.input = {
        "recommendation": "Build 3 months emergency fund.",
        "reasoning": "No buffer means forced bad decisions.",
        "principle": "emergency_fund_first",
        "requires_disclaimer": False,
        "vision_stamp": "Step 1 of your sequence.",
        "is_decision": False,
        "decision_summary": "",
    }
    mock_usage = MagicMock()
    mock_usage.input_tokens = 80
    mock_usage.output_tokens = 40
    mock_usage.cache_read_input_tokens = 0
    mock_usage.cache_creation_input_tokens = 80

    mock_resp = MagicMock()
    mock_resp.content = [mock_tool]
    mock_resp.usage = mock_usage

    mock_client = AsyncMock()
    mock_client.messages.create = AsyncMock(return_value=mock_resp)

    state = {
        "user_message": "What should I do first?",
        "conversation_id": None,
        "wealth_position": {"step": 1, "step_name": "Emergency Fund", "rationale": "no cash", "next_move": "save"},
        "income_position": {"step": 1, "step_name": "Active Income", "rationale": "ok", "next_move": "maintain"},
        "vault_snapshot": {},
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "proposals": [],
    }

    with patch("agent.nodes.synthesizer.get_anthropic", return_value=mock_client):
        result = await synthesizer_node(state)

    assert result["is_decision"] is False
    assert result["decision_summary"] is None


# --- RESPONSE_TOOL schema includes is_decision ---

def test_response_tool_has_is_decision_field():
    from agent.prompts import RESPONSE_TOOL
    props = RESPONSE_TOOL["input_schema"]["properties"]
    assert "is_decision" in props
    assert "decision_summary" in props
    assert "is_decision" in RESPONSE_TOOL["input_schema"]["required"]
    assert "decision_summary" in RESPONSE_TOOL["input_schema"]["required"]


# --- Memory router endpoints (mocked DB) ---

@pytest.mark.asyncio
async def test_decisions_endpoint_returns_list():
    """GET /memory/decisions returns a list (may be empty)."""
    from httpx import AsyncClient, ASGITransport
    from unittest.mock import patch, AsyncMock, MagicMock
    from sqlalchemy.exc import OperationalError

    # Patch get_session to yield a mock that returns empty decisions
    mock_session = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.__aenter__ = AsyncMock(return_value=mock_session)
    mock_session.__aexit__ = AsyncMock(return_value=False)

    from main import app
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            # Register + get token
            await client.post("/auth/register", json={"username": "memuser", "password": "TestPass123!"})
            token_resp = await client.post(
                "/auth/token",
                data={"username": "memuser", "password": "TestPass123!"},
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            if token_resp.status_code != 200:
                pytest.skip("live DB required for auth round-trip")
            token = token_resp.json()["access_token"]

            with patch("routers.memory.get_session") as mock_gs:
                mock_gs.return_value.__aenter__ = AsyncMock(return_value=mock_session)
                mock_gs.return_value.__aexit__ = AsyncMock(return_value=False)
                resp = await client.get(
                    "/memory/decisions",
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert resp.status_code == 200
        assert isinstance(resp.json(), list)
    except OperationalError:
        pytest.skip("live DB required for auth round-trip")
