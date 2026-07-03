"""Strategist node — allocation-side wealth-vehicle prioritization.

Reads wealth_position + active_decisions from state. Emits one NodeProposal
pointing at the highest-leverage allocation move.
"""
from __future__ import annotations
from config import get_settings

from agent.state import AgentState
from agent.nodes._llm import run_proposal_node
from agent.principles import PRINCIPLES

MODEL = get_settings().anthropic_model_smart
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
    wp = state.get("wealth_position", {})
    decisions = state.get("active_decisions", [])

    context = (
        f"Current allocation step: {wp.get('step', '?')} — {wp.get('step_name', '?')}\n"
        f"Rationale: {wp.get('rationale', '')}\n"
        f"Next move from ladder: {wp.get('next_move', '')}\n"
        f"Active decisions: {decisions}\n"
        f"User question: {state['user_message']}"
    )
    return await run_proposal_node(
        node="strategist",
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        tool=_TOOL,
        context=context,
    )
