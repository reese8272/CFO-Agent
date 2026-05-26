"""Frozen AgentState contract (CONTRACTS.md §1, 2026-05-25).

Do not edit without amending CONTRACTS.md and docs/DECISIONS.md first.
"""
from __future__ import annotations
import operator
from typing import Annotated, Literal, NotRequired, TypedDict

AllocationStep = Literal[1, 2, 3, 4, 5, 6]
IncomeStep = Literal[1, 2, 3, 4, 5]
TurnKind = Literal["allocation", "income", "both", "general"]
PrincipleKey = str


class WealthPosition(TypedDict):
    step: int
    step_name: str
    rationale: str
    next_move: str


class IncomePosition(TypedDict):
    step: int
    step_name: str
    rationale: str
    next_move: str


class NodeProposal(TypedDict):
    node: str
    move: str
    principle: PrincipleKey
    leverage_score: float
    rationale: str
    requires_disclaimer: bool


class AgentState(TypedDict):
    # inputs — set by chat router before invoke
    user_message: str
    conversation_id: int | None

    # Retrieval node writes
    vault_snapshot: dict
    wealth_position: WealthPosition
    income_position: IncomePosition
    active_decisions: list[dict]
    recent_patterns: list[dict]
    memory_summary: str | None

    # Analyzer node writes (Issue 8)
    turn_kind: TurnKind
    routes: list[str]

    # conditional nodes append (parallel-safe via reducer)
    proposals: Annotated[list[NodeProposal], operator.add]

    # Tracker node writes (Issue 10)
    trajectory_note: str
    net_worth_pace: NotRequired[dict]

    # Synthesizer terminal output
    recommendation: str
    reasoning: str
    principle: PrincipleKey
    disclaimer: str | None
    vision_stamp: str

    # decision side-output (set by Synthesizer when user states intent)
    is_decision: bool
    decision_summary: str | None

    # token accounting
    tokens_in: int
    tokens_out: int
