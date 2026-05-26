"""Strategist node — allocation-side wealth-vehicle prioritization.

Reads wealth_position + active_decisions from state. Emits one NodeProposal
pointing at the highest-leverage allocation move.
"""
from __future__ import annotations
import logging
import time

from clients import get_anthropic
from agent.state import AgentState, NodeProposal
from agent.principles import get_principle, PRINCIPLES

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

_SYSTEM = """You are the Strategist node of a personal CFO agent.

Your job: given the user's wealth position on the 6-step allocation ladder,
identify the single highest-leverage allocation move and score it.

Allocation steps:
1 Emergency Fund (3–6 months expenses in cash)
2 Eliminate high-interest debt (>7% APR)
3 Tax-advantaged accounts (Roth IRA + HSA)
4 Market exposure (taxable brokerage / index funds)
5 Real estate leverage
6 Business income that doesn't require your time

Be specific. Name the account type, the amount if known, the timeframe.
Commit to one move. No hedging, no menus.
"""

_TOOL = {
    "name": "propose_allocation_move",
    "description": "Propose the single highest-leverage allocation move.",
    "input_schema": {
        "type": "object",
        "properties": {
            "move": {"type": "string", "description": "Imperative, specific allocation action."},
            "principle": {
                "type": "string",
                "enum": list(PRINCIPLES.keys()),
                "description": "The single principle key this move cites.",
            },
            "leverage_score": {
                "type": "number",
                "description": "0.0–1.0. How much this move advances the allocation track.",
            },
            "rationale": {"type": "string", "description": "2 sentences max."},
            "requires_disclaimer": {"type": "boolean"},
        },
        "required": ["move", "principle", "leverage_score", "rationale", "requires_disclaimer"],
    },
}


async def strategist_node(state: AgentState) -> dict:
    client = get_anthropic()
    wp = state.get("wealth_position", {})
    decisions = state.get("active_decisions", [])

    context = (
        f"Current allocation step: {wp.get('step', '?')} — {wp.get('step_name', '?')}\n"
        f"Rationale: {wp.get('rationale', '')}\n"
        f"Next move from ladder: {wp.get('next_move', '')}\n"
        f"Active decisions: {decisions}\n"
        f"User question: {state['user_message']}"
    )

    t0 = time.monotonic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "propose_allocation_move"},
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    tool_block = next(b for b in response.content if b.type == "tool_use")
    r = tool_block.input

    proposal = NodeProposal(
        node="strategist",
        move=r["move"],
        principle=r["principle"],
        leverage_score=float(r["leverage_score"]),
        rationale=r["rationale"],
        requires_disclaimer=bool(r["requires_disclaimer"]),
    )
    logger.info(
        "strategist: principle=%s score=%.2f tokens_in=%d tokens_out=%d latency_ms=%d",
        r["principle"],
        r["leverage_score"],
        response.usage.input_tokens,
        response.usage.output_tokens,
        latency_ms,
    )
    return {"proposals": [proposal]}
