"""Intake router — financial onboarding wizard endpoints.

POST /intake/submit          — accepts full intake payload, populates vault, archives, computes snapshot
POST /intake/interview       — single turn of the CFO-led conversational intake interview
POST /intake/extract         — extracts structured IntakeSubmitPayload from a completed conversation
GET  /intake/status          — returns whether intake is complete + latest snapshot summary
GET  /intake/snapshot        — returns latest financial snapshot (full analysis)
POST /intake/snapshot/refresh — recomputes snapshot from current vault state
GET  /intake/archive         — returns the original intake submission
"""
import logging
from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import User, get_current_user
from clients import get_anthropic
from config import get_settings
from rate_limit import limiter
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
# Response models
# ---------------------------------------------------------------------------

class IntakeStatusResponse(BaseModel):
    intake_completed: bool
    completed_at: Optional[str] = None
    snapshot_id: Optional[int] = None
    net_worth: Optional[str] = None
    allocation_step: Optional[int] = None
    income_step: Optional[int] = None


class IntakeArchiveEntry(BaseModel):
    id: int
    submitted_at: str
    snapshot_id: Optional[int] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("/status", response_model=IntakeStatusResponse)
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


@router.get("/archive", response_model=list[IntakeArchiveEntry])
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


# ---------------------------------------------------------------------------
# CFO-led conversational intake
# ---------------------------------------------------------------------------

_INTERVIEW_SYSTEM = """You are a Personal CFO conducting a warm, efficient financial intake interview. \
Your goal is to understand someone's complete financial picture through natural conversation — not a form.

Work through these areas. You don't need to go in order, and you can combine questions naturally:
- Life context: approximate age, state of residence, household size, tax filing status
- Goals: what does financial success look like in 5 and 10 years?
- Income: all sources — W-2 salary, freelance, gig apps, business, rental
- Bank accounts & cash: checking, savings, emergency fund (rough balances are fine)
- Debt: every debt they carry — credit cards, student loans, car, personal loans (rough balances fine; \
  if they don't know the rate, that's OK, just move on)
- Retirement & investments: 401k, Roth IRA, brokerage, HSA
- Real estate: do they own property?
- Tax situation: 1099/self-employment income? Known deductions?

Rules:
- Be warm and direct — one topic at a time, open-ended first ("Tell me about your debt situation")
- Exact numbers are never required — estimates, ranges, and "I'm not sure" are all fine
- Keep each reply to 2-3 sentences max
- If they don't know something, acknowledge it briefly and move on
- Do NOT repeat questions they've already answered
- Once you have covered income, debt, assets, and goals at minimum, AND you have asked \
  about each area at least once, append exactly [INTAKE_COMPLETE] at the end of your reply

Do not append [INTAKE_COMPLETE] until all areas above have been addressed at least once."""

