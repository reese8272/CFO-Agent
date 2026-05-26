"""Intake router — financial onboarding wizard endpoints.

POST /intake/submit  — accepts full intake payload, populates vault, archives submission,
                       computes initial financial snapshot
GET  /intake/status  — returns whether intake is complete + latest snapshot summary
GET  /intake/snapshot — returns latest financial snapshot (full analysis)
POST /intake/snapshot/refresh — recomputes snapshot from current vault state
GET  /intake/archive — returns the original intake submission
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from db import get_session
from vault.financial_snapshot import compute_and_store_snapshot
from vault.models import (
    Account, CareerPosition, Debt, Expense, FinancialSnapshot, Goal,
    Holdings, IncomeStream, IntakeSubmission, RealEstate, RetirementAccount,
    SideIncomeEconomics, TaxDeduction1099, UserProfile,
)
from vault.schemas import FinancialSnapshotRead

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intake", tags=["intake"])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[User, Depends(get_current_user)]


# ---------------------------------------------------------------------------
# Intake payload schema
# ---------------------------------------------------------------------------

class LifeContextPayload(BaseModel):
    age: Optional[int] = None
    household_size: int = 1
    dependents: int = 0
    state_of_residence: Optional[str] = None
    tax_filing_status: Optional[str] = None
    last_year_agi: Optional[Decimal] = None
    has_hsa_eligible_plan: bool = False


class GoalPayload(BaseModel):
    title: str
    kind: str
    target_amount: Optional[Decimal] = None
    deadline: Optional[str] = None
    priority: Optional[int] = None


class CareerPayload(BaseModel):
    current_role: str
    current_employer: str
    current_base_salary: Optional[Decimal] = None
    current_bonus: Optional[Decimal] = None
    current_equity_annual: Optional[Decimal] = None
    target_comp: Optional[Decimal] = None
    target_date: Optional[str] = None


class PrimaryIncomePayload(BaseModel):
    source: str
    source_type: str = "w2"
    cadence: str = "biweekly"
    typical_gross_amount: Optional[Decimal] = None


class SideIncomePayload(BaseModel):
    source: str
    source_type: str = "gig"
    cadence: str = "monthly"
    typical_gross_amount: Optional[Decimal] = None
    hours_per_week: Optional[Decimal] = None
    monthly_expenses: Optional[Decimal] = None


class AccountPayload(BaseModel):
    nickname: str
    institution: str
    type: str = "checking"
    current_balance: Optional[Decimal] = None
    is_emergency_fund: bool = False


class DebtPayload(BaseModel):
    name: str
    balance: Optional[Decimal] = None
    apr: Optional[Decimal] = None
    minimum_payment: Optional[Decimal] = None
    strategy: str = "avalanche"


class RetirementAccountPayload(BaseModel):
    kind: str
    institution: str
    balance: Optional[Decimal] = None
    ytd_contribution: Optional[Decimal] = None
    employer_match_pct: Optional[Decimal] = None
    employer_match_up_to_pct: Optional[Decimal] = None


class HoldingPayload(BaseModel):
    ticker: str
    share_count: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None


class BrokerageAccountPayload(BaseModel):
    nickname: str
    institution: str
    current_balance: Optional[Decimal] = None
    holdings: list[HoldingPayload] = []


class RealEstatePayload(BaseModel):
    property_type: str = "primary"
    address: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    mortgage_balance: Optional[Decimal] = None
    mortgage_apr: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    monthly_rent: Optional[Decimal] = None


class TaxDeductionsPayload(BaseModel):
    has_1099_income: bool = False
    business_miles_ytd: Optional[Decimal] = None
    home_office_sqft: Optional[int] = None
    equipment_purchased: Optional[Decimal] = None
    education_training: Optional[Decimal] = None
    other_deductible: Optional[Decimal] = None
    paying_quarterly_estimated_tax: bool = False


class IntakeSubmitPayload(BaseModel):
    life_context: LifeContextPayload
    goals: list[GoalPayload] = []
    career: Optional[CareerPayload] = None
    primary_income: Optional[PrimaryIncomePayload] = None
    side_incomes: list[SideIncomePayload] = []
    accounts: list[AccountPayload] = []
    monthly_spend: Optional[Decimal] = None
    debts: list[DebtPayload] = []
    retirement_accounts: list[RetirementAccountPayload] = []
    brokerage_accounts: list[BrokerageAccountPayload] = []
    real_estate: list[RealEstatePayload] = []
    tax_deductions: Optional[TaxDeductionsPayload] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status")
async def intake_status(
    session: Session,
    current_user: CurrentUser,
) -> dict:
    profile = (await session.execute(select(UserProfile))).scalar_one_or_none()
    snap = (
        await session.execute(
            select(FinancialSnapshot).order_by(FinancialSnapshot.computed_at.desc()).limit(1)
        )
    ).scalar_one_or_none()

    completed = profile is not None and profile.intake_completed_at is not None
    return {
        "intake_completed": completed,
        "completed_at": profile.intake_completed_at.isoformat() if (profile and profile.intake_completed_at) else None,
        "snapshot_id": snap.id if snap else None,
        "net_worth": str(snap.net_worth) if snap and snap.net_worth else None,
        "allocation_step": snap.allocation_step if snap else None,
        "income_step": snap.income_step if snap else None,
    }


@router.post("/submit", response_model=FinancialSnapshotRead, status_code=201)
async def submit_intake(
    body: IntakeSubmitPayload,
    session: Session,
    current_user: CurrentUser,
) -> FinancialSnapshot:
    from datetime import date as date_type

    lc = body.life_context

    # --- upsert UserProfile ---
    profile = (await session.execute(select(UserProfile))).scalar_one_or_none()
    if profile is None:
        profile = UserProfile()
        session.add(profile)
    profile.age = lc.age
    profile.household_size = lc.household_size
    profile.dependents = lc.dependents
    profile.state_of_residence = lc.state_of_residence
    profile.tax_filing_status = lc.tax_filing_status
    profile.last_year_agi = lc.last_year_agi
    profile.has_hsa_eligible_plan = lc.has_hsa_eligible_plan
    await session.flush()

    # --- goals ---
    for g in body.goals:
        deadline = None
        if g.deadline:
            try:
                deadline = date_type.fromisoformat(g.deadline)
            except ValueError:
                pass
        session.add(Goal(
            title=g.title,
            kind=g.kind,
            target_amount=g.target_amount,
            current_amount=Decimal("0"),
            deadline=deadline,
            priority=g.priority,
            status="active",
        ))

    # --- career position + primary income ---
    if body.career:
        c = body.career
        total_comp = (c.current_base_salary or Decimal("0")) + (c.current_bonus or Decimal("0")) + (c.current_equity_annual or Decimal("0"))
        target_date = None
        if c.target_date:
            try:
                target_date = date_type.fromisoformat(c.target_date)
            except ValueError:
                pass
        session.add(CareerPosition(
            current_role=c.current_role,
            current_employer=c.current_employer,
            current_comp_total=total_comp,
            target_comp_total=c.target_comp,
            target_date=target_date,
        ))

    if body.primary_income:
        pi = body.primary_income
        session.add(IncomeStream(
            source=pi.source,
            source_type=pi.source_type,
            cadence=pi.cadence,
            typical_gross_amount=pi.typical_gross_amount,
            status="active",
        ))

    # --- side incomes ---
    for si in body.side_incomes:
        stream = IncomeStream(
            source=si.source,
            source_type=si.source_type,
            cadence=si.cadence,
            typical_gross_amount=si.typical_gross_amount,
            status="active",
        )
        session.add(stream)
        await session.flush()
        if si.hours_per_week and si.typical_gross_amount:
            monthly_gross = si.typical_gross_amount * Decimal("4.333")
            monthly_hours = si.hours_per_week * Decimal("4.333")
            monthly_exp = si.monthly_expenses or Decimal("0")
            net = monthly_gross - monthly_exp
            net_hourly = net / monthly_hours if monthly_hours > Decimal("0") else None
            now = datetime.now(timezone.utc)
            from datetime import date as _date
            session.add(SideIncomeEconomics(
                income_stream_id=stream.id,
                period_start=_date(now.year, now.month, 1),
                period_end=_date(now.year, now.month, 28),
                gross=monthly_gross,
                hours_worked=monthly_hours,
                expenses_jsonb={"monthly": float(monthly_exp)},
                net=net,
                net_hourly=net_hourly,
            ))

    # --- bank accounts ---
    for a in body.accounts:
        session.add(Account(
            type=a.type,
            institution=a.institution,
            nickname=a.nickname + (" (emergency fund)" if a.is_emergency_fund else ""),
            current_balance=a.current_balance,
            status="active",
        ))

    # --- monthly spend as single expense ---
    if body.monthly_spend and body.monthly_spend > Decimal("0"):
        session.add(Expense(
            name="Monthly Living Expenses (intake estimate)",
            category="living",
            cadence="monthly",
            typical_amount=body.monthly_spend,
            active=True,
        ))

    # --- debts ---
    for d in body.debts:
        session.add(Debt(
            name=d.name,
            balance=d.balance,
            apr=d.apr,
            minimum_payment=d.minimum_payment,
            strategy=d.strategy,
            status="active",
        ))

    # --- retirement accounts ---
    for r in body.retirement_accounts:
        session.add(RetirementAccount(
            kind=r.kind,
            institution=r.institution,
            balance=r.balance,
            ytd_contribution=r.ytd_contribution,
        ))

    # --- brokerage accounts + holdings ---
    for ba in body.brokerage_accounts:
        acct = Account(
            type="brokerage",
            institution=ba.institution,
            nickname=ba.nickname,
            current_balance=ba.current_balance,
            status="active",
        )
        session.add(acct)
        await session.flush()
        for h in ba.holdings:
            session.add(Holdings(
                account_id=acct.id,
                ticker=h.ticker.upper(),
                share_count=h.share_count,
                cost_basis=h.cost_basis,
            ))

    # --- real estate ---
    for re in body.real_estate:
        equity = None
        if re.current_value and re.mortgage_balance:
            equity = re.current_value - re.mortgage_balance
        session.add(RealEstate(
            address=re.address,
            purchase_price=re.purchase_price,
            current_value=re.current_value,
            mortgage_balance=re.mortgage_balance,
            mortgage_apr=re.mortgage_apr,
            monthly_payment=re.monthly_payment,
            property_type=re.property_type,
            monthly_rent=re.monthly_rent,
            equity_estimate=equity,
        ))

    # --- tax deductions ---
    if body.tax_deductions and body.tax_deductions.has_1099_income:
        td = body.tax_deductions
        current_year = datetime.now(timezone.utc).year
        from agent.principles import MILEAGE_RATE_2026
        if td.business_miles_ytd and td.business_miles_ytd > Decimal("0"):
            session.add(TaxDeduction1099(
                tax_year=current_year,
                category="mileage",
                amount=td.business_miles_ytd * Decimal(str(MILEAGE_RATE_2026)),
                evidence_note=f"{float(td.business_miles_ytd):,.0f} miles @ ${MILEAGE_RATE_2026}/mi",
            ))
        if td.equipment_purchased and td.equipment_purchased > Decimal("0"):
            session.add(TaxDeduction1099(tax_year=current_year, category="equipment", amount=td.equipment_purchased))
        if td.education_training and td.education_training > Decimal("0"):
            session.add(TaxDeduction1099(tax_year=current_year, category="education", amount=td.education_training))
        if td.home_office_sqft and td.home_office_sqft > 0:
            session.add(TaxDeduction1099(
                tax_year=current_year, category="home_office",
                amount=Decimal(str(td.home_office_sqft)) * Decimal("5"),
                evidence_note=f"{td.home_office_sqft} sqft × $5 simplified method",
            ))
        if td.other_deductible and td.other_deductible > Decimal("0"):
            session.add(TaxDeduction1099(tax_year=current_year, category="other", amount=td.other_deductible))

    await session.flush()

    # --- compute snapshot ---
    snap = await compute_and_store_snapshot(session, str(current_user.id))

    # --- archive raw submission ---
    archive = IntakeSubmission(
        raw_data=body.model_dump(mode="json"),
        snapshot_id=snap.id,
    )
    session.add(archive)

    # --- mark intake complete ---
    profile.intake_completed_at = datetime.now(timezone.utc)

    await session.commit()
    await session.refresh(snap)

    logger.info("intake submitted (user=%s, snapshot_id=%s)", current_user.username, snap.id)
    return snap


@router.get("/snapshot", response_model=FinancialSnapshotRead)
async def get_latest_snapshot(
    session: Session,
    current_user: CurrentUser,
) -> FinancialSnapshot:
    snap = (
        await session.execute(
            select(FinancialSnapshot).order_by(FinancialSnapshot.computed_at.desc()).limit(1)
        )
    ).scalar_one_or_none()
    if snap is None:
        raise HTTPException(status_code=404, detail="No snapshot found. Complete intake first.")
    return snap


@router.post("/snapshot/refresh", response_model=FinancialSnapshotRead, status_code=201)
async def refresh_snapshot(
    session: Session,
    current_user: CurrentUser,
) -> FinancialSnapshot:
    snap = await compute_and_store_snapshot(session, str(current_user.id))
    await session.commit()
    await session.refresh(snap)
    logger.info("snapshot refreshed (user=%s, snapshot_id=%s)", current_user.username, snap.id)
    return snap


@router.get("/archive")
async def get_intake_archive(
    session: Session,
    current_user: CurrentUser,
) -> list[dict]:
    rows = (
        await session.execute(
            select(IntakeSubmission).order_by(IntakeSubmission.submitted_at.desc())
        )
    ).scalars().all()
    return [
        {
            "id": r.id,
            "submitted_at": r.submitted_at.isoformat(),
            "snapshot_id": r.snapshot_id,
        }
        for r in rows
    ]
