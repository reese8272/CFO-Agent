"""Wealth, income, and net-worth trajectory endpoints.

All endpoints are behind JWT auth. No LLM calls — pure data logic.

> Disclaimer: This tool is for financial education and personal organization.
> It is not a licensed financial advisor. For tax strategy, real estate
> transactions, and investment decisions, consult a licensed professional.
"""
from __future__ import annotations
from typing import Annotated
from datetime import datetime, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from db import get_session
from auth import User, get_current_user
from vault.wealth_position import compute_wealth_position
from vault.income_position import compute_income_position

router = APIRouter(prefix="/wealth", tags=["wealth"])
Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# --- Response models (mirror the WealthLadder / IncomeLadder TypedDicts) -----
# NOTE: these enforce the *actual* wire shape the frontend consumes, which
# diverges from the frozen CONTRACTS.md §3 draft shapes (see docs/DECISIONS.md
# 2026-07-02 "wealth endpoint response_model" entry).

class AllocationGapModel(BaseModel):
    step: int
    label: str
    target: str
    current: Decimal
    gap: Decimal
    funded: bool


class WealthPositionResponse(BaseModel):
    net_worth: Decimal
    total_assets: Decimal
    total_liabilities: Decimal
    allocation_ladder: list[AllocationGapModel]
    open_gaps: list[AllocationGapModel]
    timestamp: str


class IncomeStepModel(BaseModel):
    step: int
    label: str
    monthly_target: Decimal | None
    monthly_actual: Decimal
    funded: bool


class IncomePositionResponse(BaseModel):
    total_monthly_income: Decimal
    income_ladder: list[IncomeStepModel]
    open_gaps: list[IncomeStepModel]
    timestamp: str


class CombinedPositionResponse(BaseModel):
    wealth: WealthPositionResponse
    income: IncomePositionResponse


class NetWorthPoint(BaseModel):
    net_worth: str
    total_assets: str
    total_liabilities: str
    timestamp: str


class NetWorthHistoryEntry(BaseModel):
    net_worth: str
    assets_total: str
    liabilities_total: str
    recorded_at: str


class NetWorthTrajectoryResponse(BaseModel):
    current: NetWorthPoint
    history: list[NetWorthHistoryEntry]


@router.get("/position", response_model=CombinedPositionResponse)
async def get_position(session: Session, user: CurrentUser) -> dict:
    """Return allocation and income positions in one call."""
    wealth = await compute_wealth_position(session, user)
    income = await compute_income_position(session, user)
    return {"wealth": wealth, "income": income}


@router.get("/allocation-position", response_model=WealthPositionResponse)
async def get_allocation_position(session: Session, user: CurrentUser) -> dict:
    """Return the 6-step allocation ladder with current gaps."""
    return await compute_wealth_position(session, user)


@router.get("/income-position", response_model=IncomePositionResponse)
async def get_income_position(session: Session, user: CurrentUser) -> dict:
    """Return the 5-step income ladder with current gaps."""
    return await compute_income_position(session, user)


@router.get("/net-worth-trajectory", response_model=NetWorthTrajectoryResponse)
async def get_net_worth_trajectory(session: Session, user: CurrentUser) -> dict:
    """Return current net worth + historical snapshots from net_worth_snapshots."""
    from vault.models import NetWorthSnapshot

    result = await session.execute(
        select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_at)
    )
    snapshots = result.scalars().all()
    current = await compute_wealth_position(session, user)

    return {
        "current": {
            "net_worth": str(current["net_worth"]),
            "total_assets": str(current["total_assets"]),
            "total_liabilities": str(current["total_liabilities"]),
            "timestamp": current["timestamp"],
        },
        "history": [
            {
                "net_worth": str(getattr(s, "net_worth", None) or "0"),
                "assets_total": str(getattr(s, "assets_total", None) or "0"),
                "liabilities_total": str(getattr(s, "liabilities_total", None) or "0"),
                "recorded_at": getattr(s, "snapshot_at", datetime.now(timezone.utc)).isoformat(),
            }
            for s in snapshots
        ],
    }
