"""Memory endpoints — decisions CRUD + patterns listing."""
from __future__ import annotations
from typing import Annotated
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from auth import get_current_user
from db import get_session
from memory.models import Conversation, Decision, Message, Pattern

router = APIRouter(prefix="/memory", tags=["memory"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[str, Depends(get_current_user)]


class DecisionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    decided_at: datetime
    summary: str
    principle: str | None
    expires_at: datetime | None
    status: str


class DecisionPatch(BaseModel):
    status: str  # "active" | "superseded" | "abandoned"


class ConversationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    started_at: datetime


class MessageRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    role: str
    content: str
    created_at: datetime
    cited_principle: str | None


class PatternRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    detected_at: datetime
    kind: str
    severity: str
    summary: str
    acknowledged_at: datetime | None


@router.get("/conversations", response_model=list[ConversationRead])
async def list_conversations(session: Session, _user: CurrentUser):
    result = await session.execute(
        select(Conversation).order_by(Conversation.started_at.desc()).limit(20)
    )
    return result.scalars().all()


@router.get("/conversations/{conversation_id}/messages", response_model=list[MessageRead])
async def list_messages(conversation_id: int, session: Session, _user: CurrentUser):
    result = await session.execute(
        select(Message)
        .where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
    )
    return result.scalars().all()


@router.get("/decisions", response_model=list[DecisionRead])
async def list_decisions(session: Session, _user: CurrentUser):
    result = await session.execute(
        select(Decision).order_by(Decision.decided_at.desc()).limit(50)
    )
    return result.scalars().all()


@router.patch("/decisions/{decision_id}", response_model=DecisionRead)
async def update_decision(decision_id: int, body: DecisionPatch, session: Session, _user: CurrentUser):
    result = await session.execute(select(Decision).where(Decision.id == decision_id))
    obj = result.scalar_one_or_none()
    if obj is None:
        raise HTTPException(status_code=404)
    obj.status = body.status
    await session.commit()
    await session.refresh(obj)
    return obj


@router.get("/patterns", response_model=list[PatternRead])
async def list_patterns(session: Session, _user: CurrentUser):
    result = await session.execute(
        select(Pattern).order_by(Pattern.detected_at.desc()).limit(50)
    )
    return result.scalars().all()
