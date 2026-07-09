"""Holdings + SideIncomeEvent CRUD tests + price refresh integration tests.

yfinance and RentCast calls are mocked at the network boundary — no external
requests are made during the test run. Live Postgres required.
"""
from decimal import Decimal
from unittest.mock import patch

import pytest
from httpx import AsyncClient, ASGITransport

from main import app


# ---------------------------------------------------------------------------
# Auth helper
# ---------------------------------------------------------------------------

async def _get_token(client: AsyncClient) -> str:
    await client.post("/auth/register", json={"username": "testuser", "password": "TestPass123!"})
    resp = await client.post(
        "/auth/token",
        data={"username": "testuser", "password": "TestPass123!"},
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


# ---------------------------------------------------------------------------
# Helpers: create prerequisite records
# ---------------------------------------------------------------------------

async def _create_account(client: AsyncClient) -> int:
    resp = await client.post("/vault/accounts", json={
        "institution": "Fidelity", "nickname": "Brokerage", "type": "retirement",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


async def _create_income_stream(client: AsyncClient) -> int:
    resp = await client.post("/vault/income-streams", json={
        "source": "DoorDash", "source_type": "gig", "cadence": "weekly",
    })
    assert resp.status_code == 201
    return resp.json()["id"]


# ---------------------------------------------------------------------------
# Holdings CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_holdings_crud(auth_client: AsyncClient):
    account_id = await _create_account(auth_client)

    # Create
    resp = await auth_client.post("/holdings", json={
        "account_id": account_id,
        "ticker": "VTI",
        "share_count": "42.5",
        "cost_basis": "8900.00",
        "purchase_date": "2024-01-15",
    })
    assert resp.status_code == 201
    holding_id = resp.json()["id"]
    assert resp.json()["ticker"] == "VTI"
    assert resp.json()["share_count"] == "42.5"

    # List — unfiltered
    resp = await auth_client.get("/holdings")
    assert resp.status_code == 200
    assert any(h["id"] == holding_id for h in resp.json())

    # List — filtered by account
    resp = await auth_client.get(f"/holdings?account_id={account_id}")
    assert resp.status_code == 200
    assert all(h["account_id"] == account_id for h in resp.json())

    # Get single
    resp = await auth_client.get(f"/holdings/{holding_id}")
    assert resp.status_code == 200
    assert resp.json()["cost_basis"] == "8900.00"

    # Update
    resp = await auth_client.patch(f"/holdings/{holding_id}", json={"share_count": "50.0"})
    assert resp.status_code == 200
    assert resp.json()["share_count"] == "50.0"

    # Delete
    resp = await auth_client.delete(f"/holdings/{holding_id}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/holdings/{holding_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_holdings_401(auth_client: AsyncClient):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as anon:
        resp = await anon.get("/holdings")
        assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Price refresh — yfinance mocked at network boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_all_prices_populates_last_known_price(auth_client: AsyncClient):
    account_id = await _create_account(auth_client)
    resp = await auth_client.post("/holdings", json={
        "account_id": account_id, "ticker": "VTI", "share_count": "10",
    })
    assert resp.status_code == 201

    with patch("integrations.market_data._fetch_yfinance", return_value=Decimal("245.67")):
        resp = await auth_client.post("/holdings/refresh-prices")

    assert resp.status_code == 200
    data = resp.json()
    assert "VTI" in data["updated"]
    assert data["failed"] == []

    # Verify the price was persisted
    holding_id = resp.json().get("updated") and (
        await auth_client.get("/holdings")
    ).json()[0]["id"]
    resp2 = await auth_client.get(f"/holdings/{holding_id}")
    assert resp2.json()["last_known_price"] == "245.67"


@pytest.mark.asyncio
async def test_refresh_prices_isolates_per_ticker_failure(auth_client: AsyncClient):
    """A failure on one ticker must not abort the batch — others still update."""
    account_id = await _create_account(auth_client)

    resp_vti = await auth_client.post("/holdings", json={
        "account_id": account_id, "ticker": "VTI", "share_count": "5",
    })
    resp_bad = await auth_client.post("/holdings", json={
        "account_id": account_id, "ticker": "BADTICKER", "share_count": "1",
    })
    assert resp_vti.status_code == resp_bad.status_code == 201

    def _mock_fetch(ticker: str) -> Decimal | None:
        return Decimal("245.00") if ticker == "VTI" else None

    with patch("integrations.market_data._fetch_yfinance", side_effect=_mock_fetch):
        with patch("integrations.market_data._fetch_alpha_vantage", return_value=None):
            resp = await auth_client.post("/holdings/refresh-prices")

    assert resp.status_code == 200
    data = resp.json()
    assert "VTI" in data["updated"]
    assert "BADTICKER" in data["failed"]


@pytest.mark.asyncio
async def test_refresh_prices_fetches_each_ticker_once(auth_client: AsyncClient):
    """Two holdings of the same ticker → ONE price fetch, both rows updated."""
    account_id = await _create_account(auth_client)
    for shares in ("3", "7"):
        resp = await auth_client.post("/holdings", json={
            "account_id": account_id, "ticker": "VTI", "share_count": shares,
        })
        assert resp.status_code == 201

    with patch(
        "integrations.market_data._fetch_yfinance", return_value=Decimal("100.00")
    ) as mock_fetch:
        resp = await auth_client.post("/holdings/refresh-prices")

    assert resp.status_code == 200
    data = resp.json()
    assert data["updated"] == ["VTI"]
    assert data["total"] == 1
    assert mock_fetch.call_count == 1

    listing = (await auth_client.get("/holdings")).json()
    assert len(listing) == 2
    assert all(h["last_known_price"] == "100.00" for h in listing)


@pytest.mark.asyncio
async def test_refresh_single_price(auth_client: AsyncClient):
    account_id = await _create_account(auth_client)
    resp = await auth_client.post("/holdings", json={
        "account_id": account_id, "ticker": "VXUS", "share_count": "20",
    })
    holding_id = resp.json()["id"]

    with patch("integrations.market_data._fetch_yfinance", return_value=Decimal("58.32")):
        resp = await auth_client.post(f"/holdings/{holding_id}/refresh-price")

    assert resp.status_code == 200
    assert resp.json()["last_known_price"] == "58.32"


@pytest.mark.asyncio
async def test_refresh_single_price_502_on_failure(auth_client: AsyncClient):
    account_id = await _create_account(auth_client)
    resp = await auth_client.post("/holdings", json={
        "account_id": account_id, "ticker": "BADINPUT", "share_count": "1",
    })
    holding_id = resp.json()["id"]

    with patch("integrations.market_data._fetch_yfinance", return_value=None):
        with patch("integrations.market_data._fetch_alpha_vantage", return_value=None):
            resp = await auth_client.post(f"/holdings/{holding_id}/refresh-price")

    assert resp.status_code == 502


# ---------------------------------------------------------------------------
# Real estate refresh — RentCast mocked at network boundary
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_real_estate_values(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/real-estate", json={
        "address": "123 Main St, Springfield, IL 62701",
        "property_type": "primary",
        "current_value": "200000.00",
    })
    assert resp.status_code == 201

    from integrations.property_data import PropertyEstimate
    mock_estimate = PropertyEstimate(
        price=Decimal("215000.00"),
        price_range_low=Decimal("205000.00"),
        price_range_high=Decimal("225000.00"),
    )

    with patch("routers.vault.fetch_property_estimate", return_value=mock_estimate):
        with patch("routers.vault.get_settings") as mock_settings:
            mock_settings.return_value.rentcast_api_key = "test-key"
            resp = await auth_client.post("/vault/real-estate/refresh-values")

    assert resp.status_code == 200
    data = resp.json()
    assert data["disclaimer"] != ""
    assert "estimate" in data["disclaimer"].lower()
    assert len(data["updated"]) > 0


@pytest.mark.asyncio
async def test_refresh_real_estate_503_no_key(auth_client: AsyncClient):
    """Refresh endpoint must 503 when RENTCAST_API_KEY is not configured."""
    with patch("routers.vault.get_settings") as mock_settings:
        mock_settings.return_value.rentcast_api_key = None
        resp = await auth_client.post("/vault/real-estate/refresh-values")
    assert resp.status_code == 503


# ---------------------------------------------------------------------------
# Side Income Events CRUD
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_income_event_crud(auth_client: AsyncClient):
    stream_id = await _create_income_stream(auth_client)

    resp = await auth_client.post("/side-income-events", json={
        "income_stream_id": stream_id,
        "occurred_at": "2026-05-24T18:00:00Z",
        "duration_minutes": 240,
        "gross": "87.50",
        "notes": "Saturday evening shift",
    })
    assert resp.status_code == 201
    event_id = resp.json()["id"]
    assert resp.json()["gross"] == "87.50"

    # List filtered by stream
    resp = await auth_client.get(f"/side-income-events?stream_id={stream_id}")
    assert resp.status_code == 200
    assert any(e["id"] == event_id for e in resp.json())

    # Get single
    resp = await auth_client.get(f"/side-income-events/{event_id}")
    assert resp.status_code == 200
    assert resp.json()["duration_minutes"] == 240

    # Update
    resp = await auth_client.patch(f"/side-income-events/{event_id}", json={"gross": "92.00"})
    assert resp.status_code == 200
    assert resp.json()["gross"] == "92.00"

    # Delete
    resp = await auth_client.delete(f"/side-income-events/{event_id}")
    assert resp.status_code == 204

    resp = await auth_client.get(f"/side-income-events/{event_id}")
    assert resp.status_code == 404
