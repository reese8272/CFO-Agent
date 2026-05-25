"""Auth surface tests — register-once, token issuance, and route protection.

Requires live Postgres with migrations applied (`alembic upgrade head`).
Cleanup uses a throwaway sync engine so it never collides with the app's
async engine bound to the TestClient event loop.
"""
from datetime import datetime, timedelta, timezone

import jwt as pyjwt
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text

from auth import JWT_ALGORITHM
from config import get_settings

_CREDS = {"username": "owner", "password": "supersecret123"}


@pytest.fixture(scope="module")
def client() -> TestClient:
    from main import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def clean_users() -> None:
    engine = create_engine(get_settings().database_url)
    with engine.begin() as conn:
        conn.execute(text("DELETE FROM users"))
    engine.dispose()


def test_register_first_succeeds_then_409(client: TestClient, clean_users: None) -> None:
    first = client.post("/auth/register", json=_CREDS)
    assert first.status_code == 201
    body = first.json()
    assert body["token_type"] == "bearer"
    assert body["access_token"]

    second = client.post(
        "/auth/register", json={"username": "intruder", "password": "anotherpass123"}
    )
    assert second.status_code == 409


def test_token_issued_and_protects_route(client: TestClient, clean_users: None) -> None:
    client.post("/auth/register", json=_CREDS)

    # No token → 401
    assert client.get("/auth/me").status_code == 401

    token_resp = client.post(
        "/auth/token",
        data={"username": _CREDS["username"], "password": _CREDS["password"]},
    )
    assert token_resp.status_code == 200
    access_token = token_resp.json()["access_token"]

    me = client.get("/auth/me", headers={"Authorization": f"Bearer {access_token}"})
    assert me.status_code == 200
    assert me.json()["username"] == _CREDS["username"]


def test_token_rejects_bad_password(client: TestClient, clean_users: None) -> None:
    client.post("/auth/register", json=_CREDS)
    resp = client.post(
        "/auth/token", data={"username": _CREDS["username"], "password": "wrong-password"}
    )
    assert resp.status_code == 401


def test_token_rejects_unknown_user(client: TestClient, clean_users: None) -> None:
    resp = client.post(
        "/auth/token", data={"username": "ghost", "password": "supersecret123"}
    )
    assert resp.status_code == 401


def test_expired_token_rejected(client: TestClient, clean_users: None) -> None:
    client.post("/auth/register", json=_CREDS)
    now = datetime.now(timezone.utc)
    expired = pyjwt.encode(
        {"sub": "1", "iat": now - timedelta(hours=2), "exp": now - timedelta(hours=1)},
        get_settings().jwt_secret_key,
        algorithm=JWT_ALGORITHM,
    )
    resp = client.get("/auth/me", headers={"Authorization": f"Bearer {expired}"})
    assert resp.status_code == 401


def test_malformed_token_rejected(client: TestClient) -> None:
    resp = client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401
