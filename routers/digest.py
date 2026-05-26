"""Digest endpoints — POST /digest/run-now."""
from __future__ import annotations
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import get_current_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/digest", tags=["digest"])
CurrentUser = Annotated[str, Depends(get_current_user)]


class DigestResponse(BaseModel):
    status: str
    body: str


@router.post("/run-now", response_model=DigestResponse)
async def run_digest_now(_user: CurrentUser) -> DigestResponse:
    """Trigger the digest immediately and email it."""
    from digest import generate_and_send_digest
    try:
        body = await generate_and_send_digest()
        return DigestResponse(status="sent", body=body)
    except Exception as exc:
        logger.error("run-now digest failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Digest send failed: {exc}") from exc
