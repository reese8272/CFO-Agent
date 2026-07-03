"""Career node — comp benchmarks, switch timing, raise/promotion prep, negotiation milestones.

Fires when Analyzer detects a career-related turn.
"""
from __future__ import annotations
from config import get_settings

from agent.state import AgentState
from agent.nodes._llm import run_proposal_node

MODEL = get_settings().anthropic_model_smart
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
    ip = state.get("income_position", {})
    snapshot = state.get("vault_snapshot", {})

    context = (
        f"Income step: {ip.get('step', '?')} — {ip.get('step_name', '?')}\n"
        f"Rationale: {ip.get('rationale', '')}\n"
        f"Career data from vault: {snapshot.get('career', {})}\n"
        f"User question: {state['user_message']}"
    )
    return await run_proposal_node(
        node="career",
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=_SYSTEM,
        tool=_TOOL,
        context=context,
    )
