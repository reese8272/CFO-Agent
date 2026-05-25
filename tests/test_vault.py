"""Vault CRUD surface tests.

Covers the Issue 4 acceptance criteria: every entity CRUDable via API, audit
row on every mutation, computed fields derived on write, the ergonomic HTMX
forms (render + persist + duplicate-last-entry + batch), and 404/401 paths.

Requires live Postgres + Redis (no DB mocking, per CLAUDE.md). The `client`
and `auth_headers` fixtures live in conftest.py.
"""
import json

from sqlalchemy import create_engine, text

import pytest
from fastapi.testclient import TestClient

from config import get_settings
from crypto import decrypt


def _audit_count(action: str, entity_type: str) -> int:
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        n = conn.execute(
            text(
                "SELECT count(*) FROM audit_log WHERE action = :a AND entity_type = :t"
            ),
            {"a": action, "t": entity_type},
        ).scalar()
    engine.dispose()
    return n


# --- auth ---


def test_protected_without_token_401(client: TestClient, auth_headers) -> None:
    assert client.get("/accounts").status_code == 401


# --- core CRUD lifecycle + encryption round-trip ---


def test_account_crud_lifecycle(client: TestClient, auth_headers) -> None:
    created = client.post(
        "/accounts",
        headers=auth_headers,
        json={"type": "checking", "institution": "Ally", "nickname": "Main",
              "current_balance": "1500.50"},
    )
    assert created.status_code == 201
    body = created.json()
    aid = body["id"]
    assert body["status"] == "active"  # column default applied (omitted on create)
    assert body["current_balance"] == "1500.50"

    got = client.get(f"/accounts/{aid}", headers=auth_headers)
    assert got.status_code == 200
    assert got.json()["current_balance"] == "1500.50"  # decrypt round-trip

    listing = client.get("/accounts", headers=auth_headers)
    assert listing.status_code == 200 and len(listing.json()) == 1

    patched = client.patch(
        f"/accounts/{aid}", headers=auth_headers, json={"current_balance": "1600.00"}
    )
    assert patched.status_code == 200 and patched.json()["current_balance"] == "1600.00"

    assert client.delete(f"/accounts/{aid}", headers=auth_headers).status_code == 204
    assert client.get(f"/accounts/{aid}", headers=auth_headers).status_code == 404


def test_unknown_id_returns_404(client: TestClient, auth_headers) -> None:
    assert client.get("/accounts/999999", headers=auth_headers).status_code == 404
    assert client.patch(
        "/accounts/999999", headers=auth_headers, json={"nickname": "x"}
    ).status_code == 404
    assert client.delete("/accounts/999999", headers=auth_headers).status_code == 404


def test_extra_field_rejected(client: TestClient, auth_headers) -> None:
    resp = client.post(
        "/accounts",
        headers=auth_headers,
        json={"type": "checking", "institution": "Ally", "nickname": "Main",
              "surprise": "nope"},
    )
    assert resp.status_code == 422


# --- audit ---


def test_create_and_delete_write_audit_rows(client: TestClient, auth_headers) -> None:
    created = client.post(
        "/debts", headers=auth_headers, json={"name": "Card debt", "balance": "2000"}
    )
    did = created.json()["id"]
    assert _audit_count("create", "debts") == 1

    client.patch(f"/debts/{did}", headers=auth_headers, json={"balance": "1800"})
    assert _audit_count("update", "debts") == 1

    client.delete(f"/debts/{did}", headers=auth_headers)
    assert _audit_count("delete", "debts") == 1

    # delete snapshot captured the pre-image, encrypted at rest (Fernet ciphertext)
    engine = create_engine(get_settings().database_url)
    with engine.connect() as conn:
        raw = conn.execute(
            text("SELECT before_jsonb FROM audit_log WHERE action='delete' AND entity_type='debts'")
        ).scalar()
    engine.dispose()
    assert raw is not None
    assert bytes(raw).startswith(b"gAAAAA")  # not plaintext
    before = json.loads(decrypt(bytes(raw)))
    assert before["name"] == "Card debt"


# --- computed fields (derived on write) ---


def test_real_estate_equity_computed(client: TestClient, auth_headers) -> None:
    resp = client.post(
        "/real_estate",
        headers=auth_headers,
        json={"property_type": "primary", "current_value": "500000",
              "mortgage_balance": "300000"},
    )
    assert resp.json()["equity_estimate"] == "200000"


def test_business_net_margin_computed(client: TestClient, auth_headers) -> None:
    resp = client.post(
        "/business_income",
        headers=auth_headers,
        json={"business_name": "Biz", "entity_type": "llc",
              "monthly_revenue": "10000", "monthly_expenses": "3500"},
    )
    assert resp.json()["net_margin"] == "6500"


def test_side_income_net_and_hourly_computed(client: TestClient, auth_headers) -> None:
    stream = client.post(
        "/income_streams", headers=auth_headers,
        json={"source": "DoorDash", "source_type": "gig", "cadence": "weekly"},
    ).json()
    resp = client.post(
        "/side_income_economics",
        headers=auth_headers,
        json={"income_stream_id": stream["id"], "period_start": "2026-05-01",
              "period_end": "2026-05-07", "gross": "300", "hours_worked": "10",
              "expenses_jsonb": {"gas": "40", "food": "20"}},
    )
    body = resp.json()
    assert body["net"] == "240"
    assert body["net_hourly"] == "24.00"


