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
        settings = get_settings()
        # Bound every LLM call: without an explicit timeout the SDK default is
        # 600s, so a hung Anthropic response would stall the agent for 10 minutes
        # with no backpressure. max_retries lets the SDK ride out 429/5xx.
        _anthropic = anthropic_sdk.AsyncAnthropic(
            api_key=settings.anthropic_api_key,
            timeout=settings.llm_timeout_seconds,
            max_retries=settings.llm_max_retries,
        )
        logger.info("anthropic client created")
    return _anthropic
