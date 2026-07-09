"""CSV/OFX import unit tests (no DB) + import endpoint integration tests (live DB)."""
from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient, ASGITransport

from integrations.csv_import import compute_hash, parse_csv, _apply_mappings_raw
from main import app


def test_parse_csv_happy_path():
    csv_bytes = b"date,amount,description\n2026-01-15,-42.50,AMAZON.COM\n2026-01-16,1500.00,PAYROLL\n"
    rows = parse_csv(csv_bytes)
    assert len(rows) == 2
    assert rows[0].amount == Decimal("-42.50")
    assert rows[0].description == "AMAZON.COM"
    assert rows[0].occurred_at.year == 2026


def test_parse_csv_skips_bad_rows():
    csv_bytes = b"date,amount,description\nNOT-A-DATE,10.00,valid\n2026-03-01,25.00,good\n"
    rows = parse_csv(csv_bytes)
    assert len(rows) == 1
    assert rows[0].description == "good"


def test_compute_hash_deterministic():
    dt = datetime(2026, 1, 15, tzinfo=timezone.utc)
    h1 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    h2 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    assert h1 == h2
    assert len(h1) == 64


def test_compute_hash_differs_on_amount():
    dt = datetime(2026, 1, 15, tzinfo=timezone.utc)
    h1 = compute_hash(1, dt, Decimal("42.50"), "AMAZON")
    h2 = compute_hash(1, dt, Decimal("42.51"), "AMAZON")
    assert h1 != h2


def test_parse_ofx_import_error(monkeypatch):
    import integrations.csv_import as m
    monkeypatch.setattr(m, "_import_ofxtools", lambda: (_ for _ in ()).throw(ImportError()))
    with pytest.raises(RuntimeError):
        m.parse_ofx(b"garbage")


def test_parse_ofx_defuses_stdlib_xml():
    """parse_ofx must defuse stdlib XML — entity expansion is refused process-wide."""
    import xml.etree.ElementTree as ET
    from defusedxml.common import EntitiesForbidden
    from integrations.csv_import import parse_ofx

    malicious = b"<?xml version='1.0'?><!DOCTYPE ofx [<!ENTITY a 'x'>]><OFX>&a;</OFX>"
    with pytest.raises(Exception):
        parse_ofx(malicious)  # refused or rejected as invalid OFX — never expanded
    with pytest.raises(EntitiesForbidden):
        ET.fromstring("<!DOCTYPE d [<!ENTITY e 'x'>]><d>&e;</d>")


def test_category_mapping_applied():
    mapping = MagicMock()
    mapping.pattern = "amazon"
    mapping.category = "Shopping"
    result = _apply_mappings_raw("AMAZON.COM purchase", [mapping])
    assert result == "Shopping"


# ---------------------------------------------------------------------------
# Endpoint integration — live DB
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


@pytest.mark.asyncio
async def test_import_unknown_account_returns_404(auth_client: AsyncClient):
    """An unknown account_id must be a 404 client error, not an IntegrityError 500."""
    resp = await auth_client.post(
        "/import/transactions?account_id=999999",
        files={"file": ("stmt.csv", b"date,amount,description\n2026-01-15,-1.00,X\n", "text/csv")},
    )
    assert resp.status_code == 404