def test_net_worth_computed(client: TestClient, auth_headers) -> None:
    resp = client.post(
        "/net_worth_snapshots",
        headers=auth_headers,
        json={"snapshot_at": "2026-05-25T00:00:00Z", "assets_total": "400000",
              "liabilities_total": "150000"},
    )
    assert resp.json()["net_worth"] == "250000"


# --- every entity is CRUDable ---

_MINIMAL = {
    "cards": {"issuer": "Visa", "network": "visa"},          # account_id injected
    "expenses": {"name": "Rent", "category": "housing", "cadence": "monthly"},
    "assets": {"kind": "vehicle", "nickname": "Car"},
    "real_estate": {"property_type": "primary"},
    "business_income": {"business_name": "Biz", "entity_type": "llc"},
    "retirement_accounts": {"kind": "roth_ira", "institution": "Fidelity"},
    "goals": {"title": "Emergency", "kind": "emergency_fund"},
    "career_position": {"current_role": "Eng", "current_employer": "Co"},
    "career_history": {"role": "Eng", "employer": "Old", "start_date": "2020-01-01"},
    "comp_benchmarks": {"role": "Eng", "metro": "NYC", "source": "levels_fyi",
                        "as_of_date": "2026-01-01"},
    "side_income_economics": {"period_start": "2026-05-01", "period_end": "2026-05-07"},
    "tax_deductions_1099": {"tax_year": 2026, "category": "mileage"},
    "negotiation_milestones": {"kind": "annual_review", "trigger_date": "2026-12-01"},
    "net_worth_snapshots": {"snapshot_at": "2026-05-25T00:00:00Z"},
}


def test_every_entity_createable(client: TestClient, auth_headers) -> None:
    account = client.post(
        "/accounts", headers=auth_headers,
        json={"type": "checking", "institution": "X", "nickname": "N"},
    ).json()
    stream = client.post(
        "/income_streams", headers=auth_headers,
        json={"source": "Job", "source_type": "w2", "cadence": "monthly"},
    ).json()

    for prefix, payload in _MINIMAL.items():
        body = dict(payload)
        if prefix == "cards":
            body["account_id"] = account["id"]
        if prefix == "side_income_economics":
            body["income_stream_id"] = stream["id"]
        created = client.post(f"/{prefix}", headers=auth_headers, json=body)
        assert created.status_code == 201, f"{prefix}: {created.text}"
        entity_id = created.json()["id"]
        assert client.get(f"/{prefix}/{entity_id}", headers=auth_headers).status_code == 200


# --- HTMX UI ---


def test_ui_page_served(client: TestClient) -> None:
    resp = client.get("/ui/vault")
    assert resp.status_code == 200
    assert "htmx.org" in resp.text and "Personal CFO" in resp.text


@pytest.mark.parametrize(
    "prefix,field",
    [
        ("cards", "issuer"),
        ("retirement_accounts", "institution"),
        ("career_position", "current_role"),
        ("side_income_economics", "income_stream_id"),
        ("tax_deductions_1099", "tax_year"),
    ],
)
def test_ui_form_renders(client: TestClient, auth_headers, prefix, field) -> None:
    resp = client.get(f"/ui/{prefix}/form", headers=auth_headers)
    assert resp.status_code == 200
    assert f'name="{field}"' in resp.text


def test_ui_create_persists_and_lists(client: TestClient, auth_headers) -> None:
    created = client.post(
        "/ui/tax_deductions_1099",
        headers=auth_headers,
        data={"tax_year": "2026", "category": "mileage", "amount": "123.45"},
    )
    assert created.status_code == 200
    assert "123.45" in created.text and "delete" in created.text

    listing = client.get("/ui/tax_deductions_1099/list", headers=auth_headers)
    assert "123.45" in listing.text

    # persisted through the JSON API too
    api = client.get("/tax_deductions_1099", headers=auth_headers).json()
    assert len(api) == 1 and api[0]["amount"] == "123.45"


def test_ui_duplicate_last_prefills(client: TestClient, auth_headers) -> None:
    client.post(
        "/ui/retirement_accounts",
        headers=auth_headers,
        data={"kind": "roth_ira", "institution": "Vanguard", "balance": "42000"},
    )
    form = client.get(
        "/ui/retirement_accounts/form?from_last=1", headers=auth_headers
    )
    assert 'value="Vanguard"' in form.text
    assert 'value="42000"' in form.text


def test_ui_batch_create(client: TestClient, auth_headers) -> None:
    stream = client.post(
        "/income_streams", headers=auth_headers,
        json={"source": "DoorDash", "source_type": "gig", "cadence": "weekly"},
    ).json()
    resp = client.post(
        "/ui/side_income_economics/batch",
        headers=auth_headers,
        data={
            "income_stream_id-0": stream["id"], "period_start-0": "2026-05-01",
            "period_end-0": "2026-05-07", "gross-0": "300", "hours_worked-0": "10",
            "income_stream_id-1": stream["id"], "period_start-1": "2026-05-08",
            "period_end-1": "2026-05-14", "gross-1": "275", "hours_worked-1": "9",
        },
    )
    assert resp.status_code == 200
    assert resp.text.count('class="row"') == 2
    assert len(client.get("/side_income_economics", headers=auth_headers).json()) == 2
