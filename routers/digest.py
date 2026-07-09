"""Digest endpoints — POST /digest/run-now."""
from __future__ import annotations
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from auth import User, get_current_user
from rate_limit import limiter

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/digest", tags=["digest"])
CurrentUser = Annotated[User, Depends(get_current_user)]


class DigestResponse(BaseModel):
    status: str
    body: str


@router.post("/run-now", response_model=DigestResponse)
@limiter.limit("3/hour")
async def run_digest_now(request: Request, _user: CurrentUser) -> DigestResponse:
    """Trigger the digest immediately and email it."""
    from digest import generate_and_send_digest
    try:
        body = await generate_and_send_digest()
        return DigestResponse(status="sent", body=body)
    except Exception as exc:
        # Don't leak the raw SMTP/exception detail to the client.
        logger.error("run-now digest failed: %s", exc)
        raise HTTPException(status_code=502, detail="Digest send failed") from exc
