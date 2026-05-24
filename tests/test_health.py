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


def test_disclaimer_respects_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    from disclaimer import get_disclaimer

    monkeypatch.setenv("WEALTH_DISCLAIMER_TEXT", "Custom disclaimer for tests.")
    assert get_disclaimer() == "Custom disclaimer for tests."
