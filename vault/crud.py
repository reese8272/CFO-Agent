"""Vault CRUD layer.

Every mutation (create, update, delete) writes an audit_log row via
write_audit_log(). Encryption is handled transparently by the TypeDecorators
in crypto.py — callers work with plain Python types.

Callers are responsible for committing the session.
"""
import logging
from typing import Any, TypeVar

from sqlalchemy import distinct, select
from sqlalchemy.ext.asyncio import AsyncSession

from vault.models import (
    Account,
    Asset,
    AuditLog,
    BusinessIncome,
    Card,
    CareerHistory,
    CareerPosition,
    CompBenchmark,
    Debt,
    Expense,
    Goal,
    Holdings,
    IncomeStream,
    NegotiationMilestone,
    NetWorthSnapshot,
    RealEstate,
    RetirementAccount,
    SideIncomeEconomics,
    SideIncomeEvent,
    TaxDeduction1099,
)
from vault.schemas import (
    AccountCreate, AccountUpdate,
    AssetCreate, AssetUpdate,
    BusinessIncomeCreate, BusinessIncomeUpdate,
    CardCreate, CardUpdate,
    CareerHistoryCreate, CareerHistoryUpdate,
    CareerPositionCreate, CareerPositionUpdate,
    CompBenchmarkCreate, CompBenchmarkUpdate,
    DebtCreate, DebtUpdate,
    ExpenseCreate, ExpenseUpdate,
    GoalCreate, GoalUpdate,
    HoldingsCreate, HoldingsUpdate,
    IncomeStreamCreate, IncomeStreamUpdate,
    NegotiationMilestoneCreate, NegotiationMilestoneUpdate,
    NetWorthSnapshotCreate, NetWorthSnapshotUpdate,
    RealEstateCreate, RealEstateUpdate,
    RetirementAccountCreate, RetirementAccountUpdate,
    SideIncomeEconomicsCreate, SideIncomeEconomicsUpdate,
    SideIncomeEventCreate, SideIncomeEventUpdate,
    TaxDeduction1099Create, TaxDeduction1099Update,
)

logger = logging.getLogger(__name__)


def _paginate(q, limit: int | None, offset: int):
    """Apply capped limit/offset (see routers/pagination.py) to a select."""
    if offset:
        q = q.offset(offset)
    if limit is not None:
        q = q.limit(limit)
    return q

M = TypeVar("M")


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------

def _row_snapshot(obj: Any) -> dict:
    """Return a plain-dict snapshot of an ORM row's mapped columns."""
    state = {c.key: getattr(obj, c.key) for c in obj.__mapper__.column_attrs}
    # Coerce non-JSON-serialisable types to strings so EncryptedJSON can store them
    return {k: str(v) if v is not None and not isinstance(v, (str, int, float, bool, dict, list)) else v
            for k, v in state.items()}


async def write_audit_log(
    session: AsyncSession,
    actor: str,
    action: str,
    entity_type: str,
    entity_id: int,
    before: dict | None,
    after: dict | None,
) -> None:
    entry = AuditLog(
        actor=actor,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        before_jsonb=before,
        after_jsonb=after,
    )
    session.add(entry)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

async def create_account(session: AsyncSession, data: AccountCreate, actor: str) -> Account:
    obj = Account(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "account", obj.id, None, _row_snapshot(obj))
    return obj


async def list_accounts(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Account]:
    result = await session.execute(_paginate(select(Account).order_by(Account.id), limit, offset))
    return list(result.scalars().all())


async def get_account(session: AsyncSession, account_id: int) -> Account | None:
    return await session.get(Account, account_id)


