"""Shared slowapi rate limiter instance.

Backed by Redis so limits are enforced consistently and survive a process
restart — the slowapi default in-memory store is per-process and resets on every
deploy. Under TESTING the limiter is disabled and no store is needed.
"""
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from config import get_settings

_enabled = os.environ.get("TESTING", "").lower() not in ("1", "true")

limiter = Limiter(
    key_func=get_remote_address,
    enabled=_enabled,
    storage_uri=get_settings().redis_url if _enabled else None,
)
