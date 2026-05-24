"""pytest configuration.

Sets test defaults for env vars not provided by the environment so the app's
fail-fast config validation passes inside the test process. Real values
come from the .env (or docker-compose env_file) when the app runs for real.

Tests require live Postgres + Redis per CLAUDE.md ("No DB mocking — use real
Postgres via docker-compose"). Bring them up with:
    docker compose up -d postgres redis
"""
import os

_TEST_DEFAULTS: dict[str, str] = {
    "ANTHROPIC_API_KEY": "test-key",
    "DATABASE_URL": "postgresql+psycopg://cfo:cfo@postgres:5432/personal_cfo",
    "REDIS_URL": "redis://redis:6379/0",
    "JWT_SECRET_KEY": "test-secret-key-must-be-at-least-32-chars-x",
    "VAULT_ENCRYPTION_KEY": "test-fernet-key-placeholder",
    "DIGEST_RECIPIENT": "test@example.com",
    "SMTP_HOST": "localhost",
    "SMTP_PORT": "1025",
    "SMTP_USER": "test",
    "SMTP_PASSWORD": "test",
    "SMTP_FROM": "noreply@example.com",
}
for _key, _value in _TEST_DEFAULTS.items():
    os.environ.setdefault(_key, _value)
