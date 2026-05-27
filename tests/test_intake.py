"""Intake wizard tests — submit, status, snapshot, refresh, archive, math.

Requires live Postgres (docker compose up -d postgres redis).
interview and extract endpoints require a live Anthropic key — skipped here,
same pattern as test_agent.py.
"""
from decimal import Decimal

import pytest
from httpx import AsyncClient, ASGITransport

from agent.principles import ROTH_IRA_LIMIT_2026
from main import app

# ---------------------------------------------------------------------------
# Shared payload — known inputs that produce verifiable math
# ---------------------------------------------------------------------------
#
# Expected outputs with this payload:
#   total_monthly_income      = 6 000.00   (monthly cadence × 1)
#   total_monthly_expenses    = 4 000.00   (monthly_spend)
#   savings_rate_pct          =    33.33   (2 000 / 6 000 × 100)
#   emergency_months_covered  =     3.00   (12 000 liquid / 4 000 expenses)
#   debt_to_income_ratio      =     0.04   (250 min-pmt / 6 000 income)
#   roth_utilization_pct      =    42.86   (3 000 / ROTH_IRA_LIMIT_2026 × 100)

_PAYLOAD = {
    "life_context": {
        "age": 30,
        "household_size": 1,
        "dependents": 0,
        "has_hsa_eligible_plan": False,
    },
    "goals": [
        {
            "title": "$1M net worth",
            "kind": "net_worth",
            "target_amount": 1_000_000,
            "deadline": "2031-12-31",
        }
    ],
    "career": {
        "current_role": "Software Engineer",
        "current_employer": "Acme Corp",
        "current_base_salary": 72_000,
    },
    "primary_income": {
        "source": "Acme Corp",
        "source_type": "w2",
        "cadence": "monthly",
        "typical_gross_amount": 6_000,
    },
    "side_incomes": [],
    "accounts": [
        {
            "nickname": "Chase Checking",
            "institution": "Chase",
            "type": "checking",
            "current_balance": 2_000,
            "is_emergency_fund": False,
        },
        {
            "nickname": "Ally Savings",
            "institution": "Ally",
            "type": "savings",
            "current_balance": 10_000,
            "is_emergency_fund": True,
        },
    ],
    "monthly_spend": 4_000,
    "debts": [
        {
            "name": "Student loan",
            "balance": 15_000,
            "apr": 5.5,
            "minimum_payment": 250,
            "strategy": "avalanche",
        }
    ],
    "retirement_accounts": [
        {
            "kind": "roth_ira",
            "institution": "Fidelity",
            "balance": 15_000,
            "ytd_contribution": 3_000,
        }
    ],
    "brokerage_accounts": [],
    "real_estate": [],
    "tax_deductions": {
        "has_1099_income": False,
        "paying_quarterly_estimated_tax": False,
    },
}


# ---------------------------------------------------------------------------
# Fixtures
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


@pytest.fixture
async def anon_client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client


# ---------------------------------------------------------------------------
# Status + snapshot — before any intake
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_before_intake(auth_client: AsyncClient):
    resp = await auth_client.get("/intake/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intake_completed"] is False
    assert body["snapshot_id"] is None
    assert body["net_worth"] is None


@pytest.mark.asyncio
async def test_snapshot_404_before_intake(auth_client: AsyncClient):
    resp = await auth_client.get("/intake/snapshot")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_submit_returns_snapshot(auth_client: AsyncClient):
    resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()
    assert "id" in body
    assert "computed_at" in body
    assert body["allocation_step"] >= 1
    assert body["income_step"] >= 1


