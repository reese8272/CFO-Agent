"""pytest configuration.

Sets test defaults for env vars not provided by the environment so the app's
fail-fast config validation passes inside the test process. Real values
come from the .env (or docker-compose env_file) when the app runs for real.

Tests require live Postgres + Redis per CLAUDE.md ("No DB mocking — use real
Postgres via docker-compose"). Bring them up with:
    docker compose up -d postgres redis
"""
import os

import pytest
from cryptography.fernet import Fernet

_TEST_DEFAULTS: dict[str, str] = {
    "TESTING": "true",
    "ANTHROPIC_API_KEY": "test-key",
    "DATABASE_URL": "postgresql+psycopg://cfo:cfo@localhost:5432/personal_cfo",
    "REDIS_URL": "redis://localhost:6379/0",
    "JWT_SECRET_KEY": "test-secret-key-must-be-at-least-32-chars-x",
    "VAULT_ENCRYPTION_KEY": Fernet.generate_key().decode(),
    "DIGEST_RECIPIENT": "test@example.com",
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_USER": "test",
    "SMTP_PASSWORD": "test",
    "SMTP_FROM": "noreply@example.com",
}
for _key, _value in _TEST_DEFAULTS.items():
    os.environ.setdefault(_key, _value)


import pytest_asyncio  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from config import get_settings  # noqa: E402
from db import get_sessionmaker  # noqa: E402

# Re-export so pytest recognises it without an explicit import in test files
__all__ = ["clean_users", "session"]


_TRUNCATE_ALL = text("""
    TRUNCATE TABLE
        users, accounts, cards, income_streams, expenses, debts, assets,
        real_estate, business_income, retirement_accounts, goals,
        career_position, career_history, comp_benchmarks,
        side_income_economics, side_income_events, holdings,
        net_worth_snapshots, tax_deductions_1099, negotiation_milestones,
        transactions, import_batches, category_mappings,
        audit_log, conversations, messages, decisions, patterns,
        user_profile, financial_snapshots, intake_submissions
    RESTART IDENTITY CASCADE
""")


@pytest.fixture
def clean_users() -> None:
    """Delete all users. Kept for backward compat; prefer clean_db for auth tests."""
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    engine.dispose()


@pytest.fixture
def clean_db() -> None:
    """Truncate every vault table and reset sequences.

    Use as a dependency on any fixture that needs a guaranteed-clean DB before
    running an integration test via the ASGI transport (which commits to the
    real DB). Prevents Fernet decryption errors from stale rows encrypted with
    a different key in a prior test session.
    """
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        conn.execute(_TRUNCATE_ALL)
    engine.dispose()


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Async DB session that rolls back after each test."""
    async with get_sessionmaker()() as s:
        try:
            yield s
        finally:
            await s.rollback()
