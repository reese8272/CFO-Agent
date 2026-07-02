"""LangGraph graph — full topology.

Retrieval → Analyzer → [Strategist|Career|Income-Optimizer|Tax-Optimizer] → Coach
  → Tracker → Alert → Synthesizer → Persist.

Issue 8 inserts Analyzer + conditional nodes. Issue 8b adds Career/Income-Optimizer/Tax-Optimizer.
Issue 10 adds Tracker + Alert between Coach and Synthesizer.
"""
from __future__ import annotations
import logging

from langgraph.graph import StateGraph, END

from agent.state import AgentState
from agent.nodes.synthesizer import synthesizer_node
from agent.nodes.analyzer import analyzer_node
from agent.nodes.strategist import strategist_node
from agent.nodes.coach import coach_node
from agent.nodes.career import career_node
from agent.nodes.income_optimizer import income_optimizer_node
from agent.nodes.tax_optimizer import tax_optimizer_node
from agent.nodes.tracker import tracker_node
from agent.nodes.alert import alert_node
from db import get_sessionmaker
from memory.retrieval import build_retrieval_context

logger = logging.getLogger(__name__)


async def retrieval_node(state: AgentState) -> dict:
    """Pull vault + position + decisions + patterns into state."""
    async with get_sessionmaker()() as session:
        ctx = await build_retrieval_context(session, user_id="owner")
    return ctx


async def persist_node(state: AgentState) -> dict:
    """Write conversation + message rows; return (possibly new) conversation_id."""
    from memory.models import Conversation, Message

    async with get_sessionmaker()() as session:
        # get or create conversation
        conv_id = state.get("conversation_id")
        if conv_id is None:
            conv = Conversation()
            session.add(conv)
            await session.flush()
            conv_id = conv.id

        # user turn
        user_msg = Message(
            conversation_id=conv_id,
            role="user",
            content=state["user_message"],
        )
        session.add(user_msg)

        # agent turn
        agent_content = state.get("recommendation", "")
        agent_msg = Message(
            conversation_id=conv_id,
            role="agent",
            content=agent_content,
            tokens_in=state.get("tokens_in"),
            tokens_out=state.get("tokens_out"),
            cited_principle=state.get("principle"),
        )
        session.add(agent_msg)

        # persist decision if Synthesizer flagged one
        if state.get("is_decision") and state.get("decision_summary"):
            from memory.models import Decision
            decision = Decision(
                summary=state["decision_summary"],
                principle=state.get("principle"),
                status="active",
            )
            session.add(decision)

        await session.commit()

    return {"conversation_id": conv_id}


_ROUTE_TO_NODE = {
    "allocation": "strategist",
    "career": "career",
    "income": "income_optimizer",
    "tax": "tax_optimizer",
}


def _route_from_analyzer(state: AgentState) -> list[str]:
    """Return every specialist node to fan out to after Analyzer.

    Returning a list makes LangGraph run all routed specialists in parallel (a
    multi-topic "both" turn now runs Strategist AND Income-Optimizer, etc.) —
    each appends its own proposal via the reducer before converging on Coach.
    Falls back to Coach-only when no specialist matched.
    """
    routes = state.get("routes", [])
    selected = [_ROUTE_TO_NODE[r] for r in routes if r in _ROUTE_TO_NODE]
    selected = list(dict.fromkeys(selected))  # de-dupe, preserve order
    return selected or ["coach"]


def build_graph() -> object:
    """Compile and return the LangGraph runnable."""
    g = StateGraph(AgentState)

    g.add_node("retrieval", retrieval_node)
    g.add_node("analyzer", analyzer_node)
    g.add_node("strategist", strategist_node)
    g.add_node("career", career_node)
    g.add_node("income_optimizer", income_optimizer_node)
    g.add_node("tax_optimizer", tax_optimizer_node)
    g.add_node("coach", coach_node)
    g.add_node("tracker", tracker_node)
    g.add_node("alert", alert_node)
    g.add_node("synthesizer", synthesizer_node)
    g.add_node("persist", persist_node)

    g.set_entry_point("retrieval")
    g.add_edge("retrieval", "analyzer")

    # Conditional routing: Analyzer → specialist → Coach
    g.add_conditional_edges(
        "analyzer",
        _route_from_analyzer,
        {
            "strategist": "strategist",
            "career": "career",
            "income_optimizer": "income_optimizer",
            "tax_optimizer": "tax_optimizer",
            "coach": "coach",
        },
    )
    g.add_edge("strategist", "coach")
    g.add_edge("career", "coach")
    g.add_edge("income_optimizer", "coach")
    g.add_edge("tax_optimizer", "coach")
    g.add_edge("coach", "tracker")
    g.add_edge("tracker", "alert")
    g.add_edge("alert", "synthesizer")
    g.add_edge("synthesizer", "persist")
    g.add_edge("persist", END)

    compiled = g.compile()
    return compiled


# Module-level compiled graph — built once at import time
_graph = None


def get_graph():
    global _graph
    if _graph is None:
        _graph = build_graph()
        logger.info("langgraph compiled")
    return _graph
