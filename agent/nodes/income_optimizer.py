"""Income-Optimizer node — ranks income streams by net hourly, emits cut-or-scale recommendation.

Pure logic: no LLM call. net_hourly = (gross - expenses) / hours_worked.
Fires when Analyzer detects an income-optimization turn.
"""
from __future__ import annotations
import logging
from decimal import Decimal
from agent.state import AgentState, NodeProposal

logger = logging.getLogger(__name__)

_BOTTOM_THRESHOLD = Decimal("0.30")  # cut stream if >30% below top net hourly


def income_optimizer_node(state: AgentState) -> dict:
    snapshot = state.get("vault_snapshot", {})
    streams = snapshot.get("income_streams", [])

    if not streams:
        return {"proposals": [NodeProposal(
            node="income_optimizer",
            move="Log at least one income stream's net hourly to enable stream ranking.",
            principle="side_income_hourly_truth",
            leverage_score=0.5,
            rationale="No income stream data available yet — net hourly truth requires recorded gross, expenses, and hours.",
            requires_disclaimer=False,
        )]}

    # rank by net_hourly descending
    ranked = sorted(streams, key=lambda s: Decimal(str(s.get("net_hourly", 0))), reverse=True)
    top = ranked[0]
    bottom = ranked[-1]

    top_hourly = Decimal(str(top.get("net_hourly", 0)))
    bottom_hourly = Decimal(str(bottom.get("net_hourly", 0)))

    if top_hourly > 0 and len(ranked) > 1:
        gap_pct = (top_hourly - bottom_hourly) / top_hourly
        if gap_pct > _BOTTOM_THRESHOLD:
            move = (
                f"Cut or scale down '{bottom.get('source', 'bottom stream')}' "
                f"(net ${bottom_hourly:.2f}/hr) — it's {gap_pct*100:.0f}% below "
                f"'{top.get('source', 'top stream')}' (net ${top_hourly:.2f}/hr). "
                f"Redirect that time toward the higher-margin stream."
            )
            score = float(min(gap_pct, Decimal("1.0")))
        else:
            move = (
                f"Streams are within range. Top: '{top.get('source', '?')}' at ${top_hourly:.2f}/hr. "
                f"Focus on scaling '{top.get('source', 'top stream')}' before cutting anything."
            )
            score = 0.4
    else:
        move = f"Only one stream recorded. Log expenses and hours to get a true net hourly for '{top.get('source', '?')}'."
        score = 0.3

    proposal = NodeProposal(
        node="income_optimizer",
        move=move,
        principle="side_income_hourly_truth",
        leverage_score=score,
        rationale="Net hourly truth: rank streams by (gross − expenses) / hours and cut the bottom when >30% below the top.",
        requires_disclaimer=False,
    )
    logger.info("income_optimizer: score=%.2f streams=%d", score, len(streams))
    return {"proposals": [proposal]}
