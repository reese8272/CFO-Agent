"""Coach node — enriches proposals with principle citations and arena context.

Fires always after the conditional specialist nodes (Strategist, Career, etc.).
Loads arena-specific principle library based on detected routes.
"""
from __future__ import annotations
from config import get_settings
import logging
import time

from clients import get_anthropic
from agent.state import AgentState, NodeProposal
from agent.principles import PRINCIPLES

logger = logging.getLogger(__name__)

MODEL = get_settings().anthropic_model_smart
MAX_TOKENS = 512

_SYSTEM = """You are the Coach node of a personal CFO agent.

Your role: take the proposals from specialist nodes, enrich each with:
1. The principle citation (one sentence, direct, no moralizing)
2. A "why now" context specific to this user's position
3. Confirm or adjust the leverage_score if your assessment differs

Then propose your own Coach insight if the proposals miss something important.
Cite exactly one principle per proposal. Speak in the Coach Voice:
direct, encouraging, names the long game, not preachy.
"""

_TOOL = {
    "name": "coach_output",
    "description": "Enriched proposals with principle citations.",
    "input_schema": {
        "type": "object",
        "properties": {
            "enriched_proposals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "node": {"type": "string"},
                        "move": {"type": "string"},
                        "principle": {"type": "string"},
                        "leverage_score": {"type": "number"},
                        "rationale": {"type": "string"},
                        "requires_disclaimer": {"type": "boolean"},
                        "principle_cite": {
                            "type": "string",
                            "description": "The cite sentence from the principle registry.",
                        },
                    },
                    "required": [
                        "node",
                        "move",
                        "principle",
                        "leverage_score",
                        "rationale",
                        "requires_disclaimer",
                        "principle_cite",
                    ],
                },
            },
        },
        "required": ["enriched_proposals"],
    },
}


def _load_arena_context(routes: list[str]) -> str:
    parts = []
    if "real_estate" in routes:
        from agent.principles_real_estate import ARENA_PRINCIPLES
        parts.append("Real estate principles:\n" + "\n".join(f"- {v}" for v in ARENA_PRINCIPLES.values()))
    if "saas" in routes:
        from agent.principles_saas import ARENA_PRINCIPLES
        parts.append("SaaS/business principles:\n" + "\n".join(f"- {v}" for v in ARENA_PRINCIPLES.values()))
    if "investing" in routes:
        from agent.principles_investing import ARENA_PRINCIPLES
        parts.append("Investing principles:\n" + "\n".join(f"- {v}" for v in ARENA_PRINCIPLES.values()))
    return "\n\n".join(parts)


async def coach_node(state: AgentState) -> dict:
    client = get_anthropic()
    proposals = state.get("proposals", [])
    routes = state.get("routes", [])
    arena_ctx = _load_arena_context(routes)

    proposals_text = "\n".join(
        f"- [{p['node']}] {p['move']} (principle: {p['principle']}, score: {p['leverage_score']:.2f})"
        for p in proposals
    ) or "(no specialist proposals yet — Coach should propose directly)"

    context = (
        f"User question: {state['user_message']}\n\n"
        f"Current proposals:\n{proposals_text}\n\n"
        f"Principle registry excerpt:\n"
        + "\n".join(f"- {k}: {v['cite']}" for k, v in PRINCIPLES.items())
        + (f"\n\nArena context:\n{arena_ctx}" if arena_ctx else "")
    )

    t0 = time.monotonic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "coach_output"},
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    tool_block = next(b for b in response.content if b.type == "tool_use")
    enriched = tool_block.input["enriched_proposals"]

    new_proposals = [
        NodeProposal(
            node=p["node"],
            move=p["move"],
            principle=p["principle"],
            leverage_score=float(p["leverage_score"]),
            rationale=p.get("principle_cite", p["rationale"]),
            requires_disclaimer=bool(p["requires_disclaimer"]),
        )
        for p in enriched
    ]
    logger.info(
        "coach: enriched %d proposals tokens_in=%d tokens_out=%d latency_ms=%d",
        len(new_proposals),
        response.usage.input_tokens,
        response.usage.output_tokens,
        latency_ms,
    )
    # Return enriched proposals — replace existing ones (Coach is the authority on final cite)
    return {"proposals": new_proposals}