async def update_account(session: AsyncSession, account_id: int, data: AccountUpdate, actor: str) -> Account | None:
    obj = await session.get(Account, account_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "account", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_account(session: AsyncSession, account_id: int, actor: str) -> bool:
    obj = await session.get(Account, account_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "account", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

async def create_card(session: AsyncSession, data: CardCreate, actor: str) -> Card:
    obj = Card(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "card", obj.id, None, _row_snapshot(obj))
    return obj


async def list_cards(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Card]:
    result = await session.execute(_paginate(select(Card).order_by(Card.id), limit, offset))
    return list(result.scalars().all())


async def get_card(session: AsyncSession, card_id: int) -> Card | None:
    return await session.get(Card, card_id)


async def update_card(session: AsyncSession, card_id: int, data: CardUpdate, actor: str) -> Card | None:
    obj = await session.get(Card, card_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "card", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_card(session: AsyncSession, card_id: int, actor: str) -> bool:
    obj = await session.get(Card, card_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "card", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# IncomeStream
# ---------------------------------------------------------------------------

async def create_income_stream(session: AsyncSession, data: IncomeStreamCreate, actor: str) -> IncomeStream:
    obj = IncomeStream(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "income_stream", obj.id, None, _row_snapshot(obj))
    return obj


async def list_income_streams(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[IncomeStream]:
    result = await session.execute(
        _paginate(select(IncomeStream).order_by(IncomeStream.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_income_stream(session: AsyncSession, stream_id: int) -> IncomeStream | None:
    return await session.get(IncomeStream, stream_id)


async def update_income_stream(session: AsyncSession, stream_id: int, data: IncomeStreamUpdate, actor: str) -> IncomeStream | None:
    obj = await session.get(IncomeStream, stream_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "income_stream", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_income_stream(session: AsyncSession, stream_id: int, actor: str) -> bool:
    obj = await session.get(IncomeStream, stream_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "income_stream", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

async def create_expense(session: AsyncSession, data: ExpenseCreate, actor: str) -> Expense:
    obj = Expense(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "expense", obj.id, None, _row_snapshot(obj))
    return obj


async def list_expenses(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Expense]:
    result = await session.execute(_paginate(select(Expense).order_by(Expense.id), limit, offset))
    return list(result.scalars().all())


async def get_expense(session: AsyncSession, expense_id: int) -> Expense | None:
    return await session.get(Expense, expense_id)


async def update_expense(session: AsyncSession, expense_id: int, data: ExpenseUpdate, actor: str) -> Expense | None:
    obj = await session.get(Expense, expense_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "expense", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_expense(session: AsyncSession, expense_id: int, actor: str) -> bool:
    obj = await session.get(Expense, expense_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "expense", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Debt
# ---------------------------------------------------------------------------

async def create_debt(session: AsyncSession, data: DebtCreate, actor: str) -> Debt:
    obj = Debt(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "debt", obj.id, None, _row_snapshot(obj))
    return obj


async def list_debts(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Debt]:
    result = await session.execute(_paginate(select(Debt).order_by(Debt.id), limit, offset))
    return list(result.scalars().all())


async def get_debt(session: AsyncSession, debt_id: int) -> Debt | None:
    return await session.get(Debt, debt_id)


async def update_debt(session: AsyncSession, debt_id: int, data: DebtUpdate, actor: str) -> Debt | None:
    obj = await session.get(Debt, debt_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "debt", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_debt(session: AsyncSession, debt_id: int, actor: str) -> bool:
    obj = await session.get(Debt, debt_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "debt", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

async def create_asset(session: AsyncSession, data: AssetCreate, actor: str) -> Asset:
    obj = Asset(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "asset", obj.id, None, _row_snapshot(obj))
    return obj


async def list_assets(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Asset]:
    result = await session.execute(_paginate(select(Asset).order_by(Asset.id), limit, offset))
    return list(result.scalars().all())


async def get_asset(session: AsyncSession, asset_id: int) -> Asset | None:
    return await session.get(Asset, asset_id)


async def update_asset(session: AsyncSession, asset_id: int, data: AssetUpdate, actor: str) -> Asset | None:
    obj = await session.get(Asset, asset_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "asset", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_asset(session: AsyncSession, asset_id: int, actor: str) -> bool:
    obj = await session.get(Asset, asset_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "asset", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# RealEstate
# ---------------------------------------------------------------------------

async def create_real_estate(session: AsyncSession, data: RealEstateCreate, actor: str) -> RealEstate:
    obj = RealEstate(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "real_estate", obj.id, None, _row_snapshot(obj))
    return obj


async def list_real_estate(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[RealEstate]:
    result = await session.execute(
        _paginate(select(RealEstate).order_by(RealEstate.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_real_estate(session: AsyncSession, re_id: int) -> RealEstate | None:
    return await session.get(RealEstate, re_id)


async def update_real_estate(session: AsyncSession, re_id: int, data: RealEstateUpdate, actor: str) -> RealEstate | None:
    obj = await session.get(RealEstate, re_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "real_estate", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_real_estate(session: AsyncSession, re_id: int, actor: str) -> bool:
    obj = await session.get(RealEstate, re_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "real_estate", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# BusinessIncome
# ---------------------------------------------------------------------------

async def create_business_income(session: AsyncSession, data: BusinessIncomeCreate, actor: str) -> BusinessIncome:
    obj = BusinessIncome(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "business_income", obj.id, None, _row_snapshot(obj))
    return obj


async def list_business_income(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[BusinessIncome]:
    result = await session.execute(
        _paginate(select(BusinessIncome).order_by(BusinessIncome.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_business_income(session: AsyncSession, bi_id: int) -> BusinessIncome | None:
    return await session.get(BusinessIncome, bi_id)


async def update_business_income(session: AsyncSession, bi_id: int, data: BusinessIncomeUpdate, actor: str) -> BusinessIncome | None:
    obj = await session.get(BusinessIncome, bi_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "business_income", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_business_income(session: AsyncSession, bi_id: int, actor: str) -> bool:
    obj = await session.get(BusinessIncome, bi_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "business_income", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# RetirementAccount
# ---------------------------------------------------------------------------

async def create_retirement_account(session: AsyncSession, data: RetirementAccountCreate, actor: str) -> RetirementAccount:
    obj = RetirementAccount(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "retirement_account", obj.id, None, _row_snapshot(obj))
    return obj


async def list_retirement_accounts(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[RetirementAccount]:
    result = await session.execute(
        _paginate(select(RetirementAccount).order_by(RetirementAccount.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_retirement_account(session: AsyncSession, ra_id: int) -> RetirementAccount | None:
    return await session.get(RetirementAccount, ra_id)


async def update_retirement_account(session: AsyncSession, ra_id: int, data: RetirementAccountUpdate, actor: str) -> RetirementAccount | None:
    obj = await session.get(RetirementAccount, ra_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "retirement_account", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_retirement_account(session: AsyncSession, ra_id: int, actor: str) -> bool:
    obj = await session.get(RetirementAccount, ra_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "retirement_account", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------

async def create_goal(session: AsyncSession, data: GoalCreate, actor: str) -> Goal:
    obj = Goal(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "goal", obj.id, None, _row_snapshot(obj))
    return obj


async def list_goals(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[Goal]:
    result = await session.execute(_paginate(select(Goal).order_by(Goal.id), limit, offset))
    return list(result.scalars().all())


async def get_goal(session: AsyncSession, goal_id: int) -> Goal | None:
    return await session.get(Goal, goal_id)


async def update_goal(session: AsyncSession, goal_id: int, data: GoalUpdate, actor: str) -> Goal | None:
    obj = await session.get(Goal, goal_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "goal", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_goal(session: AsyncSession, goal_id: int, actor: str) -> bool:
    obj = await session.get(Goal, goal_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "goal", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# CareerPosition
# ---------------------------------------------------------------------------

async def create_career_position(session: AsyncSession, data: CareerPositionCreate, actor: str) -> CareerPosition:
    obj = CareerPosition(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "career_position", obj.id, None, _row_snapshot(obj))
    return obj


async def list_career_positions(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[CareerPosition]:
    result = await session.execute(
        _paginate(select(CareerPosition).order_by(CareerPosition.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_career_position(session: AsyncSession, cp_id: int) -> CareerPosition | None:
    return await session.get(CareerPosition, cp_id)


async def update_career_position(session: AsyncSession, cp_id: int, data: CareerPositionUpdate, actor: str) -> CareerPosition | None:
    obj = await session.get(CareerPosition, cp_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "career_position", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_career_position(session: AsyncSession, cp_id: int, actor: str) -> bool:
    obj = await session.get(CareerPosition, cp_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "career_position", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# CareerHistory
# ---------------------------------------------------------------------------

async def create_career_history(session: AsyncSession, data: CareerHistoryCreate, actor: str) -> CareerHistory:
    obj = CareerHistory(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "career_history", obj.id, None, _row_snapshot(obj))
    return obj


async def list_career_history(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[CareerHistory]:
    result = await session.execute(
        _paginate(select(CareerHistory).order_by(CareerHistory.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_career_history(session: AsyncSession, ch_id: int) -> CareerHistory | None:
    return await session.get(CareerHistory, ch_id)


async def update_career_history(session: AsyncSession, ch_id: int, data: CareerHistoryUpdate, actor: str) -> CareerHistory | None:
    obj = await session.get(CareerHistory, ch_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "career_history", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_career_history(session: AsyncSession, ch_id: int, actor: str) -> bool:
    obj = await session.get(CareerHistory, ch_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "career_history", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# CompBenchmark
# ---------------------------------------------------------------------------

async def create_comp_benchmark(session: AsyncSession, data: CompBenchmarkCreate, actor: str) -> CompBenchmark:
    obj = CompBenchmark(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "comp_benchmark", obj.id, None, _row_snapshot(obj))
    return obj


async def list_comp_benchmarks(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[CompBenchmark]:
    result = await session.execute(
        _paginate(select(CompBenchmark).order_by(CompBenchmark.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_comp_benchmark(session: AsyncSession, cb_id: int) -> CompBenchmark | None:
    return await session.get(CompBenchmark, cb_id)


async def update_comp_benchmark(session: AsyncSession, cb_id: int, data: CompBenchmarkUpdate, actor: str) -> CompBenchmark | None:
    obj = await session.get(CompBenchmark, cb_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "comp_benchmark", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_comp_benchmark(session: AsyncSession, cb_id: int, actor: str) -> bool:
    obj = await session.get(CompBenchmark, cb_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "comp_benchmark", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# SideIncomeEconomics
# ---------------------------------------------------------------------------

async def create_side_income_economics(session: AsyncSession, data: SideIncomeEconomicsCreate, actor: str) -> SideIncomeEconomics:
    obj = SideIncomeEconomics(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "side_income_economics", obj.id, None, _row_snapshot(obj))
    return obj


async def list_side_income_economics(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[SideIncomeEconomics]:
    result = await session.execute(
        _paginate(select(SideIncomeEconomics).order_by(SideIncomeEconomics.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_side_income_economics(session: AsyncSession, sie_id: int) -> SideIncomeEconomics | None:
    return await session.get(SideIncomeEconomics, sie_id)


async def update_side_income_economics(session: AsyncSession, sie_id: int, data: SideIncomeEconomicsUpdate, actor: str) -> SideIncomeEconomics | None:
    obj = await session.get(SideIncomeEconomics, sie_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "side_income_economics", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_side_income_economics(session: AsyncSession, sie_id: int, actor: str) -> bool:
    obj = await session.get(SideIncomeEconomics, sie_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "side_income_economics", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# TaxDeduction1099
# ---------------------------------------------------------------------------

async def create_tax_deduction(session: AsyncSession, data: TaxDeduction1099Create, actor: str) -> TaxDeduction1099:
    obj = TaxDeduction1099(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "tax_deduction_1099", obj.id, None, _row_snapshot(obj))
    return obj


async def list_tax_deductions(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[TaxDeduction1099]:
    result = await session.execute(
        _paginate(select(TaxDeduction1099).order_by(TaxDeduction1099.id), limit, offset)
    )
    return list(result.scalars().all())


async def get_tax_deduction(session: AsyncSession, td_id: int) -> TaxDeduction1099 | None:
    return await session.get(TaxDeduction1099, td_id)


async def update_tax_deduction(session: AsyncSession, td_id: int, data: TaxDeduction1099Update, actor: str) -> TaxDeduction1099 | None:
    obj = await session.get(TaxDeduction1099, td_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "tax_deduction_1099", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_tax_deduction(session: AsyncSession, td_id: int, actor: str) -> bool:
    obj = await session.get(TaxDeduction1099, td_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "tax_deduction_1099", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# NegotiationMilestone
# ---------------------------------------------------------------------------

async def create_negotiation_milestone(session: AsyncSession, data: NegotiationMilestoneCreate, actor: str) -> NegotiationMilestone:
    obj = NegotiationMilestone(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "negotiation_milestone", obj.id, None, _row_snapshot(obj))
    return obj


async def list_negotiation_milestones(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[NegotiationMilestone]:
    result = await session.execute(
        _paginate(
            select(NegotiationMilestone).order_by(NegotiationMilestone.trigger_date),
            limit,
            offset,
        )
    )
    return list(result.scalars().all())


async def get_negotiation_milestone(session: AsyncSession, nm_id: int) -> NegotiationMilestone | None:
    return await session.get(NegotiationMilestone, nm_id)


async def update_negotiation_milestone(session: AsyncSession, nm_id: int, data: NegotiationMilestoneUpdate, actor: str) -> NegotiationMilestone | None:
    obj = await session.get(NegotiationMilestone, nm_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "negotiation_milestone", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_negotiation_milestone(session: AsyncSession, nm_id: int, actor: str) -> bool:
    obj = await session.get(NegotiationMilestone, nm_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "negotiation_milestone", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# NetWorthSnapshot
# ---------------------------------------------------------------------------

async def create_net_worth_snapshot(session: AsyncSession, data: NetWorthSnapshotCreate, actor: str) -> NetWorthSnapshot:
    obj = NetWorthSnapshot(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "net_worth_snapshot", obj.id, None, _row_snapshot(obj))
    return obj


async def list_net_worth_snapshots(
    session: AsyncSession, *, limit: int | None = None, offset: int = 0
) -> list[NetWorthSnapshot]:
    result = await session.execute(
        _paginate(select(NetWorthSnapshot).order_by(NetWorthSnapshot.snapshot_at), limit, offset)
    )
    return list(result.scalars().all())


async def get_net_worth_snapshot(session: AsyncSession, snap_id: int) -> NetWorthSnapshot | None:
    return await session.get(NetWorthSnapshot, snap_id)


async def update_net_worth_snapshot(session: AsyncSession, snap_id: int, data: NetWorthSnapshotUpdate, actor: str) -> NetWorthSnapshot | None:
    obj = await session.get(NetWorthSnapshot, snap_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "net_worth_snapshot", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_net_worth_snapshot(session: AsyncSession, snap_id: int, actor: str) -> bool:
    obj = await session.get(NetWorthSnapshot, snap_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "net_worth_snapshot", obj.id, before, None)
    await session.delete(obj)
    return True


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

async def create_holding(session: AsyncSession, data: HoldingsCreate, actor: str) -> Holdings:
    obj = Holdings(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "holding", obj.id, None, _row_snapshot(obj))
    return obj


async def list_holdings(
    session: AsyncSession, account_id: int | None = None,
    *, limit: int | None = None, offset: int = 0
) -> list[Holdings]:
    q = select(Holdings).order_by(Holdings.account_id, Holdings.ticker)
    if account_id is not None:
        q = q.where(Holdings.account_id == account_id)
    result = await session.execute(_paginate(q, limit, offset))
    return list(result.scalars().all())


async def get_holding(session: AsyncSession, holding_id: int) -> Holdings | None:
    return await session.get(Holdings, holding_id)


async def update_holding(session: AsyncSession, holding_id: int, data: HoldingsUpdate, actor: str) -> Holdings | None:
    obj = await session.get(Holdings, holding_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "holding", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_holding(session: AsyncSession, holding_id: int, actor: str) -> bool:
    obj = await session.get(Holdings, holding_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "holding", obj.id, before, None)
    await session.delete(obj)
    return True


async def list_distinct_tickers(session: AsyncSession) -> list[str]:
    """Return each distinct ticker exactly once — used by batch price refresh."""
    result = await session.execute(
        select(distinct(Holdings.ticker)).order_by(Holdings.ticker)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# SideIncomeEvent
# ---------------------------------------------------------------------------

async def create_side_income_event(session: AsyncSession, data: SideIncomeEventCreate, actor: str) -> SideIncomeEvent:
    obj = SideIncomeEvent(**data.model_dump())
    session.add(obj)
    await session.flush()
    await write_audit_log(session, actor, "create", "side_income_event", obj.id, None, _row_snapshot(obj))
    return obj


async def list_side_income_events(
    session: AsyncSession, stream_id: int | None = None,
    *, limit: int | None = None, offset: int = 0
) -> list[SideIncomeEvent]:
    q = select(SideIncomeEvent).order_by(SideIncomeEvent.occurred_at.desc())
    if stream_id is not None:
        q = q.where(SideIncomeEvent.income_stream_id == stream_id)
    result = await session.execute(_paginate(q, limit, offset))
    return list(result.scalars().all())


async def get_side_income_event(session: AsyncSession, event_id: int) -> SideIncomeEvent | None:
    return await session.get(SideIncomeEvent, event_id)


async def update_side_income_event(session: AsyncSession, event_id: int, data: SideIncomeEventUpdate, actor: str) -> SideIncomeEvent | None:
    obj = await session.get(SideIncomeEvent, event_id)
    if obj is None:
        return None
    before = _row_snapshot(obj)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(obj, field, value)
    await session.flush()
    await write_audit_log(session, actor, "update", "side_income_event", obj.id, before, _row_snapshot(obj))
    return obj


async def delete_side_income_event(session: AsyncSession, event_id: int, actor: str) -> bool:
    obj = await session.get(SideIncomeEvent, event_id)
    if obj is None:
        return False
    before = _row_snapshot(obj)
    await write_audit_log(session, actor, "delete", "side_income_event", obj.id, before, None)
    await session.delete(obj)
    return True
