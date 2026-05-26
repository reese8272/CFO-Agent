"""External client singletons.

Issue 1: async Redis client.
Issue 6: adds the Anthropic SDK client.
"""
import logging

import anthropic as anthropic_sdk
import redis.asyncio as aioredis

from config import get_settings

logger = logging.getLogger(__name__)

_redis: aioredis.Redis | None = None


def get_redis() -> aioredis.Redis:
    """Return the module-level async Redis client, creating it on first call."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            get_settings().redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("redis client created")
    return _redis


async def close_redis() -> None:
    """Close the Redis client. Called on app shutdown."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None
        logger.info("redis client closed")


async def ping_redis() -> bool:
    """Return True if PING succeeds against Redis."""
    try:
        return bool(await get_redis().ping())
    except Exception:
        logger.exception("redis ping failed")
        return False


_anthropic: anthropic_sdk.AsyncAnthropic | None = None


def get_anthropic() -> anthropic_sdk.AsyncAnthropic:
    """Return the module-level async Anthropic client, creating it on first call."""
    global _anthropic
    if _anthropic is None:
        _anthropic = anthropic_sdk.AsyncAnthropic(
            api_key=get_settings().anthropic_api_key,
        )
        logger.info("anthropic client created")
    return _anthropic
