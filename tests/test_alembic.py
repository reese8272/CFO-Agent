"""Verify Alembic migrations apply cleanly from empty to head."""
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import inspect

from db import get_engine


@pytest.mark.asyncio
async def test_alembic_head_matches_applied_revision() -> None:
    """The DB's alembic_version row matches the latest revision in migrations/versions/."""
    cfg = Config("/home/user/CFO-Agent/alembic.ini")
    script = ScriptDirectory.from_config(cfg)
    head_revisions = script.get_heads()
    assert len(head_revisions) == 1, f"expected single head, got {head_revisions}"

    engine = get_engine()
    async with engine.connect() as conn:
        applied = await conn.run_sync(
            lambda c: c.execute(__import__("sqlalchemy").text("SELECT version_num FROM alembic_version")).scalar()
        )
    assert applied == head_revisions[0], (
        f"DB applied revision {applied} but head is {head_revisions[0]} — "
        "run `alembic upgrade head` to bring the test DB current"
    )


@pytest.mark.asyncio
async def test_all_expected_tables_after_upgrade() -> None:
    expected = {
        "accounts", "assets", "audit_log", "business_income", "cards",
        "career_history", "career_position", "comp_benchmarks", "conversations",
        "debts", "decisions", "expenses", "goals", "income_streams", "messages",
        "negotiation_milestones", "net_worth_snapshots", "patterns", "real_estate",
        "retirement_accounts", "side_income_economics", "tax_deductions_1099",
    }
    engine = get_engine()
    async with engine.connect() as conn:
        names = set(await conn.run_sync(lambda c: inspect(c).get_table_names()))
    missing = expected - names
    assert not missing, f"missing after upgrade: {missing}"
