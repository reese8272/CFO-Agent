"""Pydantic v2 schemas for all vault entities.

Each entity has three shapes:
  - Create  — fields required to insert a new row
  - Update  — same fields but all Optional (PATCH semantics)
  - Read    — Create + server-set fields (id, created_at, etc.)

Money fields use Decimal throughout; never float.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Shared config
# ---------------------------------------------------------------------------

class _Base(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------------------------------------------------------------------
# Account
# ---------------------------------------------------------------------------

class AccountCreate(_Base):
    type: str
    institution: str
    nickname: str
    current_balance: Optional[Decimal] = None
    plaid_account_id: Optional[str] = None
    status: str = "active"


class AccountUpdate(_Base):
    type: Optional[str] = None
    institution: Optional[str] = None
    nickname: Optional[str] = None
    current_balance: Optional[Decimal] = None
    plaid_account_id: Optional[str] = None
    status: Optional[str] = None


class AccountRead(AccountCreate):
    id: int
    last_synced_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# Card
# ---------------------------------------------------------------------------

class CardCreate(_Base):
    account_id: int
    issuer: str
    network: str
    last4: Optional[str] = None
    benefits_jsonb: Optional[dict] = None
    credit_limit: Optional[Decimal] = None
    statement_day: Optional[int] = None
    due_day: Optional[int] = None
    autopay: bool = False
    current_cycle_spend: Optional[Decimal] = None
    status: str = "active"


class CardUpdate(_Base):
    account_id: Optional[int] = None
    issuer: Optional[str] = None
    network: Optional[str] = None
    last4: Optional[str] = None
    benefits_jsonb: Optional[dict] = None
    credit_limit: Optional[Decimal] = None
    statement_day: Optional[int] = None
    due_day: Optional[int] = None
    autopay: Optional[bool] = None
    current_cycle_spend: Optional[Decimal] = None
    status: Optional[str] = None


class CardRead(CardCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# IncomeStream
# ---------------------------------------------------------------------------

class IncomeStreamCreate(_Base):
    source: str
    source_type: str
    cadence: str
    typical_gross_amount: Optional[Decimal] = None
    tax_treatment_jsonb: Optional[dict] = None
    rolling_4wk_avg: Optional[Decimal] = None
    notes: Optional[str] = None
    status: str = "active"


class IncomeStreamUpdate(_Base):
    source: Optional[str] = None
    source_type: Optional[str] = None
    cadence: Optional[str] = None
    typical_gross_amount: Optional[Decimal] = None
    tax_treatment_jsonb: Optional[dict] = None
    rolling_4wk_avg: Optional[Decimal] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class IncomeStreamRead(IncomeStreamCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Expense
# ---------------------------------------------------------------------------

class ExpenseCreate(_Base):
    name: str
    category: str
    cadence: str
    typical_amount: Optional[Decimal] = None
    account_id: Optional[int] = None
    card_id: Optional[int] = None
    active: bool = True


class ExpenseUpdate(_Base):
    name: Optional[str] = None
    category: Optional[str] = None
    cadence: Optional[str] = None
    typical_amount: Optional[Decimal] = None
    account_id: Optional[int] = None
    card_id: Optional[int] = None
    active: Optional[bool] = None


class ExpenseRead(ExpenseCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Debt
# ---------------------------------------------------------------------------

class DebtCreate(_Base):
    name: str
    balance: Optional[Decimal] = None
    apr: Optional[Decimal] = None
    minimum_payment: Optional[Decimal] = None
    strategy: str = "avalanche"
    priority_rank: Optional[int] = None
    status: str = "active"


class DebtUpdate(_Base):
    name: Optional[str] = None
    balance: Optional[Decimal] = None
    apr: Optional[Decimal] = None
    minimum_payment: Optional[Decimal] = None
    strategy: Optional[str] = None
    priority_rank: Optional[int] = None
    status: Optional[str] = None


class DebtRead(DebtCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Asset
# ---------------------------------------------------------------------------

class AssetCreate(_Base):
    kind: str
    nickname: str
    value_estimate: Optional[Decimal] = None
    notes: Optional[str] = None


class AssetUpdate(_Base):
    kind: Optional[str] = None
    nickname: Optional[str] = None
    value_estimate: Optional[Decimal] = None
    notes: Optional[str] = None


class AssetRead(AssetCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# RealEstate
# ---------------------------------------------------------------------------

class RealEstateCreate(_Base):
    address: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    mortgage_balance: Optional[Decimal] = None
    mortgage_apr: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    property_type: str
    monthly_rent: Optional[Decimal] = None
    equity_estimate: Optional[Decimal] = None


class RealEstateUpdate(_Base):
    address: Optional[str] = None
    purchase_price: Optional[Decimal] = None
    current_value: Optional[Decimal] = None
    mortgage_balance: Optional[Decimal] = None
    mortgage_apr: Optional[Decimal] = None
    monthly_payment: Optional[Decimal] = None
    property_type: Optional[str] = None
    monthly_rent: Optional[Decimal] = None
    equity_estimate: Optional[Decimal] = None


class RealEstateRead(RealEstateCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# BusinessIncome
# ---------------------------------------------------------------------------

class BusinessIncomeCreate(_Base):
    business_name: str
    entity_type: str
    monthly_revenue: Optional[Decimal] = None
    monthly_expenses: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    notes: Optional[str] = None
    status: str = "active"


class BusinessIncomeUpdate(_Base):
    business_name: Optional[str] = None
    entity_type: Optional[str] = None
    monthly_revenue: Optional[Decimal] = None
    monthly_expenses: Optional[Decimal] = None
    net_margin: Optional[Decimal] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class BusinessIncomeRead(BusinessIncomeCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# RetirementAccount
# ---------------------------------------------------------------------------

class RetirementAccountCreate(_Base):
    kind: str
    institution: str
    ytd_contribution: Optional[Decimal] = None
    balance: Optional[Decimal] = None
    ytd_contribution_limit_remaining: Optional[Decimal] = None
    notes: Optional[str] = None


class RetirementAccountUpdate(_Base):
    kind: Optional[str] = None
    institution: Optional[str] = None
    ytd_contribution: Optional[Decimal] = None
    balance: Optional[Decimal] = None
    ytd_contribution_limit_remaining: Optional[Decimal] = None
    notes: Optional[str] = None


class RetirementAccountRead(RetirementAccountCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Goal
# ---------------------------------------------------------------------------

class GoalCreate(_Base):
    title: str
    kind: str
    target_amount: Optional[Decimal] = None
    current_amount: Optional[Decimal] = None
    deadline: Optional[date] = None
    priority: Optional[int] = None
    status: str = "active"


class GoalUpdate(_Base):
    title: Optional[str] = None
    kind: Optional[str] = None
    target_amount: Optional[Decimal] = None
    current_amount: Optional[Decimal] = None
    deadline: Optional[date] = None
    priority: Optional[int] = None
    status: Optional[str] = None


class GoalRead(GoalCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# CareerPosition
# ---------------------------------------------------------------------------

class CareerPositionCreate(_Base):
    current_role: str
    current_employer: str
    current_comp_total: Optional[Decimal] = None
    target_role: Optional[str] = None
    target_comp_total: Optional[Decimal] = None
    target_date: Optional[date] = None
    cert_or_milestone_jsonb: Optional[dict] = None
    notes: Optional[str] = None


class CareerPositionUpdate(_Base):
    current_role: Optional[str] = None
    current_employer: Optional[str] = None
    current_comp_total: Optional[Decimal] = None
    target_role: Optional[str] = None
    target_comp_total: Optional[Decimal] = None
    target_date: Optional[date] = None
    cert_or_milestone_jsonb: Optional[dict] = None
    notes: Optional[str] = None


class CareerPositionRead(CareerPositionCreate):
    id: int
    updated_at: datetime


# ---------------------------------------------------------------------------
# CareerHistory
# ---------------------------------------------------------------------------

class CareerHistoryCreate(_Base):
    role: str
    employer: str
    comp_total: Optional[Decimal] = None
    start_date: date
    end_date: Optional[date] = None
    reason_for_leaving: Optional[str] = None
    notes: Optional[str] = None


class CareerHistoryUpdate(_Base):
    role: Optional[str] = None
    employer: Optional[str] = None
    comp_total: Optional[Decimal] = None
    start_date: Optional[date] = None
    end_date: Optional[date] = None
    reason_for_leaving: Optional[str] = None
    notes: Optional[str] = None


class CareerHistoryRead(CareerHistoryCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# CompBenchmark
# ---------------------------------------------------------------------------

class CompBenchmarkCreate(_Base):
    role: str
    metro: str
    source: str
    comp_p50: Optional[Decimal] = None
    comp_p75: Optional[Decimal] = None
    comp_p90: Optional[Decimal] = None
    as_of_date: date
    notes: Optional[str] = None


class CompBenchmarkUpdate(_Base):
    role: Optional[str] = None
    metro: Optional[str] = None
    source: Optional[str] = None
    comp_p50: Optional[Decimal] = None
    comp_p75: Optional[Decimal] = None
    comp_p90: Optional[Decimal] = None
    as_of_date: Optional[date] = None
    notes: Optional[str] = None


class CompBenchmarkRead(CompBenchmarkCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# SideIncomeEconomics
# ---------------------------------------------------------------------------

class SideIncomeEconomicsCreate(_Base):
    income_stream_id: int
    period_start: date
    period_end: date
    gross: Optional[Decimal] = None
    hours_worked: Optional[Decimal] = None
    expenses_jsonb: Optional[dict] = None
    net: Optional[Decimal] = None
    net_hourly: Optional[Decimal] = None


class SideIncomeEconomicsUpdate(_Base):
    income_stream_id: Optional[int] = None
    period_start: Optional[date] = None
    period_end: Optional[date] = None
    gross: Optional[Decimal] = None
    hours_worked: Optional[Decimal] = None
    expenses_jsonb: Optional[dict] = None
    net: Optional[Decimal] = None
    net_hourly: Optional[Decimal] = None


class SideIncomeEconomicsRead(SideIncomeEconomicsCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# TaxDeduction1099
# ---------------------------------------------------------------------------

class TaxDeduction1099Create(_Base):
    tax_year: int
    category: str
    amount: Optional[Decimal] = None
    evidence_note: Optional[str] = None


class TaxDeduction1099Update(_Base):
    tax_year: Optional[int] = None
    category: Optional[str] = None
    amount: Optional[Decimal] = None
    evidence_note: Optional[str] = None


class TaxDeduction1099Read(TaxDeduction1099Create):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# NegotiationMilestone
# ---------------------------------------------------------------------------

class NegotiationMilestoneCreate(_Base):
    kind: str
    trigger_date: date
    related_role: Optional[str] = None
    prep_notes: Optional[str] = None
    status: str = "upcoming"


class NegotiationMilestoneUpdate(_Base):
    kind: Optional[str] = None
    trigger_date: Optional[date] = None
    related_role: Optional[str] = None
    prep_notes: Optional[str] = None
    status: Optional[str] = None
    completed_at: Optional[datetime] = None


class NegotiationMilestoneRead(NegotiationMilestoneCreate):
    id: int
    completed_at: Optional[datetime] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# NetWorthSnapshot
# ---------------------------------------------------------------------------

class NetWorthSnapshotCreate(_Base):
    snapshot_at: datetime
    assets_total: Optional[Decimal] = None
    liabilities_total: Optional[Decimal] = None
    net_worth: Optional[Decimal] = None
    asset_breakdown_jsonb: Optional[dict] = None
    liability_breakdown_jsonb: Optional[dict] = None
    source: str = "manual"


class NetWorthSnapshotUpdate(_Base):
    snapshot_at: Optional[datetime] = None
    assets_total: Optional[Decimal] = None
    liabilities_total: Optional[Decimal] = None
    net_worth: Optional[Decimal] = None
    asset_breakdown_jsonb: Optional[dict] = None
    liability_breakdown_jsonb: Optional[dict] = None
    source: Optional[str] = None


class NetWorthSnapshotRead(NetWorthSnapshotCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Holdings
# ---------------------------------------------------------------------------

class HoldingsCreate(_Base):
    account_id: int
    ticker: str
    share_count: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    last_known_price: Optional[Decimal] = None
    last_priced_at: Optional[datetime] = None
    notes: Optional[str] = None


class HoldingsUpdate(_Base):
    account_id: Optional[int] = None
    ticker: Optional[str] = None
    share_count: Optional[Decimal] = None
    cost_basis: Optional[Decimal] = None
    purchase_date: Optional[date] = None
    last_known_price: Optional[Decimal] = None
    last_priced_at: Optional[datetime] = None
    notes: Optional[str] = None


class HoldingsRead(HoldingsCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# SideIncomeEvent
# ---------------------------------------------------------------------------

class SideIncomeEventCreate(_Base):
    income_stream_id: int
    occurred_at: datetime
    duration_minutes: Optional[int] = None
    gross: Optional[Decimal] = None
    stream_specific_jsonb: Optional[dict] = None
    notes: Optional[str] = None


class SideIncomeEventUpdate(_Base):
    income_stream_id: Optional[int] = None
    occurred_at: Optional[datetime] = None
    duration_minutes: Optional[int] = None
    gross: Optional[Decimal] = None
    stream_specific_jsonb: Optional[dict] = None
    notes: Optional[str] = None


class SideIncomeEventRead(SideIncomeEventCreate):
    id: int
    created_at: datetime


# ---------------------------------------------------------------------------
# Import (Issue 4c)
# ---------------------------------------------------------------------------

class ImportBatchRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    filename: str
    file_format: str
    row_count: int
    imported_at: datetime


class CategoryMappingCreate(BaseModel):
    pattern: str
    category: str


class CategoryMappingRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    pattern: str
    category: str
    created_at: datetime


class TransactionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    account_id: int
    occurred_at: datetime
    amount: Decimal
    description: Optional[str] = None
    category: Optional[str] = None
    import_batch_id: Optional[int] = None
    import_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# UserProfile
# ---------------------------------------------------------------------------

class UserProfileCreate(_Base):
    age: Optional[int] = None
    household_size: int = 1
    dependents: int = 0
    state_of_residence: Optional[str] = None
    tax_filing_status: Optional[str] = None
    last_year_agi: Optional[Decimal] = None
    has_hsa_eligible_plan: bool = False
    intake_completed_at: Optional[datetime] = None


class UserProfileUpdate(_Base):
    age: Optional[int] = None
    household_size: Optional[int] = None
    dependents: Optional[int] = None
    state_of_residence: Optional[str] = None
    tax_filing_status: Optional[str] = None
    last_year_agi: Optional[Decimal] = None
    has_hsa_eligible_plan: Optional[bool] = None
    intake_completed_at: Optional[datetime] = None


class UserProfileRead(UserProfileCreate):
    id: int
    updated_at: datetime


# ---------------------------------------------------------------------------
# FinancialSnapshot
# ---------------------------------------------------------------------------

class FinancialSnapshotRead(_Base):
    id: int
    computed_at: datetime
    net_worth: Optional[Decimal] = None
    total_assets: Optional[Decimal] = None
    total_liabilities: Optional[Decimal] = None
    total_monthly_income: Optional[Decimal] = None
    total_monthly_expenses: Optional[Decimal] = None
    allocation_step: int
    income_step: int
    savings_rate_pct: Optional[Decimal] = None
    debt_to_income_ratio: Optional[Decimal] = None
    emergency_months_covered: Optional[Decimal] = None
    roth_utilization_pct: Optional[Decimal] = None
    k401_match_capture_pct: Optional[Decimal] = None
    hsa_utilization_pct: Optional[Decimal] = None
    career_comp_vs_p50_pct: Optional[Decimal] = None
    analysis_jsonb: Optional[dict] = None
    vault_hash: Optional[str] = None


# ---------------------------------------------------------------------------
# IntakeSubmission
# ---------------------------------------------------------------------------

class IntakeSubmissionRead(_Base):
    id: int
    submitted_at: datetime
    snapshot_id: Optional[int] = None
