"""Synthesizer node — Issue 7 minimal version.

Makes one Anthropic call with the user profile cached, returns the committed
recommendation via tool use. Extended in Issue 8 when proposals from
Analyzer/Strategist/Coach are available.
"""
from __future__ import annotations
from config import get_settings
import logging
import time

from clients import get_anthropic
from disclaimer import get_disclaimer
from agent.state import AgentState
from agent.prompts import CFO_SYSTEM_PROMPT, RESPONSE_TOOL
from memory.retrieval import build_profile_block

logger = logging.getLogger(__name__)

MODEL = get_settings().anthropic_model_smart
MAX_TOKENS = 1024


async def synthesizer_node(state: AgentState) -> dict:
    """Call Anthropic with cached user profile; return terminal fields."""
    client = get_anthropic()
    profile_block = build_profile_block(state)

    # If proposals are present, build a proposals context block
    proposals_text = ""
    if proposals := state.get("proposals", []):
        proposals_text = "\n\n### Specialist Proposals\n" + "\n".join(
            f"[{p['node']} | score={p['leverage_score']:.2f} | principle={p['principle']}]\n"
            f"Move: {p['move']}\nRationale: {p['rationale']}"
            for p in sorted(proposals, key=lambda x: -x["leverage_score"])
        )

    user_content = state["user_message"]
    if proposals_text:
        user_content = (
            f"{user_content}\n\n"
            f"The following specialist nodes have proposed moves. "
            f"Pick the highest-leverage one and render it in your voice:\n{proposals_text}"
        )

    t0 = time.monotonic()
    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": CFO_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            },
            {
                "type": "text",
                "text": profile_block,
                "cache_control": {"type": "ephemeral"},
            },
        ],
        messages=[{"role": "user", "content": user_content}],
        tools=[RESPONSE_TOOL],
        tool_choice={"type": "tool", "name": "produce_response"},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)

    # extract tool call result
    tool_block = next(b for b in response.content if b.type == "tool_use")
    result = tool_block.input

    cache_read = getattr(response.usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(response.usage, "cache_creation_input_tokens", 0) or 0
    logger.info(
        "synthesizer: tokens_in=%d tokens_out=%d cache_read=%d cache_write=%d latency_ms=%d",
        response.usage.input_tokens,
        response.usage.output_tokens,
        cache_read,
        cache_write,
        latency_ms,
    )

    # The disclaimer is mandatory whenever ANY contributing proposal set
    # requires_disclaimer (CONTRACTS.md §2) — never trust the final LLM's flag
    # alone, or a tax/investment recommendation can ship without it.
    needs_disclaimer = bool(result.get("requires_disclaimer")) or any(
        p.get("requires_disclaimer") for p in state.get("proposals", [])
    )
    disclaimer = get_disclaimer() if needs_disclaimer else None

    return {
        "recommendation": result["recommendation"],
        "reasoning": result["reasoning"],
        "principle": result["principle"],
        "disclaimer": disclaimer,
        "vision_stamp": result["vision_stamp"],
        "is_decision": bool(result.get("is_decision", False)),
        "decision_summary": result.get("decision_summary") or None,
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
    }