@pytest.mark.asyncio
async def test_submit_401_without_auth(anon_client: AsyncClient, clean_db: None):
    resp = await anon_client.post("/intake/submit", json=_PAYLOAD)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_submit_populates_vault(auth_client: AsyncClient):
    await auth_client.post("/intake/submit", json=_PAYLOAD)

    # Account rows created
    accts = await auth_client.get("/vault/accounts")
    assert accts.status_code == 200
    assert len(accts.json()) == 2  # checking + savings

    # Goal row created
    goals = await auth_client.get("/vault/goals")
    assert goals.status_code == 200
    assert len(goals.json()) >= 1
    assert goals.json()[0]["title"] == "$1M net worth"

    # Income stream created
    streams = await auth_client.get("/vault/income-streams")
    assert streams.status_code == 200
    assert len(streams.json()) >= 1
    assert streams.json()[0]["source"] == "Acme Corp"

    # Debt created
    debts = await auth_client.get("/vault/debts")
    assert debts.status_code == 200
    assert len(debts.json()) == 1
    assert debts.json()[0]["name"] == "Student loan"


# ---------------------------------------------------------------------------
# Status + snapshot — after intake
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_status_after_intake(auth_client: AsyncClient):
    submit_resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    snap_id = submit_resp.json()["id"]

    resp = await auth_client.get("/intake/status")
    assert resp.status_code == 200
    body = resp.json()
    assert body["intake_completed"] is True
    assert body["completed_at"] is not None
    assert body["snapshot_id"] == snap_id


@pytest.mark.asyncio
async def test_get_snapshot_after_submit(auth_client: AsyncClient):
    submit_resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    submit_id = submit_resp.json()["id"]

    resp = await auth_client.get("/intake/snapshot")
    assert resp.status_code == 200
    assert resp.json()["id"] == submit_id


# ---------------------------------------------------------------------------
# Refresh
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_refresh_creates_new_snapshot(auth_client: AsyncClient):
    submit_resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    original_id = submit_resp.json()["id"]

    refresh_resp = await auth_client.post("/intake/snapshot/refresh")
    assert refresh_resp.status_code == 201
    new_id = refresh_resp.json()["id"]
    assert new_id != original_id

    # GET /snapshot now returns the newer one
    get_resp = await auth_client.get("/intake/snapshot")
    assert get_resp.json()["id"] == new_id


# ---------------------------------------------------------------------------
# Archive
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_archive_after_submit(auth_client: AsyncClient):
    submit_resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    snap_id = submit_resp.json()["id"]

    resp = await auth_client.get("/intake/archive")
    assert resp.status_code == 200
    entries = resp.json()
    assert len(entries) == 1
    assert entries[0]["snapshot_id"] == snap_id
    assert "submitted_at" in entries[0]


# ---------------------------------------------------------------------------
# Snapshot math — verified against known inputs
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_snapshot_math(auth_client: AsyncClient):
    resp = await auth_client.post("/intake/submit", json=_PAYLOAD)
    assert resp.status_code == 201
    body = resp.json()

    def d(key: str) -> Decimal:
        val = body.get(key)
        assert val is not None, f"{key} should not be None with this payload"
        return Decimal(str(val))

    # Monthly expenses: $4 000 living expense at monthly cadence
    assert d("total_monthly_expenses") == Decimal("4000.00")

    # Savings rate: (6 000 − 4 000) / 6 000 × 100 = 33.33
    assert d("savings_rate_pct") == Decimal("33.33")

    # Emergency fund: $12 000 liquid cash / $4 000 expenses = 3 months
    assert d("emergency_months_covered") == Decimal("3.00")

    # DTI: $250 min-payment / $6 000 income = 0.04
    assert d("debt_to_income_ratio") == Decimal("0.04")

    # Roth utilization: $3 000 YTD / ROTH_IRA_LIMIT_2026 × 100
    expected_roth = Decimal(str(round(3000 / ROTH_IRA_LIMIT_2026 * 100, 2)))
    assert d("roth_utilization_pct") == expected_roth

    # Structural checks
    assert int(body["allocation_step"]) >= 1
    assert int(body["income_step"]) >= 1
    assert body["vault_hash"] is not None
    assert len(body["vault_hash"]) == 16  # sha256[:16]
