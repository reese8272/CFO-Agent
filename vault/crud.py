"""Generic async CRUD with transparent audit logging.

Every entity in the vault shares the same shape (integer PK, encrypted
columns via TypeDecorators, optional server-computed fields), so the create /
read / list / update / delete logic lives here once and is parameterized by
the model. The router factory in routers/vault.py wires each entity to these
functions.

Every mutation (create / update / delete) writes an append-only `audit_log`
row whose `before`/`after` snapshots are themselves Fernet-encrypted at rest
(EncryptedJSON column). This is the one place mutations happen, so no endpoint
can forget to audit.

`compute` callbacks derive trivial arithmetic fields (equity, net margin, net
hourly, net worth) server-side on write; they read the full intended row state
and return the fields to set. Rolling-window / tax-constant fields are left
null for their owning issues (5 / 8) to populate.
"""
import logging
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Callable

from sqlalchemy import inspect as sa_inspect, select
from sqlalchemy.ext.asyncio import AsyncSession

from db import Base
from vault.models import AuditLog

logger = logging.getLogger(__name__)

ComputeFn = Callable[[dict[str, Any]], dict[str, Any]]

_CENTS = Decimal("0.01")


def _column_keys(model: type) -> list[str]:
    return [attr.key for attr in sa_inspect(model).mapper.column_attrs]


def _jsonable(value: Any) -> Any:
    """Coerce a column value into something json.dumps can serialize for audit."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return value


def _snapshot(instance: Base) -> dict[str, Any]:
    return {key: _jsonable(getattr(instance, key)) for key in _column_keys(type(instance))}


def _write_audit(
    session: AsyncSession,
    *,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict[str, Any] | None,
    after: dict[str, Any] | None,
) -> None:
    session.add(
        AuditLog(
            actor=actor,
            action=action,
            entity_type=entity_type,
            entity_id=entity_id,
            before_jsonb=before,
            after_jsonb=after,
        )
    )
    logger.info("audit %s %s id=%s actor=%s", action, entity_type, entity_id, actor)


def _apply_compute(instance: Base, compute: ComputeFn | None) -> None:
    if compute is None:
        return
    state = {key: getattr(instance, key, None) for key in _column_keys(type(instance))}
    for key, value in compute(state).items():
        setattr(instance, key, value)


async def create_entity(
    session: AsyncSession,
    model: type[Base],
    data: dict[str, Any],
    *,
    actor: str,
    entity_type: str,
    compute: ComputeFn | None = None,
) -> Base:
    instance = model(**data)
    _apply_compute(instance, compute)
    session.add(instance)
    await session.flush()  # assign PK before snapshotting
    _write_audit(
        session,
        actor=actor,
        action="create",
        entity_type=entity_type,
        entity_id=instance.id,
        before=None,
        after=_snapshot(instance),
    )
    await session.commit()
    await session.refresh(instance)
    return instance


async def get_entity(session: AsyncSession, model: type[Base], entity_id: int) -> Base | None:
    return await session.get(model, entity_id)


async def list_entities(
    session: AsyncSession, model: type[Base], *, limit: int = 500, offset: int = 0
) -> list[Base]:
    result = await session.execute(
        select(model).order_by(model.id.desc()).limit(limit).offset(offset)
    )
    return list(result.scalars().all())


async def get_last_entity(session: AsyncSession, model: type[Base]) -> Base | None:
    result = await session.execute(select(model).order_by(model.id.desc()).limit(1))
    return result.scalars().first()


async def update_entity(
    session: AsyncSession,
    model: type[Base],
    entity_id: int,
    data: dict[str, Any],
    *,
    actor: str,
    entity_type: str,
    compute: ComputeFn | None = None,
) -> Base | None:
    instance = await session.get(model, entity_id)
    if instance is None:
        return None
    before = _snapshot(instance)
    for key, value in data.items():
        setattr(instance, key, value)
    _apply_compute(instance, compute)
    _write_audit(
        session,
        actor=actor,
        action="update",
        entity_type=entity_type,
        entity_id=instance.id,
        before=before,
        after=_snapshot(instance),
    )
    await session.commit()
    await session.refresh(instance)
    return instance


async def delete_entity(
    session: AsyncSession,
    model: type[Base],
    entity_id: int,
    *,
    actor: str,
    entity_type: str,
) -> bool:
    instance = await session.get(model, entity_id)
    if instance is None:
        return False
    before = _snapshot(instance)
    await session.delete(instance)
    _write_audit(
        session,
        actor=actor,
        action="delete",
        entity_type=entity_type,
        entity_id=entity_id,
        before=before,
        after=None,
    )
    await session.commit()
    return True


# --- computed-field callbacks (trivial arithmetic, derived on write) ---


def _sum_money(blob: dict[str, Any] | None) -> Decimal:
    total = Decimal(0)
    for value in (blob or {}).values():
        total += Decimal(str(value))
    return total


def _stringify_money(blob: dict[str, Any] | None) -> dict[str, str] | None:
    """EncryptedJSON serializes with json.dumps, which can't encode Decimal.

    Store money breakdowns as Decimal-preserving strings; the Out schema reads
    them back into Decimal.
    """
    if not blob:
        return blob
    return {key: str(Decimal(str(value))) for key, value in blob.items()}


def compute_real_estate(state: dict[str, Any]) -> dict[str, Any]:
    current_value = state.get("current_value")
    if current_value is None:
        return {"equity_estimate": None}
    mortgage = state.get("mortgage_balance") or Decimal(0)
    return {"equity_estimate": current_value - mortgage}


def compute_business_income(state: dict[str, Any]) -> dict[str, Any]:
    revenue = state.get("monthly_revenue")
    if revenue is None:
        return {"net_margin": None}
    expenses = state.get("monthly_expenses") or Decimal(0)
    return {"net_margin": revenue - expenses}


def compute_side_income(state: dict[str, Any]) -> dict[str, Any]:
    expenses = state.get("expenses_jsonb")
    out: dict[str, Any] = {"expenses_jsonb": _stringify_money(expenses)}
    gross = state.get("gross")
    if gross is None:
        out["net"] = None
        out["net_hourly"] = None
        return out
    net = gross - _sum_money(expenses)
    out["net"] = net
    hours = state.get("hours_worked")
    out["net_hourly"] = (net / hours).quantize(_CENTS) if hours else None
    return out


def compute_net_worth(state: dict[str, Any]) -> dict[str, Any]:
    assets = state.get("assets_total")
    liabilities = state.get("liabilities_total")
    out: dict[str, Any] = {
        "asset_breakdown_jsonb": _stringify_money(state.get("asset_breakdown_jsonb")),
        "liability_breakdown_jsonb": _stringify_money(state.get("liability_breakdown_jsonb")),
    }
    if assets is None and liabilities is None:
        out["net_worth"] = None
    else:
        out["net_worth"] = (assets or Decimal(0)) - (liabilities or Decimal(0))
    return out
