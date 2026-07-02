"""Analyzer node — classifies the user turn and sets routing.

Fires first after Retrieval. Determines which specialist nodes should run.
"""
from __future__ import annotations
from config import get_settings
import logging
import time

from clients import get_anthropic
from agent.state import AgentState

logger = logging.getLogger(__name__)

MODEL = get_settings().anthropic_model_fast  # fastest/cheapest — classification only
MAX_TOKENS = 256

_SYSTEM = """You are a turn classifier for a personal CFO assistant.

Given the user's message, return:
- turn_kind: one of "allocation", "income", "both", "general"
- routes: a list of specialist nodes that should respond. Choose from:
    "allocation"   — wealth allocation question (which step, emergency fund, debt, retirement, brokerage)
    "income"       — income stream optimization (side income, net hourly, cut/scale)
    "career"       — career comp, job switch, raise, negotiation, promotion
    "tax"          — 1099 deductions, quarterly estimated tax, tax strategy
    "real_estate"  — real estate investing question
    "saas"         — SaaS / indie business question
    "investing"    — portfolio, index funds, asset allocation, TLH

Rules:
- routes must be a non-empty list
- A general question like "what should I do next?" routes to both "allocation" and "income"
- A specific "where does my surplus go?" is "allocation"
- A question about a side gig is "income"
- Multiple topics → multiple routes
"""

_CLASSIFY_TOOL = {
    "name": "classify_turn",
    "description": "Classify the user turn and determine routing.",
    "input_schema": {
        "type": "object",
        "properties": {
            "turn_kind": {
                "type": "string",
                "enum": ["allocation", "income", "both", "general"],
            },
            "routes": {
                "type": "array",
                "items": {
                    "type": "string",
                    "enum": ["allocation", "income", "career", "tax", "real_estate", "saas", "investing"],
                },
                "minItems": 1,
            },
        },
        "required": ["turn_kind", "routes"],
    },
}


async def analyzer_node(state: AgentState) -> dict:
    client = get_anthropic()
    t0 = time.monotonic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": state["user_message"]}],
        tools=[_CLASSIFY_TOOL],
        tool_choice={"type": "tool", "name": "classify_turn"},
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    tool_block = next(b for b in response.content if b.type == "tool_use")
    result = tool_block.input
    logger.info(
        "analyzer: turn_kind=%s routes=%s tokens_in=%d tokens_out=%d latency_ms=%d",
        result["turn_kind"],
        result["routes"],
        response.usage.input_tokens,
        response.usage.output_tokens,
        latency_ms,
    )
    return {"turn_kind": result["turn_kind"], "routes": result["routes"]}
