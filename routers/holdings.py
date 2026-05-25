"""Holdings router — /holdings/* endpoints.

Covers:
- CRUD for the holdings table (per-share investment tracking)
- CRUD for side_income_events (per-shift granularity)
- POST /holdings/refresh-prices  — batch price refresh via yfinance
- POST /holdings/{id}/refresh-price — single holding price refresh
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import get_settings
from db import get_session
from integrations.market_data import fetch_price
from vault import crud
from vault.models import Holdings
from vault.schemas import (
    HoldingsCreate, HoldingsRead, HoldingsUpdate,
    SideIncomeEventCreate, SideIncomeEventRead, SideIncomeEventUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/holdings", tags=["holdings"])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[str, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Holdings CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=HoldingsRead, status_code=201)
async def create_holding(body: HoldingsCreate, session: Session, user: CurrentUser):
    obj = await crud.create_holding(session, body, actor=user)
    await session.commit()
    return obj


@router.get("", response_model=list[HoldingsRead])
async def list_holdings(session: Session, user: CurrentUser, account_id: int | None = None):
    return await crud.list_holdings(session, account_id=account_id)


@router.get("/{holding_id}", response_model=HoldingsRead)
async def get_holding(holding_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_holding(session, holding_id)
    if obj is None:
        raise HTTPException(404, "holding not found")
    return obj


@router.patch("/{holding_id}", response_model=HoldingsRead)
async def update_holding(holding_id: int, body: HoldingsUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_holding(session, holding_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "holding not found")
    await session.commit()
    return obj


@router.delete("/{holding_id}", status_code=204)
async def delete_holding(holding_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_holding(session, holding_id, actor=user)
    if not deleted:
        raise HTTPException(404, "holding not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Price refresh
# ---------------------------------------------------------------------------

@router.post("/refresh-prices", status_code=200)
async def refresh_all_prices(session: Session, user: CurrentUser) -> dict:
    """Pull latest price for every distinct ticker in holdings.

    Per-ticker errors are isolated — one failure does not abort the batch.
    Returns a summary of updated, skipped, and failed tickers.
    """
    rows = await crud.list_distinct_tickers(session)
    updated: list[str] = []
    failed: list[str] = []
    now = datetime.now(timezone.utc)

    for holding_id, ticker in rows:
        price = fetch_price(ticker)
        if price is None:
            logger.warning("price refresh: no price returned for ticker %s", ticker)
            failed.append(ticker)
            continue
        obj = await session.get(Holdings, holding_id)
        if obj is None:
            continue
        obj.last_known_price = price
        obj.last_priced_at = now
        updated.append(ticker)

    await session.commit()
    return {"updated": updated, "failed": failed, "total": len(rows)}


@router.post("/{holding_id}/refresh-price", response_model=HoldingsRead)
async def refresh_single_price(holding_id: int, session: Session, user: CurrentUser):
    """Refresh price for a single holding."""
    obj = await session.get(Holdings, holding_id)
    if obj is None:
        raise HTTPException(404, "holding not found")

    price = fetch_price(obj.ticker)
    if price is None:
        raise HTTPException(502, f"could not fetch price for ticker {obj.ticker!r}")

    obj.last_known_price = price
    obj.last_priced_at = datetime.now(timezone.utc)
    await session.commit()
    return obj


# ---------------------------------------------------------------------------
# Side Income Events CRUD
# ---------------------------------------------------------------------------

side_event_router = APIRouter(prefix="/side-income-events", tags=["side-income-events"])


@side_event_router.post("", response_model=SideIncomeEventRead, status_code=201)
async def create_side_income_event(body: SideIncomeEventCreate, session: Session, user: CurrentUser):
    obj = await crud.create_side_income_event(session, body, actor=user)
    await session.commit()
    return obj


@side_event_router.get("", response_model=list[SideIncomeEventRead])
async def list_side_income_events(session: Session, user: CurrentUser, stream_id: int | None = None):
    return await crud.list_side_income_events(session, stream_id=stream_id)


@side_event_router.get("/{event_id}", response_model=SideIncomeEventRead)
async def get_side_income_event(event_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_side_income_event(session, event_id)
    if obj is None:
        raise HTTPException(404, "side income event not found")
    return obj


@side_event_router.patch("/{event_id}", response_model=SideIncomeEventRead)
async def update_side_income_event(event_id: int, body: SideIncomeEventUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_side_income_event(session, event_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "side income event not found")
    await session.commit()
    return obj


@side_event_router.delete("/{event_id}", status_code=204)
async def delete_side_income_event(event_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_side_income_event(session, event_id, actor=user)
    if not deleted:
        raise HTTPException(404, "side income event not found")
    await session.commit()
