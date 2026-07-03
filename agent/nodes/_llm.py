"""Shared driver for the single-proposal specialist nodes.

Strategist / Career / Tax-Optimizer are structurally identical: build a context
string, call Anthropic with a forced structured tool, turn the tool result into
one `NodeProposal`. This helper centralizes that so the truncation guard and the
token accounting live in exactly one place (assessment 2026-07-03).
"""
from __future__ import annotations

import logging
import time

from clients import get_anthropic
from agent.state import NodeProposal

logger = logging.getLogger(__name__)


async def run_proposal_node(
    *,
    node: str,
    model: str,
    max_tokens: int,
    system: str,
    tool: dict,
    context: str,
    force_disclaimer: bool = False,
) -> dict:
    """Run one specialist LLM turn and return its proposal + token usage.

    Returns ``{"proposals": [...], "tokens_in": n, "tokens_out": m}``. On a
    ``max_tokens`` truncation (no complete ``tool_use`` block) it logs a warning
    and returns an EMPTY proposals list rather than raising ``StopIteration`` —
    the turn continues with the other specialists' proposals instead of 500-ing.
    Token usage is always returned so per-turn cost stays accurate even on the
    truncated path.
    """
    client = get_anthropic()
    t0 = time.monotonic()
    response = await client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=[{"type": "text", "text": system, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[tool],
        tool_choice={"type": "tool", "name": tool["name"]},
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    tokens_in = response.usage.input_tokens
    tokens_out = response.usage.output_tokens

    tool_block = next((b for b in response.content if b.type == "tool_use"), None)
    if tool_block is None:
        logger.warning(
            "%s: no tool_use block (stop_reason=%s) — skipping this specialist's "
            "proposal this turn",
            node,
            getattr(response, "stop_reason", "?"),
        )
        return {"proposals": [], "tokens_in": tokens_in, "tokens_out": tokens_out}

    r = tool_block.input
    proposal = NodeProposal(
        node=node,
        move=r["move"],
        principle=r["principle"],
        leverage_score=max(0.0, min(1.0, float(r["leverage_score"]))),
        rationale=r["rationale"],
        requires_disclaimer=True if force_disclaimer else bool(r["requires_disclaimer"]),
    )
    logger.info(
        "%s: principle=%s score=%.2f tokens_in=%d tokens_out=%d latency_ms=%d",
        node,
        r["principle"],
        r["leverage_score"],
        tokens_in,
        tokens_out,
        latency_ms,
    )
    return {"proposals": [proposal], "tokens_in": tokens_in, "tokens_out": tokens_out}
