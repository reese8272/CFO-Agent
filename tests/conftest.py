"""pytest configuration.

Sets test defaults for env vars not provided by the environment so the app's
fail-fast config validation passes inside the test process. Real values
come from the .env (or docker-compose env_file) when the app runs for real.

Tests require live Postgres + Redis per CLAUDE.md ("No DB mocking — use real
Postgres via docker-compose"). Bring them up with:
    docker compose up -d postgres redis
"""
import os

from cryptography.fernet import Fernet

_TEST_DEFAULTS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "test-key",
    "DATABASE_URL": "postgresql+psycopg://cfo:cfo@postgres:5432/personal_cfo",
    "REDIS_URL": "redis://redis:6379/0",
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


import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, text  # noqa: E402
from sqlalchemy.ext.asyncio import AsyncSession  # noqa: E402

from config import get_settings  # noqa: E402
from db import get_sessionmaker  # noqa: E402

# Vault tables wiped between tests; CASCADE clears FK-dependent rows in any order.
_VAULT_TABLES = (
    "audit_log", "users", "accounts", "cards", "income_streams", "expenses", "debts",
    "assets", "real_estate", "business_income", "retirement_accounts", "goals",
    "career_position", "career_history", "comp_benchmarks", "side_income_economics",
    "tax_deductions_1099", "negotiation_milestones", "net_worth_snapshots",
)


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    """Async DB session that rolls back after each test."""
    async with get_sessionmaker()() as s:
        try:
            yield s
        finally:
            await s.rollback()


@pytest.fixture(scope="module")
def client() -> TestClient:
    """App-bound TestClient (runs lifespan: engine + redis)."""
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def _wipe_vault() -> None:
    """Truncate vault + users via a throwaway sync engine (no event-loop collision)."""
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        conn.execute(
            text(f"TRUNCATE TABLE {', '.join(_VAULT_TABLES)} RESTART IDENTITY CASCADE")
        )
    engine.dispose()


@pytest.fixture
def auth_headers(client: TestClient) -> dict[str, str]:
    """Clean vault, register the single user, return a bearer-auth header."""
    _wipe_vault()
    resp = client.post(
        "/auth/register", json={"username": "owner", "password": "supersecret123"}
    )
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}