_EXTRACT_TOOL = {
    "name": "extract_intake_payload",
    "description": "Extract all financial data from the conversation into a structured intake payload.",
    "input_schema": {
        "type": "object",
        "properties": {
            "life_context": {
                "type": "object",
                "properties": {
                    "age": {"type": ["integer", "null"]},
                    "household_size": {"type": "integer"},
                    "dependents": {"type": "integer"},
                    "state_of_residence": {"type": ["string", "null"], "description": "2-letter state code"},
                    "tax_filing_status": {"type": ["string", "null"], "enum": ["single", "married_filing_jointly", "married_filing_separately", "head_of_household", None]},
                    "last_year_agi": {"type": ["number", "null"]},
                    "has_hsa_eligible_plan": {"type": "boolean"},
                },
                "required": ["household_size", "dependents", "has_hsa_eligible_plan"],
            },
            "goals": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "kind": {"type": "string", "enum": ["net_worth", "income", "passive_income", "other"]},
                        "target_amount": {"type": ["number", "null"]},
                        "deadline": {"type": ["string", "null"], "description": "YYYY-MM-DD"},
                        "priority": {"type": ["integer", "null"]},
                    },
                    "required": ["title", "kind"],
                },
            },
            "career": {
                "type": ["object", "null"],
                "properties": {
                    "current_role": {"type": "string"},
                    "current_employer": {"type": "string"},
                    "current_base_salary": {"type": ["number", "null"]},
                    "current_bonus": {"type": ["number", "null"]},
                    "current_equity_annual": {"type": ["number", "null"]},
                    "target_comp": {"type": ["number", "null"]},
                    "target_date": {"type": ["string", "null"]},
                },
                "required": ["current_role", "current_employer"],
            },
            "primary_income": {
                "type": ["object", "null"],
                "properties": {
                    "source": {"type": "string"},
                    "source_type": {"type": "string", "enum": ["w2", "1099", "cash", "gig", "business", "other"]},
                    "cadence": {"type": "string", "enum": ["weekly", "biweekly", "monthly", "irregular"]},
                    "typical_gross_amount": {"type": ["number", "null"], "description": "Monthly gross amount"},
                },
                "required": ["source", "source_type", "cadence"],
            },
            "side_incomes": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "source": {"type": "string"},
                        "source_type": {"type": "string", "enum": ["w2", "1099", "cash", "gig", "business", "other"]},
                        "cadence": {"type": "string", "enum": ["weekly", "biweekly", "monthly", "irregular"]},
                        "typical_gross_amount": {"type": ["number", "null"]},
                        "hours_per_week": {"type": ["number", "null"]},
                        "monthly_expenses": {"type": ["number", "null"]},
                    },
                    "required": ["source", "source_type", "cadence"],
                },
            },
            "accounts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nickname": {"type": "string"},
                        "institution": {"type": "string"},
                        "type": {"type": "string", "enum": ["checking", "savings", "cash"]},
                        "current_balance": {"type": ["number", "null"]},
                        "is_emergency_fund": {"type": "boolean"},
                    },
                    "required": ["nickname", "institution", "type", "is_emergency_fund"],
                },
            },
            "monthly_spend": {"type": ["number", "null"]},
            "debts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "balance": {"type": ["number", "null"]},
                        "apr": {"type": ["number", "null"]},
                        "minimum_payment": {"type": ["number", "null"]},
                        "strategy": {"type": "string", "enum": ["avalanche", "snowball", "custom"]},
                    },
                    "required": ["name", "strategy"],
                },
            },
            "retirement_accounts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["401k", "roth_ira", "traditional_ira", "hsa", "solo_401k"]},
                        "institution": {"type": "string"},
                        "balance": {"type": ["number", "null"]},
                        "ytd_contribution": {"type": ["number", "null"]},
                        "employer_match_pct": {"type": ["number", "null"]},
                        "employer_match_up_to_pct": {"type": ["number", "null"]},
                    },
                    "required": ["kind", "institution"],
                },
            },
            "brokerage_accounts": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "nickname": {"type": "string"},
                        "institution": {"type": "string"},
                        "current_balance": {"type": ["number", "null"]},
                        "holdings": {"type": "array", "items": {"type": "object"}},
                    },
                    "required": ["nickname", "institution"],
                },
            },
            "real_estate": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "property_type": {"type": "string", "enum": ["primary", "rental", "vacation", "land"]},
                        "address": {"type": ["string", "null"]},
                        "purchase_price": {"type": ["number", "null"]},
                        "current_value": {"type": ["number", "null"]},
                        "mortgage_balance": {"type": ["number", "null"]},
                        "mortgage_apr": {"type": ["number", "null"]},
                        "monthly_payment": {"type": ["number", "null"]},
                        "monthly_rent": {"type": ["number", "null"]},
                    },
                    "required": ["property_type"],
                },
            },
            "tax_deductions": {
                "type": "object",
                "properties": {
                    "has_1099_income": {"type": "boolean"},
                    "business_miles_ytd": {"type": ["number", "null"]},
                    "home_office_sqft": {"type": ["integer", "null"]},
                    "equipment_purchased": {"type": ["number", "null"]},
                    "education_training": {"type": ["number", "null"]},
                    "other_deductible": {"type": ["number", "null"]},
                    "paying_quarterly_estimated_tax": {"type": "boolean"},
                },
                "required": ["has_1099_income", "paying_quarterly_estimated_tax"],
            },
        },
        "required": ["life_context", "goals", "side_incomes", "accounts", "debts",
                     "retirement_accounts", "brokerage_accounts", "real_estate", "tax_deductions"],
    },
}

