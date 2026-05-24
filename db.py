"""Async SQLAlchemy engine, declarative Base, and session factory.

Issue 1: engine + /health ping.
Issue 2: declarative Base and async session factory for the ORM models.
"""
import logging

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from config import get_settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Shared declarative base for all ORM models."""


_engine: AsyncEngine | None = None
_sessionmaker: async_sessionmaker[AsyncSession] | None = None


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


def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return the module-level session factory."""
    global _sessionmaker
    if _sessionmaker is None:
        _sessionmaker = async_sessionmaker(get_engine(), expire_on_commit=False)
    return _sessionmaker


async def dispose_engine() -> None:
    """Dispose the engine and its connection pool. Called on app shutdown."""
    global _engine, _sessionmaker
    if _engine is not None:
        await _engine.dispose()
        _engine = None
        _sessionmaker = None
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
