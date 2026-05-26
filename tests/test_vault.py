"""Vault CRUD tests — happy paths + 404 + 401.

Requires live Postgres (docker compose up -d postgres redis).
Each test rolls back via the session fixture so the DB stays clean.
"""
import pytest
from httpx import AsyncClient, ASGITransport

from main import app


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _get_token(client: AsyncClient) -> str:
    """Register a test user (if needed) and return a valid JWT."""
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
    """AsyncClient with a valid Authorization header."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        token = await _get_token(client)
        client.headers.update({"Authorization": f"Bearer {token}"})
        yield client


@pytest.fixture
async def anon_client():
    """AsyncClient without auth."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_account_crud(auth_client: AsyncClient):
    # Create
    resp = await auth_client.post("/vault/accounts", json={
        "institution": "Chase", "nickname": "Checking", "type": "checking",
        "current_balance": "1500.00",
    })
    assert resp.status_code == 201
    account_id = resp.json()["id"]
    assert resp.json()["institution"] == "Chase"

    # Read list
    resp = await auth_client.get("/vault/accounts")
    assert resp.status_code == 200
    ids = [a["id"] for a in resp.json()]
    assert account_id in ids

    # Read single
    resp = await auth_client.get(f"/vault/accounts/{account_id}")
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "Checking"

    # Update
    resp = await auth_client.patch(f"/vault/accounts/{account_id}", json={"nickname": "Main Checking"})
    assert resp.status_code == 200
    assert resp.json()["nickname"] == "Main Checking"

    # Delete
    resp = await auth_client.delete(f"/vault/accounts/{account_id}")
    assert resp.status_code == 204

    # 404 after delete
    resp = await auth_client.get(f"/vault/accounts/{account_id}")
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_account_401(anon_client: AsyncClient):
    resp = await anon_client.get("/vault/accounts")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_account_404(auth_client: AsyncClient):
    resp = await auth_client.get("/vault/accounts/999999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Retirement Accounts (encryption round-trip)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_retirement_account_crud(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/retirement-accounts", json={
        "kind": "roth_ira",
        "institution": "Fidelity",
        "balance": "12500.00",
        "ytd_contribution": "3500.00",
    })
    assert resp.status_code == 201
    ra_id = resp.json()["id"]
    assert resp.json()["kind"] == "roth_ira"
    assert resp.json()["balance"] == "12500.00"

    # Verify round-trip — balance must come back as the exact Decimal string
    resp = await auth_client.get(f"/vault/retirement-accounts/{ra_id}")
    assert resp.status_code == 200
    assert resp.json()["balance"] == "12500.00"

    # Update
    resp = await auth_client.patch(f"/vault/retirement-accounts/{ra_id}", json={"ytd_contribution": "4000.00"})
    assert resp.status_code == 200
    assert resp.json()["ytd_contribution"] == "4000.00"

    # Delete
    resp = await auth_client.delete(f"/vault/retirement-accounts/{ra_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_retirement_account_401(anon_client: AsyncClient):
    resp = await anon_client.post("/vault/retirement-accounts", json={
        "kind": "roth_ira", "institution": "Fidelity",
    })
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Side Income Economics (batch use case)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_side_income_economics_crud(auth_client: AsyncClient):
    # Need a parent income stream first
    stream_resp = await auth_client.post("/vault/income-streams", json={
        "source": "DoorDash", "source_type": "gig", "cadence": "weekly",
    })
    assert stream_resp.status_code == 201
    stream_id = stream_resp.json()["id"]

    resp = await auth_client.post("/vault/side-income-economics", json={
        "income_stream_id": stream_id,
        "period_start": "2026-05-01",
        "period_end": "2026-05-07",
        "gross": "320.00",
        "hours_worked": "18.5",
        "net": "210.00",
        "net_hourly": "11.35",
    })
    assert resp.status_code == 201
    sie_id = resp.json()["id"]
    assert resp.json()["gross"] == "320.00"

    resp = await auth_client.get(f"/vault/side-income-economics/{sie_id}")
    assert resp.status_code == 200
    assert resp.json()["net_hourly"] == "11.35"

    resp = await auth_client.delete(f"/vault/side-income-economics/{sie_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Tax Deductions 1099
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tax_deduction_crud(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/tax-deductions", json={
        "tax_year": 2026,
        "category": "mileage",
        "amount": "1842.00",
        "evidence_note": "4200 miles @ IRS rate",
    })
    assert resp.status_code == 201
    td_id = resp.json()["id"]

    resp = await auth_client.get(f"/vault/tax-deductions/{td_id}")
    assert resp.status_code == 200
    assert resp.json()["category"] == "mileage"
    assert resp.json()["evidence_note"] == "4200 miles @ IRS rate"

    resp = await auth_client.delete(f"/vault/tax-deductions/{td_id}")
    assert resp.status_code == 204


@pytest.mark.asyncio
async def test_tax_deduction_404(auth_client: AsyncClient):
    resp = await auth_client.get("/vault/tax-deductions/999999")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Negotiation Milestones
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_negotiation_milestone_crud(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/negotiation-milestones", json={
        "kind": "annual_review",
        "trigger_date": "2026-08-01",
        "related_role": "Software Engineer",
        "prep_notes": "Research market rate first",
    })
    assert resp.status_code == 201
    nm_id = resp.json()["id"]
    assert resp.json()["status"] == "upcoming"

    resp = await auth_client.patch(f"/vault/negotiation-milestones/{nm_id}", json={"status": "in_progress"})
    assert resp.status_code == 200
    assert resp.json()["status"] == "in_progress"

    resp = await auth_client.delete(f"/vault/negotiation-milestones/{nm_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Career History
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_career_history_crud(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/career-history", json={
        "role": "Software Engineer",
        "employer": "Cognizant",
        "comp_total": "72000.00",
        "start_date": "2023-06-01",
        "end_date": "2025-01-15",
        "reason_for_leaving": "switched",
    })
    assert resp.status_code == 201
    ch_id = resp.json()["id"]
    assert resp.json()["employer"] == "Cognizant"

    resp = await auth_client.get(f"/vault/career-history/{ch_id}")
    assert resp.status_code == 200
    assert resp.json()["comp_total"] == "72000.00"

    resp = await auth_client.delete(f"/vault/career-history/{ch_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Net Worth Snapshots
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_net_worth_snapshot_crud(auth_client: AsyncClient):
    resp = await auth_client.post("/vault/net-worth-snapshots", json={
        "snapshot_at": "2026-05-25T00:00:00Z",
        "assets_total": "85000.00",
        "liabilities_total": "22000.00",
        "net_worth": "63000.00",
        "source": "manual",
    })
    assert resp.status_code == 201
    snap_id = resp.json()["id"]
    assert resp.json()["net_worth"] == "63000.00"

    resp = await auth_client.get(f"/vault/net-worth-snapshots/{snap_id}")
    assert resp.status_code == 200

    resp = await auth_client.delete(f"/vault/net-worth-snapshots/{snap_id}")
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Audit log is written on mutations (spot check)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_audit_log_written_on_create(auth_client: AsyncClient, session):
    from sqlalchemy import select, text

    resp = await auth_client.post("/vault/assets", json={
        "kind": "vehicle", "nickname": "Honda Civic", "value_estimate": "8500.00",
    })
    assert resp.status_code == 201
    asset_id = resp.json()["id"]

    result = await session.execute(
        text("SELECT action, entity_type, entity_id FROM audit_log WHERE entity_type='asset' AND entity_id=:eid"),
        {"eid": asset_id},
    )
    rows = result.fetchall()
    assert any(r.action == "create" for r in rows)
