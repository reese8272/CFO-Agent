"""Typed application configuration loaded from environment / .env.

pydantic-settings reads `.env` via python-dotenv under the hood and validates
on instantiation, so the app fails fast on missing required values.
"""
from functools import lru_cache

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
    vault_encryption_key: str = Field(..., min_length=1)
    digest_recipient: str = Field(..., min_length=1)
    smtp_host: str = Field(..., min_length=1)
    smtp_port: int = Field(...)
    smtp_user: str = Field(..., min_length=1)
    smtp_password: str = Field(..., min_length=1)
    smtp_from: str = Field(..., min_length=1)

    jwt_expiry_minutes: int = 60
    llm_timeout_seconds: int = 120
    env: str = "development"
    langgraph_checkpoint_backend: str = "redis"
    alert_drift_pct_threshold: int = 25
    alert_income_drop_pct_threshold: int = 30
    wealth_disclaimer_text: str | None = None

    rentcast_api_key: str | None = None
    alpha_vantage_key: str | None = None

    plaid_client_id: str | None = None
    plaid_secret: str | None = None
    plaid_env: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
