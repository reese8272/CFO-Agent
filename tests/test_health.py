"""Smoke tests for the /health endpoint and the disclaimer module.

The health test requires live Postgres + Redis. Bring them up first:
    docker compose up -d postgres redis
"""
import pytest
from fastapi.testclient import TestClient


@pytest.fixture(scope="module")
def client() -> TestClient:
    from main import app

    with TestClient(app) as test_client:
        yield test_client


def test_health_returns_ok(client: TestClient) -> None:
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload == {"status": "ok", "postgres": "ok", "redis": "ok"}


def test_disclaimer_loadable() -> None:
    from disclaimer import DISCLAIMER, get_disclaimer

    assert "licensed financial advisor" in DISCLAIMER
    assert get_disclaimer() == DISCLAIMER


def test_disclaimer_respects_settings_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from config import get_settings
    from disclaimer import get_disclaimer

    # The override now flows through typed Settings (loaded from env/.env), not a
    # raw os.environ read — so clear the settings cache to pick up the new value.
    monkeypatch.setenv("WEALTH_DISCLAIMER_TEXT", "Custom disclaimer for tests.")
    get_settings.cache_clear()
    try:
        assert get_disclaimer() == "Custom disclaimer for tests."
    finally:
        get_settings.cache_clear()
