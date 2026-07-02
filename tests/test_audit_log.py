"""Audit log is append-only at the app layer."""
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from vault.models import AuditLog, AuditLogImmutableError


@pytest.mark.asyncio
async def test_insert_succeeds(session: AsyncSession) -> None:
    entry = AuditLog(
        actor="test",
        action="create",
        entity_type="accounts",
        entity_id=1,
        before_jsonb=None,
        after_jsonb={"institution": "Bank", "type": "checking"},
    )
    session.add(entry)
    await session.flush()
    assert entry.id is not None


@pytest.mark.asyncio
async def test_orm_update_raises(session: AsyncSession) -> None:
    entry = AuditLog(
        actor="test", action="create", entity_type="accounts", entity_id=2, after_jsonb={"v": 1}
    )
    session.add(entry)
    await session.flush()

    entry.action = "update"
    with pytest.raises(AuditLogImmutableError):
        await session.flush()


@pytest.mark.asyncio
async def test_orm_delete_raises(session: AsyncSession) -> None:
    entry = AuditLog(
        actor="test", action="create", entity_type="accounts", entity_id=3, after_jsonb={"v": 1}
    )
    session.add(entry)
    await session.flush()

    await session.delete(entry)
    with pytest.raises(AuditLogImmutableError):
        await session.flush()