_EXTRACT_SYSTEM = """Extract every piece of financial data from this intake conversation into the \
extract_intake_payload tool. Be generous with estimates — if someone said "around $50k in student loans" \
use 50000. If something was not mentioned, use null or empty arrays. \
Convert annual salary to monthly for typical_gross_amount (annual / 12). \
Default strategy to "avalanche" for debts. Default household_size to 1 and dependents to 0 \
if not stated."""

class InterviewTurnRequest(BaseModel):
    message: str
    history: list[dict] = []


class InterviewTurnResponse(BaseModel):
    reply: str
    history: list[dict]
    complete: bool


class ExtractRequest(BaseModel):
    history: list[dict]


@router.post("/interview", response_model=InterviewTurnResponse)
@limiter.limit("20/minute")
async def intake_interview(
    request: Request,
    body: InterviewTurnRequest,
    current_user: CurrentUser,
) -> InterviewTurnResponse:
    client = get_anthropic()
    history = list(body.history)

    # Empty message on first turn = opening greeting; don't add a blank user turn
    if body.message.strip():
        history.append({"role": "user", "content": body.message})
    elif history:
        # Non-empty history but empty message — nothing to do
        pass
    # If history is empty and message is empty, just call Claude with no prior turns
    # so it produces the opening greeting

    response = await client.messages.create(
        model=get_settings().anthropic_model_smart,
        max_tokens=512,
        system=[{
            "type": "text",
            "text": _INTERVIEW_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=history if history else [{"role": "user", "content": "Hello"}],
    )

    reply_text: str = response.content[0].text if response.content else ""
    complete = "[INTAKE_COMPLETE]" in reply_text
    clean_reply = reply_text.replace("[INTAKE_COMPLETE]", "").strip()

    history.append({"role": "assistant", "content": clean_reply})
    logger.info(
        "interview turn (user=%s, complete=%s, turns=%d) tokens_in=%d tokens_out=%d cache_read=%d",
        current_user.username, complete, len(history),
        response.usage.input_tokens, response.usage.output_tokens,
        getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    )
    return InterviewTurnResponse(reply=clean_reply, history=history, complete=complete)


@router.post("/extract", response_model=dict)
@limiter.limit("6/minute")
async def extract_intake(
    request: Request,
    body: ExtractRequest,
    current_user: CurrentUser,
) -> dict:
    """Run structured extraction on a completed interview conversation."""
    client = get_anthropic()

    transcript = "\n".join(
        f"{'User' if m['role'] == 'user' else 'CFO'}: {m['content']}"
        for m in body.history
    )

    response = await client.messages.create(
        model=get_settings().anthropic_model_smart,
        max_tokens=4096,
        system=[{
            "type": "text",
            "text": _EXTRACT_SYSTEM,
            "cache_control": {"type": "ephemeral"},
        }],
        messages=[{"role": "user", "content": f"Intake conversation:\n\n{transcript}"}],
        tools=[{**_EXTRACT_TOOL, "cache_control": {"type": "ephemeral"}}],
        tool_choice={"type": "tool", "name": "extract_intake_payload"},
    )
    logger.info(
        "intake extraction (user=%s) tokens_in=%d tokens_out=%d cache_read=%d",
        current_user.username,
        response.usage.input_tokens, response.usage.output_tokens,
        getattr(response.usage, "cache_read_input_tokens", 0) or 0,
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "extract_intake_payload":
            return block.input

    raise HTTPException(status_code=500, detail="Extraction failed — no structured output returned.")


@router.post("/reset", status_code=200)
async def reset_intake(
    session: Session,
    current_user: CurrentUser,
) -> dict:
    """Clear intake_completed_at so the user can redo the intake wizard. Vault data is preserved."""
    profile = (await session.execute(select(UserProfile))).scalar_one_or_none()
    if profile is not None:
        profile.intake_completed_at = None
        await session.commit()
    return {"reset": True}
