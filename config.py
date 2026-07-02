"""Typed application configuration loaded from environment / .env.

pydantic-settings reads `.env` via python-dotenv under the hood and validates
on instantiation, so the app fails fast on missing required values.
"""
from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    anthropic_api_key: str = Field(..., min_length=1)
    database_url: str = Field(..., min_length=1)
    redis_url: str = Field(..., min_length=1)
    jwt_secret_key: str = Field(..., min_length=32)
    # A real Fernet key is 44 url-safe-base64 chars; fail fast on a truncated one.
    vault_encryption_key: str = Field(..., min_length=44)
    # Optional comma-separated keys for rotation (first encrypts, all decrypt).
    # When set, supersedes vault_encryption_key. See crypto._fernet / DEPLOYMENT.md.
    vault_encryption_keys: Optional[str] = None
    digest_recipient: str = Field(..., min_length=1)
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None
    smtp_from: Optional[str] = None

    jwt_expiry_minutes: int = 60
    llm_timeout_seconds: int = 120
    llm_max_retries: int = 2
    # Model ids sourced here (not hardcoded in nodes) so a model change is one edit.
    # Defaults preserve the exact ids the app already used — changing tier is a
    # deliberate decision, not a side effect of this setting existing.
    anthropic_model_smart: str = "claude-sonnet-4-6"
    anthropic_model_fast: str = "claude-haiku-4-5-20251001"
    env: str = "development"
    langgraph_checkpoint_backend: str = "redis"
    alert_drift_pct_threshold: int = 25
    alert_income_drop_pct_threshold: int = 30
    wealth_disclaimer_text: str | None = None

    allowed_origins: list[str] = ["http://localhost:8000"]

    rentcast_api_key: str | None = None
    alpha_vantage_key: str | None = None

    healthcheck_ping_url: str | None = None

    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
