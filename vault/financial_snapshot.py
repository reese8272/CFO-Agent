"""Financial snapshot analysis engine.

Computes a comprehensive analytical profile from the current vault state.
Called immediately after intake submission and on every vault refresh.
No LLM calls — pure deterministic math.
"""
from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from agent.principles import (
    ROTH_IRA_LIMIT_2026, HSA_LIMIT_SINGLE_2026, HSA_LIMIT_FAMILY_2026,
    K401_EMPLOYEE_LIMIT_2026, HIGH_INTEREST_APR_THRESHOLD, TAX_YEAR,
    MILEAGE_RATE_2026,
)
from vault.wealth_position import compute_wealth_position
from vault.income_position import compute_income_position

logger = logging.getLogger(__name__)

_ZERO = Decimal("0")
_HUNDRED = Decimal("100")


async def compute_and_store_snapshot(session: AsyncSession, user_id: str) -> "FinancialSnapshot":
    """Compute a fresh snapshot, persist it, and return the ORM row."""
    from vault.models import FinancialSnapshot

    data = await _compute_snapshot_data(session, user_id)
    vault_hash = _hash_snapshot_data(data)

    snap = FinancialSnapshot(
        net_worth=data["net_worth"],
        total_assets=data["total_assets"],
        total_liabilities=data["total_liabilities"],
        total_monthly_income=data["total_monthly_income"],
        total_monthly_expenses=data["total_monthly_expenses"],
        allocation_step=data["allocation_step"],
        income_step=data["income_step"],
        savings_rate_pct=data["savings_rate_pct"],
        debt_to_income_ratio=data["debt_to_income_ratio"],
        emergency_months_covered=data["emergency_months_covered"],
        roth_utilization_pct=data["roth_utilization_pct"],
        k401_match_capture_pct=data["k401_match_capture_pct"],
        hsa_utilization_pct=data["hsa_utilization_pct"],
        career_comp_vs_p50_pct=data["career_comp_vs_p50_pct"],
        analysis_jsonb=data,
        vault_hash=vault_hash,
    )
    session.add(snap)
    await session.flush()
    return snap


