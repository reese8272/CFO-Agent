"""Vault CRUD router — /vault/* endpoints.

All endpoints require authentication. JSON is the canonical response format.
HTMX callers (HX-Request header present) receive an HTML partial instead,
allowing the vault UI to do in-place list refreshes without a full page reload.
"""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from fastapi.responses import HTMLResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from auth import get_current_user
from config import get_settings
from db import get_session
from integrations.property_data import fetch_property_estimate
from vault import crud
from vault.models import RealEstate as RealEstateModel
from vault.schemas import (
    AccountCreate, AccountRead, AccountUpdate,
    AssetCreate, AssetRead, AssetUpdate,
    BusinessIncomeCreate, BusinessIncomeRead, BusinessIncomeUpdate,
    CardCreate, CardRead, CardUpdate,
    CareerHistoryCreate, CareerHistoryRead, CareerHistoryUpdate,
    CareerPositionCreate, CareerPositionRead, CareerPositionUpdate,
    CompBenchmarkCreate, CompBenchmarkRead, CompBenchmarkUpdate,
    DebtCreate, DebtRead, DebtUpdate,
    ExpenseCreate, ExpenseRead, ExpenseUpdate,
    GoalCreate, GoalRead, GoalUpdate,
    IncomeStreamCreate, IncomeStreamRead, IncomeStreamUpdate,
    NegotiationMilestoneCreate, NegotiationMilestoneRead, NegotiationMilestoneUpdate,
    NetWorthSnapshotCreate, NetWorthSnapshotRead, NetWorthSnapshotUpdate,
    RealEstateCreate, RealEstateRead, RealEstateUpdate,
    RetirementAccountCreate, RetirementAccountRead, RetirementAccountUpdate,
    SideIncomeEconomicsCreate, SideIncomeEconomicsRead, SideIncomeEconomicsUpdate,
    TaxDeduction1099Create, TaxDeduction1099Read, TaxDeduction1099Update,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/vault", tags=["vault"])

Session = Annotated[AsyncSession, Depends(get_session)]
CurrentUser = Annotated[str, Depends(get_current_user)]


def _is_htmx(hx_request: str | None) -> bool:
    return hx_request == "true"


def _entity_row_html(entity_type: str, obj: object, fields: list[tuple[str, str]]) -> str:
    """Render a minimal HTML table row for HTMX swap responses."""
    cells = "".join(
        f'<td class="px-3 py-2 text-sm">{getattr(obj, attr, "") or ""}</td>'
        for label, attr in fields
    )
    return (
        f'<tr id="{entity_type}-{obj.id}" '  # type: ignore[attr-defined]
        f'class="border-b border-gray-700 hover:bg-gray-800">'
        f'{cells}'
        f'<td class="px-3 py-2 text-sm">'
        f'<button hx-delete="/vault/{entity_type}/{obj.id}" '  # type: ignore[attr-defined]
        f'hx-target="closest tr" hx-swap="outerHTML" '
        f'class="text-red-400 hover:text-red-300 text-xs">delete</button>'
        f'</td>'
        f'</tr>'
    )


# ---------------------------------------------------------------------------
# Accounts
# ---------------------------------------------------------------------------

@router.post("/accounts", response_model=AccountRead, status_code=201)
async def create_account(
    body: AccountCreate,
    session: Session,
    user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_account(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("accounts", obj, [
            ("Institution", "institution"), ("Nickname", "nickname"),
            ("Type", "type"), ("Balance", "current_balance"), ("Status", "status"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/accounts", response_model=list[AccountRead])
async def list_accounts(session: Session, user: CurrentUser):
    return await crud.list_accounts(session)


@router.get("/accounts/{account_id}", response_model=AccountRead)
async def get_account(account_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_account(session, account_id)
    if obj is None:
        raise HTTPException(404, "account not found")
    return obj


@router.patch("/accounts/{account_id}", response_model=AccountRead)
async def update_account(
    account_id: int, body: AccountUpdate, session: Session, user: CurrentUser,
):
    obj = await crud.update_account(session, account_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "account not found")
    await session.commit()
    return obj


@router.delete("/accounts/{account_id}", status_code=204)
async def delete_account(account_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_account(session, account_id, actor=user)
    if not deleted:
        raise HTTPException(404, "account not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Cards
# ---------------------------------------------------------------------------

@router.post("/cards", response_model=CardRead, status_code=201)
async def create_card(
    body: CardCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_card(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("cards", obj, [
            ("Issuer", "issuer"), ("Network", "network"), ("Last 4", "last4"),
            ("Limit", "credit_limit"), ("Status", "status"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/cards", response_model=list[CardRead])
async def list_cards(session: Session, user: CurrentUser):
    return await crud.list_cards(session)


@router.get("/cards/{card_id}", response_model=CardRead)
async def get_card(card_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_card(session, card_id)
    if obj is None:
        raise HTTPException(404, "card not found")
    return obj


@router.patch("/cards/{card_id}", response_model=CardRead)
async def update_card(card_id: int, body: CardUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_card(session, card_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "card not found")
    await session.commit()
    return obj


@router.delete("/cards/{card_id}", status_code=204)
async def delete_card(card_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_card(session, card_id, actor=user)
    if not deleted:
        raise HTTPException(404, "card not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Income Streams
# ---------------------------------------------------------------------------

@router.post("/income-streams", response_model=IncomeStreamRead, status_code=201)
async def create_income_stream(
    body: IncomeStreamCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_income_stream(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("income-streams", obj, [
            ("Source", "source"), ("Type", "source_type"), ("Cadence", "cadence"),
            ("Typical Gross", "typical_gross_amount"), ("Status", "status"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/income-streams", response_model=list[IncomeStreamRead])
async def list_income_streams(session: Session, user: CurrentUser):
    return await crud.list_income_streams(session)


@router.get("/income-streams/{stream_id}", response_model=IncomeStreamRead)
async def get_income_stream(stream_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_income_stream(session, stream_id)
    if obj is None:
        raise HTTPException(404, "income stream not found")
    return obj


@router.patch("/income-streams/{stream_id}", response_model=IncomeStreamRead)
async def update_income_stream(stream_id: int, body: IncomeStreamUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_income_stream(session, stream_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "income stream not found")
    await session.commit()
    return obj


@router.delete("/income-streams/{stream_id}", status_code=204)
async def delete_income_stream(stream_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_income_stream(session, stream_id, actor=user)
    if not deleted:
        raise HTTPException(404, "income stream not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Expenses
# ---------------------------------------------------------------------------

@router.post("/expenses", response_model=ExpenseRead, status_code=201)
async def create_expense(
    body: ExpenseCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_expense(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("expenses", obj, [
            ("Name", "name"), ("Category", "category"), ("Cadence", "cadence"),
            ("Amount", "typical_amount"), ("Active", "active"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/expenses", response_model=list[ExpenseRead])
async def list_expenses(session: Session, user: CurrentUser):
    return await crud.list_expenses(session)


@router.get("/expenses/{expense_id}", response_model=ExpenseRead)
async def get_expense(expense_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_expense(session, expense_id)
    if obj is None:
        raise HTTPException(404, "expense not found")
    return obj


@router.patch("/expenses/{expense_id}", response_model=ExpenseRead)
async def update_expense(expense_id: int, body: ExpenseUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_expense(session, expense_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "expense not found")
    await session.commit()
    return obj


@router.delete("/expenses/{expense_id}", status_code=204)
async def delete_expense(expense_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_expense(session, expense_id, actor=user)
    if not deleted:
        raise HTTPException(404, "expense not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Debts
# ---------------------------------------------------------------------------

@router.post("/debts", response_model=DebtRead, status_code=201)
async def create_debt(
    body: DebtCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_debt(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("debts", obj, [
            ("Name", "name"), ("Balance", "balance"), ("APR", "apr"),
            ("Min Payment", "minimum_payment"), ("Strategy", "strategy"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/debts", response_model=list[DebtRead])
async def list_debts(session: Session, user: CurrentUser):
    return await crud.list_debts(session)


@router.get("/debts/{debt_id}", response_model=DebtRead)
async def get_debt(debt_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_debt(session, debt_id)
    if obj is None:
        raise HTTPException(404, "debt not found")
    return obj


@router.patch("/debts/{debt_id}", response_model=DebtRead)
async def update_debt(debt_id: int, body: DebtUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_debt(session, debt_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "debt not found")
    await session.commit()
    return obj


@router.delete("/debts/{debt_id}", status_code=204)
async def delete_debt(debt_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_debt(session, debt_id, actor=user)
    if not deleted:
        raise HTTPException(404, "debt not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

@router.post("/assets", response_model=AssetRead, status_code=201)
async def create_asset(
    body: AssetCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_asset(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("assets", obj, [
            ("Kind", "kind"), ("Nickname", "nickname"), ("Value", "value_estimate"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/assets", response_model=list[AssetRead])
async def list_assets(session: Session, user: CurrentUser):
    return await crud.list_assets(session)


@router.get("/assets/{asset_id}", response_model=AssetRead)
async def get_asset(asset_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_asset(session, asset_id)
    if obj is None:
        raise HTTPException(404, "asset not found")
    return obj


@router.patch("/assets/{asset_id}", response_model=AssetRead)
async def update_asset(asset_id: int, body: AssetUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_asset(session, asset_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "asset not found")
    await session.commit()
    return obj


@router.delete("/assets/{asset_id}", status_code=204)
async def delete_asset(asset_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_asset(session, asset_id, actor=user)
    if not deleted:
        raise HTTPException(404, "asset not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Real Estate
# ---------------------------------------------------------------------------

@router.post("/real-estate", response_model=RealEstateRead, status_code=201)
async def create_real_estate(
    body: RealEstateCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_real_estate(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("real-estate", obj, [
            ("Address", "address"), ("Type", "property_type"),
            ("Value", "current_value"), ("Equity", "equity_estimate"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/real-estate", response_model=list[RealEstateRead])
async def list_real_estate(session: Session, user: CurrentUser):
    return await crud.list_real_estate(session)


@router.get("/real-estate/{re_id}", response_model=RealEstateRead)
async def get_real_estate(re_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_real_estate(session, re_id)
    if obj is None:
        raise HTTPException(404, "real estate record not found")
    return obj


@router.patch("/real-estate/{re_id}", response_model=RealEstateRead)
async def update_real_estate(re_id: int, body: RealEstateUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_real_estate(session, re_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "real estate record not found")
    await session.commit()
    return obj


@router.delete("/real-estate/{re_id}", status_code=204)
async def delete_real_estate(re_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_real_estate(session, re_id, actor=user)
    if not deleted:
        raise HTTPException(404, "real estate record not found")
    await session.commit()


@router.post("/real-estate/refresh-values", status_code=200)
async def refresh_real_estate_values(session: Session, user: CurrentUser) -> dict:
    """Pull Zestimate-equivalent AVM for every real estate address via RentCast.

    Requires RENTCAST_API_KEY. Returns 503 if the key is absent.
    Disclaimer is mandatory on this response — property value is an estimate,
    not a licensed appraisal.
    """
    settings = get_settings()
    if not settings.rentcast_api_key:
        raise HTTPException(503, "RENTCAST_API_KEY not configured; property value refresh unavailable")

    result = await session.execute(select(RealEstateModel))
    properties = list(result.scalars().all())

    updated: list[int] = []
    skipped: list[int] = []
    disclaimer = (
        "Property value is an automated estimate from RentCast, not a licensed appraisal. "
        "Consult a licensed appraiser or real estate professional for accurate valuation."
    )

    for prop in properties:
        if not prop.address:
            skipped.append(prop.id)
            continue
        estimate = fetch_property_estimate(prop.address, settings.rentcast_api_key)
        if estimate is None:
            skipped.append(prop.id)
            continue
        prop.current_value = estimate.price
        updated.append(prop.id)

    await session.commit()
    return {
        "updated": updated,
        "skipped": skipped,
        "total": len(properties),
        "disclaimer": disclaimer,
    }


# ---------------------------------------------------------------------------
# Business Income
# ---------------------------------------------------------------------------

@router.post("/business-income", response_model=BusinessIncomeRead, status_code=201)
async def create_business_income(
    body: BusinessIncomeCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_business_income(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("business-income", obj, [
            ("Name", "business_name"), ("Entity", "entity_type"),
            ("Revenue", "monthly_revenue"), ("Margin", "net_margin"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/business-income", response_model=list[BusinessIncomeRead])
async def list_business_income(session: Session, user: CurrentUser):
    return await crud.list_business_income(session)


@router.get("/business-income/{bi_id}", response_model=BusinessIncomeRead)
async def get_business_income(bi_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_business_income(session, bi_id)
    if obj is None:
        raise HTTPException(404, "business income record not found")
    return obj


@router.patch("/business-income/{bi_id}", response_model=BusinessIncomeRead)
async def update_business_income(bi_id: int, body: BusinessIncomeUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_business_income(session, bi_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "business income record not found")
    await session.commit()
    return obj


@router.delete("/business-income/{bi_id}", status_code=204)
async def delete_business_income(bi_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_business_income(session, bi_id, actor=user)
    if not deleted:
        raise HTTPException(404, "business income record not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Retirement Accounts
# ---------------------------------------------------------------------------

@router.post("/retirement-accounts", response_model=RetirementAccountRead, status_code=201)
async def create_retirement_account(
    body: RetirementAccountCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_retirement_account(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("retirement-accounts", obj, [
            ("Kind", "kind"), ("Institution", "institution"),
            ("Balance", "balance"), ("YTD Contrib", "ytd_contribution"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/retirement-accounts", response_model=list[RetirementAccountRead])
async def list_retirement_accounts(session: Session, user: CurrentUser):
    return await crud.list_retirement_accounts(session)


@router.get("/retirement-accounts/{ra_id}", response_model=RetirementAccountRead)
async def get_retirement_account(ra_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_retirement_account(session, ra_id)
    if obj is None:
        raise HTTPException(404, "retirement account not found")
    return obj


@router.patch("/retirement-accounts/{ra_id}", response_model=RetirementAccountRead)
async def update_retirement_account(ra_id: int, body: RetirementAccountUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_retirement_account(session, ra_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "retirement account not found")
    await session.commit()
    return obj


@router.delete("/retirement-accounts/{ra_id}", status_code=204)
async def delete_retirement_account(ra_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_retirement_account(session, ra_id, actor=user)
    if not deleted:
        raise HTTPException(404, "retirement account not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Goals
# ---------------------------------------------------------------------------

@router.post("/goals", response_model=GoalRead, status_code=201)
async def create_goal(
    body: GoalCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_goal(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("goals", obj, [
            ("Title", "title"), ("Kind", "kind"),
            ("Target", "target_amount"), ("Status", "status"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/goals", response_model=list[GoalRead])
async def list_goals(session: Session, user: CurrentUser):
    return await crud.list_goals(session)


@router.get("/goals/{goal_id}", response_model=GoalRead)
async def get_goal(goal_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_goal(session, goal_id)
    if obj is None:
        raise HTTPException(404, "goal not found")
    return obj


@router.patch("/goals/{goal_id}", response_model=GoalRead)
async def update_goal(goal_id: int, body: GoalUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_goal(session, goal_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "goal not found")
    await session.commit()
    return obj


@router.delete("/goals/{goal_id}", status_code=204)
async def delete_goal(goal_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_goal(session, goal_id, actor=user)
    if not deleted:
        raise HTTPException(404, "goal not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Career Position
# ---------------------------------------------------------------------------

@router.post("/career-position", response_model=CareerPositionRead, status_code=201)
async def create_career_position(
    body: CareerPositionCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_career_position(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("career-position", obj, [
            ("Role", "current_role"), ("Employer", "current_employer"),
            ("Comp", "current_comp_total"), ("Target Role", "target_role"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/career-position", response_model=list[CareerPositionRead])
async def list_career_positions(session: Session, user: CurrentUser):
    return await crud.list_career_positions(session)


@router.get("/career-position/{cp_id}", response_model=CareerPositionRead)
async def get_career_position(cp_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_career_position(session, cp_id)
    if obj is None:
        raise HTTPException(404, "career position not found")
    return obj


@router.patch("/career-position/{cp_id}", response_model=CareerPositionRead)
async def update_career_position(cp_id: int, body: CareerPositionUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_career_position(session, cp_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "career position not found")
    await session.commit()
    return obj


@router.delete("/career-position/{cp_id}", status_code=204)
async def delete_career_position(cp_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_career_position(session, cp_id, actor=user)
    if not deleted:
        raise HTTPException(404, "career position not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Career History
# ---------------------------------------------------------------------------

@router.post("/career-history", response_model=CareerHistoryRead, status_code=201)
async def create_career_history(
    body: CareerHistoryCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_career_history(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("career-history", obj, [
            ("Role", "role"), ("Employer", "employer"),
            ("Comp", "comp_total"), ("Start", "start_date"), ("End", "end_date"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/career-history", response_model=list[CareerHistoryRead])
async def list_career_history(session: Session, user: CurrentUser):
    return await crud.list_career_history(session)


@router.get("/career-history/{ch_id}", response_model=CareerHistoryRead)
async def get_career_history(ch_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_career_history(session, ch_id)
    if obj is None:
        raise HTTPException(404, "career history record not found")
    return obj


@router.patch("/career-history/{ch_id}", response_model=CareerHistoryRead)
async def update_career_history(ch_id: int, body: CareerHistoryUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_career_history(session, ch_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "career history record not found")
    await session.commit()
    return obj


@router.delete("/career-history/{ch_id}", status_code=204)
async def delete_career_history(ch_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_career_history(session, ch_id, actor=user)
    if not deleted:
        raise HTTPException(404, "career history record not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Comp Benchmarks
# ---------------------------------------------------------------------------

@router.post("/comp-benchmarks", response_model=CompBenchmarkRead, status_code=201)
async def create_comp_benchmark(
    body: CompBenchmarkCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_comp_benchmark(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("comp-benchmarks", obj, [
            ("Role", "role"), ("Metro", "metro"), ("Source", "source"),
            ("P50", "comp_p50"), ("P75", "comp_p75"), ("P90", "comp_p90"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/comp-benchmarks", response_model=list[CompBenchmarkRead])
async def list_comp_benchmarks(session: Session, user: CurrentUser):
    return await crud.list_comp_benchmarks(session)


@router.get("/comp-benchmarks/{cb_id}", response_model=CompBenchmarkRead)
async def get_comp_benchmark(cb_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_comp_benchmark(session, cb_id)
    if obj is None:
        raise HTTPException(404, "comp benchmark not found")
    return obj


@router.patch("/comp-benchmarks/{cb_id}", response_model=CompBenchmarkRead)
async def update_comp_benchmark(cb_id: int, body: CompBenchmarkUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_comp_benchmark(session, cb_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "comp benchmark not found")
    await session.commit()
    return obj


@router.delete("/comp-benchmarks/{cb_id}", status_code=204)
async def delete_comp_benchmark(cb_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_comp_benchmark(session, cb_id, actor=user)
    if not deleted:
        raise HTTPException(404, "comp benchmark not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Side Income Economics
# ---------------------------------------------------------------------------

@router.post("/side-income-economics", response_model=SideIncomeEconomicsRead, status_code=201)
async def create_side_income_economics(
    body: SideIncomeEconomicsCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_side_income_economics(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("side-income-economics", obj, [
            ("Period Start", "period_start"), ("Period End", "period_end"),
            ("Gross", "gross"), ("Hours", "hours_worked"),
            ("Net", "net"), ("Net/hr", "net_hourly"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/side-income-economics", response_model=list[SideIncomeEconomicsRead])
async def list_side_income_economics(session: Session, user: CurrentUser):
    return await crud.list_side_income_economics(session)


@router.get("/side-income-economics/{sie_id}", response_model=SideIncomeEconomicsRead)
async def get_side_income_economics(sie_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_side_income_economics(session, sie_id)
    if obj is None:
        raise HTTPException(404, "side income economics record not found")
    return obj


@router.patch("/side-income-economics/{sie_id}", response_model=SideIncomeEconomicsRead)
async def update_side_income_economics(sie_id: int, body: SideIncomeEconomicsUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_side_income_economics(session, sie_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "side income economics record not found")
    await session.commit()
    return obj


@router.delete("/side-income-economics/{sie_id}", status_code=204)
async def delete_side_income_economics(sie_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_side_income_economics(session, sie_id, actor=user)
    if not deleted:
        raise HTTPException(404, "side income economics record not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Tax Deductions 1099
# ---------------------------------------------------------------------------

@router.post("/tax-deductions", response_model=TaxDeduction1099Read, status_code=201)
async def create_tax_deduction(
    body: TaxDeduction1099Create, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_tax_deduction(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("tax-deductions", obj, [
            ("Year", "tax_year"), ("Category", "category"), ("Amount", "amount"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/tax-deductions", response_model=list[TaxDeduction1099Read])
async def list_tax_deductions(session: Session, user: CurrentUser):
    return await crud.list_tax_deductions(session)


@router.get("/tax-deductions/{td_id}", response_model=TaxDeduction1099Read)
async def get_tax_deduction(td_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_tax_deduction(session, td_id)
    if obj is None:
        raise HTTPException(404, "tax deduction not found")
    return obj


@router.patch("/tax-deductions/{td_id}", response_model=TaxDeduction1099Read)
async def update_tax_deduction(td_id: int, body: TaxDeduction1099Update, session: Session, user: CurrentUser):
    obj = await crud.update_tax_deduction(session, td_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "tax deduction not found")
    await session.commit()
    return obj


@router.delete("/tax-deductions/{td_id}", status_code=204)
async def delete_tax_deduction(td_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_tax_deduction(session, td_id, actor=user)
    if not deleted:
        raise HTTPException(404, "tax deduction not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Negotiation Milestones
# ---------------------------------------------------------------------------

@router.post("/negotiation-milestones", response_model=NegotiationMilestoneRead, status_code=201)
async def create_negotiation_milestone(
    body: NegotiationMilestoneCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_negotiation_milestone(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("negotiation-milestones", obj, [
            ("Kind", "kind"), ("Date", "trigger_date"),
            ("Role", "related_role"), ("Status", "status"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/negotiation-milestones", response_model=list[NegotiationMilestoneRead])
async def list_negotiation_milestones(session: Session, user: CurrentUser):
    return await crud.list_negotiation_milestones(session)


@router.get("/negotiation-milestones/{nm_id}", response_model=NegotiationMilestoneRead)
async def get_negotiation_milestone(nm_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_negotiation_milestone(session, nm_id)
    if obj is None:
        raise HTTPException(404, "negotiation milestone not found")
    return obj


@router.patch("/negotiation-milestones/{nm_id}", response_model=NegotiationMilestoneRead)
async def update_negotiation_milestone(nm_id: int, body: NegotiationMilestoneUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_negotiation_milestone(session, nm_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "negotiation milestone not found")
    await session.commit()
    return obj


@router.delete("/negotiation-milestones/{nm_id}", status_code=204)
async def delete_negotiation_milestone(nm_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_negotiation_milestone(session, nm_id, actor=user)
    if not deleted:
        raise HTTPException(404, "negotiation milestone not found")
    await session.commit()


# ---------------------------------------------------------------------------
# Net Worth Snapshots
# ---------------------------------------------------------------------------

@router.post("/net-worth-snapshots", response_model=NetWorthSnapshotRead, status_code=201)
async def create_net_worth_snapshot(
    body: NetWorthSnapshotCreate, session: Session, user: CurrentUser,
    hx_request: Annotated[str | None, Header()] = None,
):
    obj = await crud.create_net_worth_snapshot(session, body, actor=user)
    await session.commit()
    if _is_htmx(hx_request):
        html = _entity_row_html("net-worth-snapshots", obj, [
            ("Date", "snapshot_at"), ("Assets", "assets_total"),
            ("Liabilities", "liabilities_total"), ("Net Worth", "net_worth"),
        ])
        return HTMLResponse(html, status_code=201)
    return obj


@router.get("/net-worth-snapshots", response_model=list[NetWorthSnapshotRead])
async def list_net_worth_snapshots(session: Session, user: CurrentUser):
    return await crud.list_net_worth_snapshots(session)


@router.get("/net-worth-snapshots/{snap_id}", response_model=NetWorthSnapshotRead)
async def get_net_worth_snapshot(snap_id: int, session: Session, user: CurrentUser):
    obj = await crud.get_net_worth_snapshot(session, snap_id)
    if obj is None:
        raise HTTPException(404, "net worth snapshot not found")
    return obj


@router.patch("/net-worth-snapshots/{snap_id}", response_model=NetWorthSnapshotRead)
async def update_net_worth_snapshot(snap_id: int, body: NetWorthSnapshotUpdate, session: Session, user: CurrentUser):
    obj = await crud.update_net_worth_snapshot(session, snap_id, body, actor=user)
    if obj is None:
        raise HTTPException(404, "net worth snapshot not found")
    await session.commit()
    return obj


@router.delete("/net-worth-snapshots/{snap_id}", status_code=204)
async def delete_net_worth_snapshot(snap_id: int, session: Session, user: CurrentUser):
    deleted = await crud.delete_net_worth_snapshot(session, snap_id, actor=user)
    if not deleted:
        raise HTTPException(404, "net worth snapshot not found")
    await session.commit()
