"""API-surface hardening tests (Phase 5b).

Covers the response_model contracts added to the wealth / intake / holdings
endpoints and the security-headers middleware. The load-bearing assertion for
the response models is that they accept *real* (empty-DB) output without a 500 —
a too-strict model would reject a valid response.

Live Postgres + Redis required.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from main import app


async def _get_token(client: AsyncClient) -> str:
    await client.post("/auth/register", json={"username": "apiuser", "password": "TestPass123!"})
    resp = await client.post(
        "/auth/token",
        data={"username": "apiuser", "password": "TestPass123!"},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    assert resp.status_code == 200
    return resp.json()["access_token"]


@pytest.fixture
async def auth_client(clean_db: None):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


# --- response_model shapes ---------------------------------------------------

async def test_wealth_position_validates(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/wealth/position")
    assert resp.status_code == 200
    body = resp.json()
    # Combined shape: {"wealth": WealthPosition, "income": IncomePosition}
    assert set(body) == {"wealth", "income"}
    wealth = body["wealth"]
    assert set(wealth) == {
        "net_worth", "total_assets", "total_liabilities",
        "allocation_ladder", "open_gaps", "timestamp",
    }
    # 6-step allocation ladder always fully populated
    assert len(wealth["allocation_ladder"]) == 6
    step = wealth["allocation_ladder"][0]
    assert set(step) == {"step", "label", "target", "current", "gap", "funded"}
    income = body["income"]
    assert set(income) == {
        "total_monthly_income", "income_ladder", "open_gaps", "timestamp",
    }


async def test_net_worth_trajectory_validates(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/wealth/net-worth-trajectory")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"current", "history"}
    assert set(body["current"]) == {
        "net_worth", "total_assets", "total_liabilities", "timestamp",
    }
    assert isinstance(body["history"], list)


async def test_intake_status_validates(auth_client: AsyncClient) -> None:
    resp = await auth_client.get("/intake/status")
    assert resp.status_code == 200
    body = resp.json()
    # Fresh user: intake not completed, nullable fields present as null
    assert body["intake_completed"] is False
    assert set(body) == {
        "intake_completed", "completed_at", "snapshot_id",
        "net_worth", "allocation_step", "income_step",
    }


async def test_refresh_prices_validates(auth_client: AsyncClient) -> None:
    # No holdings → empty summary, no network call.
    resp = await auth_client.post("/holdings/refresh-prices")
    assert resp.status_code == 200
    body = resp.json()
    assert set(body) == {"updated", "failed", "total"}
    assert body == {"updated": [], "failed": [], "total": 0}


# --- security headers --------------------------------------------------------

async def test_security_headers_present() -> None:
    # GET / returns a redirect but still passes through the middleware; it
    # touches neither redis nor Postgres, so no connection leaks across the
    # ASGITransport event loop.
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/", follow_redirects=False)
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    # HSTS is prod-only; the test env is not production.
    assert "Strict-Transport-Security" not in resp.headers


async def test_request_id_minted_and_echoed() -> None:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # no inbound id → one is minted
        minted = await client.get("/", follow_redirects=False)
        assert minted.headers.get("X-Request-ID")
        # inbound id → echoed back verbatim (correlation across a proxy hop)
        echoed = await client.get(
            "/", follow_redirects=False, headers={"X-Request-ID": "trace-abc-123"}
        )
    assert echoed.headers["X-Request-ID"] == "trace-abc-123"