async def _compute_snapshot_data(session: AsyncSession, user_id: str) -> dict:
    from vault.models import (
        Account, Debt, Expense, IncomeStream, RetirementAccount,
        SideIncomeEconomics, TaxDeduction1099, CareerPosition, CompBenchmark,
        Goal, RealEstate, Holdings, UserProfile,
    )

    # --- positions ---
    wealth = await compute_wealth_position(session, user_id)
    income = await compute_income_position(session, user_id)

    net_worth: Decimal = wealth.get("net_worth", _ZERO)
    total_assets: Decimal = wealth.get("total_assets", _ZERO)
    total_liabilities: Decimal = wealth.get("total_liabilities", _ZERO)
    total_monthly_income: Decimal = income.get("total_monthly_income", _ZERO)

    open_wealth = wealth.get("open_gaps", [])
    open_income = income.get("open_gaps", [])
    allocation_step = open_wealth[0]["step"] if open_wealth else 6
    income_step = open_income[0]["step"] if open_income else 5

    # --- monthly expenses ---
    exp_rows = (await session.execute(select(Expense))).scalars().all()
    total_monthly_expenses = _ZERO
    for e in exp_rows:
        amt = _d(getattr(e, "typical_amount", None))
        if amt:
            total_monthly_expenses += _to_monthly(amt, getattr(e, "cadence", "monthly"))

    # --- savings rate ---
    savings_rate_pct: Decimal | None = None
    if total_monthly_income > _ZERO:
        surplus = total_monthly_income - total_monthly_expenses
        savings_rate_pct = _pct(surplus, total_monthly_income)

    # --- debt-to-income ---
    debt_rows = (await session.execute(select(Debt).where(Debt.status == "active"))).scalars().all()
    total_min_payments = sum(_d(getattr(d, "minimum_payment", None)) for d in debt_rows)
    debt_to_income_ratio: Decimal | None = None
    if total_monthly_income > _ZERO:
        debt_to_income_ratio = _round2(total_min_payments / total_monthly_income)

    # --- emergency months ---
    emergency_months_covered: Decimal | None = None
    if total_monthly_expenses > _ZERO:
        savings_balance = _ZERO
        acct_rows = (await session.execute(select(Account).where(Account.status == "active"))).scalars().all()
        for a in acct_rows:
            if getattr(a, "type", "") in ("checking", "savings", "cash"):
                savings_balance += _d(getattr(a, "current_balance", None))
        emergency_months_covered = _round2(savings_balance / total_monthly_expenses)

    # --- retirement utilization ---
    ret_rows = (await session.execute(select(RetirementAccount))).scalars().all()
    roth_contrib = _ZERO
    k401_contrib = _ZERO
    hsa_contrib = _ZERO
    k401_match_pct_offered = _ZERO  # placeholder — stored in analysis_jsonb when available

    for r in ret_rows:
        kind = getattr(r, "kind", "")
        ytd = _d(getattr(r, "ytd_contribution", None))
        if kind in ("roth_ira",):
            roth_contrib += ytd
        elif kind in ("401k", "traditional_401k"):
            k401_contrib += ytd
        elif kind == "hsa":
            hsa_contrib += ytd

    profile_row = (await session.execute(select(UserProfile))).scalar_one_or_none()
    has_hsa = profile_row.has_hsa_eligible_plan if profile_row else False
    hsa_limit = Decimal(str(HSA_LIMIT_SINGLE_2026))

    roth_utilization_pct = _pct(roth_contrib, Decimal(str(ROTH_IRA_LIMIT_2026)))
    k401_utilization_pct = _pct(k401_contrib, Decimal(str(K401_EMPLOYEE_LIMIT_2026)))
    hsa_utilization_pct = _pct(hsa_contrib, hsa_limit) if has_hsa else None
    k401_match_capture_pct: Decimal | None = None  # computed below if benchmark data available

    # --- career vs benchmark ---
    career_comp_vs_p50_pct: Decimal | None = None
    career_row = (await session.execute(select(CareerPosition))).scalar_one_or_none()
    bench_rows = (await session.execute(select(CompBenchmark))).scalars().all()
    if career_row and bench_rows:
        current_comp = _d(getattr(career_row, "current_comp_total", None))
        latest_bench = sorted(bench_rows, key=lambda b: b.as_of_date, reverse=True)[0]
        p50 = _d(getattr(latest_bench, "comp_p50", None))
        if current_comp and p50 and p50 > _ZERO:
            career_comp_vs_p50_pct = _round2(((current_comp - p50) / p50) * _HUNDRED)

    # --- income stream detail ---
    stream_rows = (await session.execute(select(IncomeStream).where(IncomeStream.status == "active"))).scalars().all()
    income_streams_detail = []
    for s in stream_rows:
        monthly = _to_monthly(_d(getattr(s, "typical_gross_amount", None)), getattr(s, "cadence", "monthly"))
        income_streams_detail.append({
            "source": s.source,
            "source_type": s.source_type,
            "cadence": s.cadence,
            "monthly_gross": float(_round2(monthly)),
        })

    # --- side income net hourly ---
    sie_rows = (await session.execute(select(SideIncomeEconomics))).scalars().all()
    net_hourlies = []
    for sie in sie_rows:
        nh = _d(getattr(sie, "net_hourly", None))
        if nh:
            net_hourlies.append(float(_round2(nh)))

    # --- debt detail ---
    debt_detail = []
    for d in debt_rows:
        debt_detail.append({
            "name": d.name,
            "balance": float(_round2(_d(getattr(d, "balance", None)))),
            "apr": float(_round2(_d(getattr(d, "apr", None)))),
            "minimum_payment": float(_round2(_d(getattr(d, "minimum_payment", None)))),
            "strategy": getattr(d, "strategy", "avalanche"),
        })
    # Sort by APR descending (avalanche order)
    debt_detail.sort(key=lambda x: x["apr"], reverse=True)

    # --- tax deductions ---
    current_year = datetime.now(timezone.utc).year
    tax_rows = (await session.execute(
        select(TaxDeduction1099).where(TaxDeduction1099.tax_year == current_year)
    )).scalars().all()
    deduction_categories = {r.category: float(_round2(_d(getattr(r, "amount", None)))) for r in tax_rows}

    # --- goals progress ---
    goal_rows = (await session.execute(select(Goal).where(Goal.status == "active"))).scalars().all()
    goals_progress = []
    for g in goal_rows:
        target = _d(getattr(g, "target_amount", None))
        current_g = _d(getattr(g, "current_amount", None)) or _ZERO
        pct_done = float(_pct(current_g, target)) if target and target > _ZERO else 0.0
        goals_progress.append({
            "title": g.title,
            "kind": g.kind,
            "target": float(_round2(target)) if target else None,
            "current": float(_round2(current_g)),
            "pct": round(pct_done, 1),
            "deadline": g.deadline.isoformat() if g.deadline else None,
        })

    # --- life context ---
    life_context: dict = {}
    if profile_row:
        life_context = {
            "age": profile_row.age,
            "household_size": profile_row.household_size,
            "dependents": profile_row.dependents,
            "state_of_residence": profile_row.state_of_residence,
            "tax_filing_status": profile_row.tax_filing_status,
            "has_hsa_eligible_plan": profile_row.has_hsa_eligible_plan,
        }

    # --- risk flags ---
    risk_flags: list[str] = []
    if emergency_months_covered is not None and emergency_months_covered < Decimal("3"):
        risk_flags.append(
            f"Emergency fund covers only {float(emergency_months_covered):.1f} months (target: 3 months minimum)"
        )
    high_apr_debts = [d for d in debt_detail if d["apr"] > HIGH_INTEREST_APR_THRESHOLD]
    for d in high_apr_debts:
        monthly_cost = round(d["balance"] * d["apr"] / 100 / 12, 0)
        risk_flags.append(
            f"{d['name']} at {d['apr']}% APR — costs ~${monthly_cost:,.0f}/mo in interest"
        )
    if savings_rate_pct is not None and savings_rate_pct < Decimal("10"):
        risk_flags.append(
            f"Savings rate is {float(savings_rate_pct):.1f}% (target: 20%+)"
        )
    if debt_to_income_ratio is not None and debt_to_income_ratio > Decimal("0.36"):
        risk_flags.append(
            f"Debt-to-income ratio is {float(debt_to_income_ratio):.2f} (above 0.36 threshold)"
        )

    # --- opportunity flags ---
    opportunity_flags: list[str] = []
    roth_room = Decimal(str(ROTH_IRA_LIMIT_2026)) - roth_contrib
    if roth_room > _ZERO:
        opportunity_flags.append(
            f"${float(roth_room):,.0f} of unused {TAX_YEAR} Roth IRA contribution room remaining"
        )
    if net_hourlies and len(net_hourlies) >= 2:
        top = max(net_hourlies)
        bottom = min(net_hourlies)
        if top > 0 and bottom / top < Decimal("0.70"):
            opportunity_flags.append(
                f"Lowest-margin income stream at ${bottom:.2f}/hr is significantly below top stream (${top:.2f}/hr) — candidate for reduction"
            )
    if not deduction_categories and any(s["source_type"] in ("1099", "gig") for s in income_streams_detail):
        opportunity_flags.append(
            f"1099/gig income detected but no deductions recorded — mileage at ${MILEAGE_RATE_2026}/mi alone could save hundreds"
        )
    if career_comp_vs_p50_pct is not None and career_comp_vs_p50_pct < Decimal("-5"):
        opportunity_flags.append(
            f"Current comp is {abs(float(career_comp_vs_p50_pct)):.0f}% below market P50 — job switch or negotiation likely worth pursuing"
        )
    if career_row:
        current_comp_c = _d(getattr(career_row, "current_comp_total", None)) or _ZERO
        if k401_contrib == _ZERO and current_comp_c > _ZERO:
            opportunity_flags.append("No 401k contributions detected — check if employer plan is available")

    return {
        "net_worth": net_worth,
        "total_assets": total_assets,
        "total_liabilities": total_liabilities,
        "total_monthly_income": total_monthly_income,
        "total_monthly_expenses": total_monthly_expenses,
        "allocation_step": allocation_step,
        "income_step": income_step,
        "savings_rate_pct": savings_rate_pct,
        "debt_to_income_ratio": debt_to_income_ratio,
        "emergency_months_covered": emergency_months_covered,
        "roth_utilization_pct": roth_utilization_pct,
        "k401_match_capture_pct": k401_match_capture_pct,
        "hsa_utilization_pct": hsa_utilization_pct,
        "career_comp_vs_p50_pct": career_comp_vs_p50_pct,
        "income_streams": income_streams_detail,
        "debt_breakdown": debt_detail,
        "net_hourly_by_stream": net_hourlies,
        "deduction_categories": deduction_categories,
        "goals_progress": goals_progress,
        "life_context": life_context,
        "risk_flags": risk_flags,
        "opportunity_flags": opportunity_flags,
        "allocation_ladder": wealth.get("allocation_ladder", []),
        "income_ladder": income.get("income_ladder", []),
        "computed_at": datetime.now(timezone.utc).isoformat(),
    }


def _hash_snapshot_data(data: dict) -> str:
    def _default(obj: object) -> str:
        if isinstance(obj, Decimal):
            return str(obj)
        return str(obj)
    serialized = json.dumps(
        {k: v for k, v in data.items() if k not in ("computed_at",)},
        sort_keys=True, default=_default
    )
    return hashlib.sha256(serialized.encode()).hexdigest()[:16]


def _d(val: object) -> Decimal:
    if val is None:
        return _ZERO
    try:
        return Decimal(str(val))
    except Exception:
        return _ZERO


def _pct(numerator: Decimal, denominator: Decimal) -> Decimal:
    if not denominator or denominator == _ZERO:
        return _ZERO
    return _round2((numerator / denominator) * _HUNDRED)


def _round2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def _to_monthly(amount: Decimal, cadence: str) -> Decimal:
    mapping = {
        "weekly": Decimal("4.333"),
        "biweekly": Decimal("2.167"),
        "monthly": Decimal("1"),
        "quarterly": Decimal("0.333"),
        "annual": Decimal("0.0833"),
        "irregular": Decimal("1"),
    }
    return amount * mapping.get(cadence, Decimal("1"))
