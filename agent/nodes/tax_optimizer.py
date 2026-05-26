"""Tax-Optimizer node — surfaces missed 1099 deductions and quarterly tax estimates.

Uses year-versioned constants from agent/principles.py.
Disclaimer mandatory on all output (requires_disclaimer=True always).
"""
from __future__ import annotations
import logging
from decimal import Decimal
from clients import get_anthropic
from agent.state import AgentState, NodeProposal
from agent.principles import (
    MILEAGE_RATE_2026, SE_TAX_RATE, TAX_YEAR,
    ROTH_IRA_LIMIT_2026, SOLO_401K_TOTAL_LIMIT_2026,
)

logger = logging.getLogger(__name__)

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 512

_DEDUCTION_CATEGORIES = ["mileage", "home_office", "equipment", "education", "other"]

_SYSTEM = f"""You are the Tax-Optimizer node of a personal CFO agent.

Year: {TAX_YEAR}
Self-employment tax rate: {SE_TAX_RATE*100:.1f}% (SS + Medicare)
Standard mileage rate: ${MILEAGE_RATE_2026}/mile
Solo 401k total limit: ${SOLO_401K_TOTAL_LIMIT_2026:,}

Your job: given the user's 1099 income and recorded deductions, surface:
1. Missing deduction categories (which of mileage/home_office/equipment/education are empty)
2. Quarterly estimated tax due (rough: 1099_ytd × (income_tax_rate + {SE_TAX_RATE*100:.1f}%) ÷ 4)
3. The single highest-leverage tax optimization for this user

Always set requires_disclaimer=True. Always say "for {TAX_YEAR}..." when citing any number.
Be specific and actionable. Not preachy.
"""

_TOOL = {
    "name": "propose_tax_move",
    "description": "Propose the single highest-leverage tax optimization.",
    "input_schema": {
        "type": "object",
        "properties": {
            "move": {"type": "string", "description": "Specific, actionable tax move."},
            "principle": {
                "type": "string",
                "enum": ["deduction_discipline_1099", "quarterly_estimated_tax", "solo_401k_for_1099", "tax_arbitrage"],
            },
            "leverage_score": {"type": "number"},
            "rationale": {"type": "string"},
            "requires_disclaimer": {"type": "boolean", "enum": [True]},
        },
        "required": ["move", "principle", "leverage_score", "rationale", "requires_disclaimer"],
    },
}


async def tax_optimizer_node(state: AgentState) -> dict:
    client = get_anthropic()
    snapshot = state.get("vault_snapshot", {})
    deductions = snapshot.get("tax_deductions", [])
    income_1099_ytd = Decimal(str(snapshot.get("income_1099_ytd", 0)))

    recorded_categories = {d.get("category") for d in deductions if d.get("category")}
    missing = [c for c in _DEDUCTION_CATEGORIES if c not in recorded_categories]

    estimated_quarterly = (income_1099_ytd * Decimal(str(SE_TAX_RATE + 0.22))) / 4

    context = (
        f"User question: {state['user_message']}\n\n"
        f"For tax year {TAX_YEAR}:\n"
        f"1099 income YTD: ${income_1099_ytd:,.2f}\n"
        f"Recorded deduction categories: {list(recorded_categories) or 'none'}\n"
        f"Missing categories: {missing}\n"
        f"Estimated quarterly payment (rough): ${estimated_quarterly:,.2f}\n"
        f"Mileage rate: ${MILEAGE_RATE_2026}/mile\n"
        f"SE tax rate: {SE_TAX_RATE*100:.1f}%"
    )

    response = await client.messages.create(
        model=MODEL,
        max_tokens=MAX_TOKENS,
        system=[{"type": "text", "text": _SYSTEM, "cache_control": {"type": "ephemeral"}}],
        messages=[{"role": "user", "content": context}],
        tools=[_TOOL],
        tool_choice={"type": "tool", "name": "propose_tax_move"},
        extra_headers={"anthropic-beta": "prompt-caching-2024-07-31"},
    )
    tool_block = next(b for b in response.content if b.type == "tool_use")
    r = tool_block.input

    proposal = NodeProposal(
        node="tax_optimizer",
        move=r["move"],
        principle=r["principle"],
        leverage_score=float(r["leverage_score"]),
        rationale=r["rationale"],
        requires_disclaimer=True,  # always True for tax output
    )
    logger.info("tax_optimizer: principle=%s score=%.2f", r["principle"], r["leverage_score"])
    return {"proposals": [proposal]}
