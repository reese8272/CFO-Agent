"""POST /chat endpoint — CONTRACTS.md §5 shape."""
from __future__ import annotations
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import User, get_current_user
from agent.graph import get_graph
from rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])
CurrentUser = Annotated[User, Depends(get_current_user)]


class ChatRequest(BaseModel):
    message: str
    conversation_id: int | None = None


class ChatResponse(BaseModel):
    recommendation: str
    reasoning: str
    principle: str
    disclaimer: str | None
    vision_stamp: str
    conversation_id: int


@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat(request: Request, body: ChatRequest, _user: CurrentUser):
    graph = get_graph()
    initial_state = {
        "user_message": body.message,
        "conversation_id": body.conversation_id,
        "proposals": [],
        "routes": [],
        "turn_kind": "general",
        "trajectory_note": "",
        "tokens_in": 0,
        "tokens_out": 0,
        "active_decisions": [],
        "recent_patterns": [],
        "memory_summary": None,
        "vault_snapshot": {},
        "financial_snapshot": None,
        "wealth_position": {},
        "income_position": {},
    }
    config = {"configurable": {"thread_id": str(body.conversation_id or "new")}}
    try:
        result = await graph.ainvoke(initial_state, config=config)
    except Exception as exc:
        logger.exception("graph invocation failed")
        raise HTTPException(status_code=500, detail="Agent error") from exc

    return ChatResponse(
        recommendation=result["recommendation"],
        reasoning=result["reasoning"],
        principle=result["principle"],
        disclaimer=result.get("disclaimer"),
        vision_stamp=result["vision_stamp"],
        conversation_id=result["conversation_id"],
    )
