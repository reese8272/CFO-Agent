"""Career node — comp benchmarks, switch timing, raise/promotion prep, negotiation milestones.

Fires when Analyzer detects a career-related turn.
"""
from __future__ import annotations
import logging
import time
from clients import get_anthropic
from agent.state import AgentState, NodeProposal

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

_SYSTEM = """You are the Career node of a personal CFO agent.

Your job: given the user's income position and career data, identify the single
highest-leverage career move and score it.

Career levers (in order of typical leverage):
1. Job switch if comp delta > 7% above internal raise trajectory (job_switch_comp_arbitrage)
2. Comp negotiation — anchor high, ask in writing, track milestones (comp_negotiation_anchor_high)
3. Career income as wealth lever — $20k bump invested 30yr > most portfolio opts (career_income_as_wealth_lever)

Be specific. Name the target role, the comp delta if computable, the timeframe.
Commit to ONE move. No hedging.
"""

_TOOL = {
    "name": "propose_career_move",
    "description": "Propose the single highest-leverage career move.",
    "input_schema": {
        "type": "object",
        "properties": {
            "move": {"type": "string", "description": "Imperative, specific career action."},
            "principle": {
                "type": "string",
                "enum": ["job_switch_comp_arbitrage", "comp_negotiation_anchor_high", "career_income_as_wealth_lever"],
            },
            "leverage_score": {"type": "number", "description": "0.0–1.0"},
            "rationale": {"type": "string", "description": "2 sentences max."},
            "requires_disclaimer": {"type": "boolean"},
        },
        "required": ["move", "principle", "leverage_score", "rationale", "requires_disclaimer"],
    },
}


async def career_node(state: AgentState) -> dict:
    client = get_anthropic()
    ip = state.get("income_position", {})
    snapshot = state.get("vault_snapshot", {})

    context = (
        f"Income step: {ip.get('step', '?')} — {ip.get('step_name', '?')}\n"
        f"Rationale: {ip.get('rationale', '')}\n"
        f"Career data from vault: {snapshot.get('career', {})}\n"
        f"User question: {state['user_message']}"
    )

    t0 = time.monotonic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "propose_career_move"},
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    tool_block = next(b for b in response.content if b.type == "tool_use")
    r = tool_block.input

    proposal = NodeProposal(
        node="career",
        move=r["move"],
        principle=r["principle"],
        leverage_score=float(r["leverage_score"]),
        rationale=r["rationale"],
        requires_disclaimer=bool(r["requires_disclaimer"]),
    )
    logger.info(
        "career: principle=%s score=%.2f tokens_in=%d tokens_out=%d latency_ms=%d",
        r["principle"], r["leverage_score"],
        response.usage.input_tokens, response.usage.output_tokens, latency_ms,
    )
    return {"proposals": [proposal]}
