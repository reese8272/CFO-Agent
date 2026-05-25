"""ORM model tests — verify the schema is intact and encryption round-trips through Postgres."""
from decimal import Decimal

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.ext.asyncio import AsyncSession

import auth  # noqa: F401 — register the User model with Base.metadata
import memory.models  # noqa: F401
import vault.models  # noqa: F401
from db import Base, get_engine
from vault.models import Account, RetirementAccount

EXPECTED_TABLES = {
    "accounts",
    "assets",
    "audit_log",
    "business_income",
    "cards",
    "career_history",
    "career_position",
    "comp_benchmarks",
    "conversations",
    "debts",
    "decisions",
    "expenses",
    "goals",
    "income_streams",
    "messages",
    "negotiation_milestones",
    "net_worth_snapshots",
    "patterns",
    "real_estate",
    "retirement_accounts",
    "side_income_economics",
    "tax_deductions_1099",
    "users",
}


@pytest.mark.asyncio
async def test_metadata_registers_all_expected_tables() -> None:
    declared = set(Base.metadata.tables.keys())
    missing = EXPECTED_TABLES - declared
    extras = declared - EXPECTED_TABLES
    assert not missing, f"missing tables in Base.metadata: {missing}"
    assert not extras, f"unexpected tables in Base.metadata: {extras}"


@pytest.mark.asyncio
async def test_all_expected_tables_present_in_database() -> None:
    engine = get_engine()
    async with engine.connect() as conn:
        names = await conn.run_sync(lambda c: inspect(c).get_table_names())
    missing = EXPECTED_TABLES - set(names)
    assert not missing, f"missing tables in DB: {missing}"


@pytest.mark.asyncio
async def test_account_round_trip_encrypts_balance(session: AsyncSession) -> None:
    """Write a Decimal balance, read it back, confirm Python sees Decimal and DB stores ciphertext."""
    account = Account(
        type="checking",
        institution="Test Bank",
        nickname="Round-trip",
        current_balance=Decimal("12345.67"),
        status="active",
    )
    session.add(account)
    await session.flush()
    account_id = account.id

    session.expire_all()
    fetched = (await session.execute(select(Account).where(Account.id == account_id))).scalar_one()
    assert fetched.current_balance == Decimal("12345.67")
    assert isinstance(fetched.current_balance, Decimal)

    raw = (
        await session.execute(
            text("SELECT current_balance_encrypted FROM accounts WHERE id = :id"),
            {"id": account_id},
        )
    ).scalar_one()
    assert isinstance(raw, (bytes, memoryview))
    raw_bytes = bytes(raw)
    assert b"12345.67" not in raw_bytes
    assert raw_bytes.startswith(b"gAAAAA")


@pytest.mark.asyncio
async def test_null_encrypted_columns_round_trip(session: AsyncSession) -> None:
    account = RetirementAccount(
        kind="roth_ira",
        institution="Test Brokerage",
        ytd_contribution=None,
        balance=None,
    )
    session.add(account)
    await session.flush()
    account_id = account.id

    session.expire_all()
    fetched = (
        await session.execute(
            select(RetirementAccount).where(RetirementAccount.id == account_id)
        )
    ).scalar_one()
    assert fetched.ytd_contribution is None
    assert fetched.balance is None
