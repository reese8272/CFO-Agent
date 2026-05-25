"""Vault CRUD endpoints — one REST resource per vault entity.

A single router factory (`make_crud_router`) turns each entry in `ENTITIES`
into a five-verb resource (create / list / get / update / delete), all behind
`get_current_user`. The behavior (encryption, audit, computed fields) lives in
vault/crud.py; this module only wires models + schemas + routes.

NOTE: do not add `from __future__ import annotations` here — FastAPI needs the
per-entity Pydantic classes to be live objects in the handler signatures, not
stringized annotations.
"""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel, ConfigDict, create_model
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from db import get_session
from vault import crud, models, schemas


def make_patch_schema(name: str, in_schema: type[BaseModel]) -> type[BaseModel]:
    """Derive an all-optional PATCH schema from a create schema."""
    fields = {
        field_name: (Optional[field.annotation], None)
        for field_name, field in in_schema.model_fields.items()
    }
    return create_model(name, __config__=ConfigDict(extra="forbid"), **fields)


class EntitySpec:
    """Binds an ORM model to its schemas, route prefix, and compute callback."""

    def __init__(self, model, in_schema, out_schema, *, prefix, compute=None):
        self.model = model
        self.in_schema = in_schema
        self.out_schema = out_schema
        self.patch_schema = make_patch_schema(f"{model.__name__}Patch", in_schema)
        self.prefix = prefix
        self.entity_type = model.__tablename__
        self.compute = compute


ENTITIES: list[EntitySpec] = [
    EntitySpec(models.Account, schemas.AccountIn, schemas.AccountOut, prefix="accounts"),
    EntitySpec(models.Card, schemas.CardIn, schemas.CardOut, prefix="cards"),
    EntitySpec(
        models.IncomeStream, schemas.IncomeStreamIn, schemas.IncomeStreamOut,
        prefix="income_streams",
    ),
    EntitySpec(models.Expense, schemas.ExpenseIn, schemas.ExpenseOut, prefix="expenses"),
    EntitySpec(models.Debt, schemas.DebtIn, schemas.DebtOut, prefix="debts"),
    EntitySpec(models.Asset, schemas.AssetIn, schemas.AssetOut, prefix="assets"),
    EntitySpec(
        models.RealEstate, schemas.RealEstateIn, schemas.RealEstateOut,
        prefix="real_estate", compute=crud.compute_real_estate,
    ),
    EntitySpec(
        models.BusinessIncome, schemas.BusinessIncomeIn, schemas.BusinessIncomeOut,
        prefix="business_income", compute=crud.compute_business_income,
    ),
    EntitySpec(
        models.RetirementAccount, schemas.RetirementAccountIn, schemas.RetirementAccountOut,
        prefix="retirement_accounts",
    ),
    EntitySpec(models.Goal, schemas.GoalIn, schemas.GoalOut, prefix="goals"),
    EntitySpec(
        models.CareerPosition, schemas.CareerPositionIn, schemas.CareerPositionOut,
        prefix="career_position",
    ),
    EntitySpec(
        models.CareerHistory, schemas.CareerHistoryIn, schemas.CareerHistoryOut,
        prefix="career_history",
    ),
    EntitySpec(
        models.CompBenchmark, schemas.CompBenchmarkIn, schemas.CompBenchmarkOut,
        prefix="comp_benchmarks",
    ),
    EntitySpec(
        models.SideIncomeEconomics, schemas.SideIncomeEconomicsIn,
        schemas.SideIncomeEconomicsOut, prefix="side_income_economics",
        compute=crud.compute_side_income,
    ),
    EntitySpec(
        models.TaxDeduction1099, schemas.TaxDeduction1099In, schemas.TaxDeduction1099Out,
        prefix="tax_deductions_1099",
    ),
    EntitySpec(
        models.NegotiationMilestone, schemas.NegotiationMilestoneIn,
        schemas.NegotiationMilestoneOut, prefix="negotiation_milestones",
    ),
    EntitySpec(
        models.NetWorthSnapshot, schemas.NetWorthSnapshotIn, schemas.NetWorthSnapshotOut,
        prefix="net_worth_snapshots", compute=crud.compute_net_worth,
    ),
]


def make_crud_router(spec: EntitySpec) -> APIRouter:
    router = APIRouter(prefix=f"/{spec.prefix}", tags=[spec.prefix])
    model = spec.model
    entity_type = spec.entity_type
    compute = spec.compute
    InModel = spec.in_schema
    PatchModel = spec.patch_schema
    OutModel = spec.out_schema

    @router.post("", response_model=OutModel, status_code=status.HTTP_201_CREATED)
    async def create(
        payload: InModel,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
    ):
        return await crud.create_entity(
            session, model, payload.model_dump(exclude_unset=True),
            actor=user.username, entity_type=entity_type, compute=compute,
        )

    @router.get("", response_model=list[OutModel])
    async def list_all(
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
    ):
        return await crud.list_entities(session, model)

    @router.get("/{entity_id}", response_model=OutModel)
    async def get_one(
        entity_id: int,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
    ):
        obj = await crud.get_entity(session, model, entity_id)
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return obj

    @router.patch("/{entity_id}", response_model=OutModel)
    async def update(
        entity_id: int,
        payload: PatchModel,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
    ):
        obj = await crud.update_entity(
            session, model, entity_id, payload.model_dump(exclude_unset=True),
            actor=user.username, entity_type=entity_type, compute=compute,
        )
        if obj is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return obj

    @router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete(
        entity_id: int,
        session: AsyncSession = Depends(get_session),
        user: User = Depends(get_current_user),
    ):
        deleted = await crud.delete_entity(
            session, model, entity_id, actor=user.username, entity_type=entity_type,
        )
        if not deleted:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    return router


router = APIRouter(tags=["vault"])
for _spec in ENTITIES:
    router.include_router(make_crud_router(_spec))
