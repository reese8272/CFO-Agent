"""Async SQLAlchemy engine for Postgres.

Issue 1 uses this only for the /health ping. Issue 2 layers Alembic + ORM
models on top of the same engine.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from config import get_settings

logger = logging.getLogger(__name__)

_engine: AsyncEngine | None = None


def get_engine() -> AsyncEngine:
    """Return the module-level async engine, creating it on first call."""
    global _engine
    if _engine is None:
        _engine = create_async_engine(
            get_settings().database_url,
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        logger.info("postgres engine created")
    return _engine


async def dispose_engine() -> None:
    """Dispose the engine and its connection pool. Called on app shutdown."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        logger.info("postgres engine disposed")


async def ping() -> bool:
    """Return True if SELECT 1 succeeds against Postgres."""
    try:
        async with get_engine().connect() as conn:
            result = await conn.execute(text("SELECT 1"))
            return result.scalar() == 1
    except Exception:
        logger.exception("postgres ping failed")
        return False
