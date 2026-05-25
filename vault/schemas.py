"""Pydantic request/response schemas for the vault CRUD surface.

Per entity we declare two hand-written schemas:
  - `<Entity>In`  — writable fields (used for create). `extra="forbid"` so the
                    API rejects unknown fields at the boundary.
  - `<Entity>Out` — read projection: writable fields + id + timestamp +
                    any server-computed / deferred read-only fields.

The partial-update (`PATCH`) schema is generated from `<Entity>In` by
`make_patch_schema` in routers/vault.py — every field becomes optional.

Money is always Decimal. JSONB money breakdowns (side-income expenses,
net-worth asset/liability splits) are typed `dict[str, Decimal]`; non-money
metadata blobs (card benefits, tax treatment, career milestones) are
`dict[str, Any]`.
"""
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


class _In(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int


# --- accounts ---
class AccountIn(_In):
    type: str
    institution: str
    nickname: str
    current_balance: Decimal | None = None
    last_synced_at: datetime | None = None
    plaid_account_id: str | None = None
    status: str | None = None


class AccountOut(_Out):
    type: str
    institution: str
    nickname: str
    current_balance: Decimal | None = None
    last_synced_at: datetime | None = None
    plaid_account_id: str | None = None
    status: str
    created_at: datetime


# --- cards ---
class CardIn(_In):
    account_id: int
    issuer: str
    network: str
    last4: str | None = None
    benefits_jsonb: dict[str, Any] | None = None
    credit_limit: Decimal | None = None
    statement_day: int | None = None
    due_day: int | None = None
    autopay: bool | None = None
    current_cycle_spend: Decimal | None = None
    status: str | None = None


class CardOut(_Out):
    account_id: int
    issuer: str
    network: str
    last4: str | None = None
    benefits_jsonb: dict[str, Any] | None = None
    credit_limit: Decimal | None = None
    statement_day: int | None = None
    due_day: int | None = None
    autopay: bool
    current_cycle_spend: Decimal | None = None
    status: str
    created_at: datetime


# --- income_streams ---
class IncomeStreamIn(_In):
    source: str
    source_type: str
    cadence: str
    typical_gross_amount: Decimal | None = None
    tax_treatment_jsonb: dict[str, Any] | None = None
    notes: str | None = None
    status: str | None = None


class IncomeStreamOut(_Out):
    source: str
    source_type: str
    cadence: str
    typical_gross_amount: Decimal | None = None
    tax_treatment_jsonb: dict[str, Any] | None = None
    rolling_4wk_avg: Decimal | None = None  # deferred to Issue 5 (rolling window)
    notes: str | None = None
    status: str
    created_at: datetime


# --- expenses ---
class ExpenseIn(_In):
    name: str
    category: str
    cadence: str
    typical_amount: Decimal | None = None
    account_id: int | None = None
    card_id: int | None = None
    active: bool | None = None


class ExpenseOut(_Out):
    name: str
    category: str
    cadence: str
    typical_amount: Decimal | None = None
    account_id: int | None = None
    card_id: int | None = None
    active: bool
    created_at: datetime


# --- debts ---
class DebtIn(_In):
    name: str
    balance: Decimal | None = None
    apr: Decimal | None = None
    minimum_payment: Decimal | None = None
    strategy: str | None = None
    priority_rank: int | None = None
    status: str | None = None


class DebtOut(_Out):
    name: str
    balance: Decimal | None = None
    apr: Decimal | None = None
    minimum_payment: Decimal | None = None
    strategy: str
    priority_rank: int | None = None
    status: str
    created_at: datetime


# --- assets ---
class AssetIn(_In):
    kind: str
    nickname: str
    value_estimate: Decimal | None = None
    notes: str | None = None


class AssetOut(_Out):
    kind: str
    nickname: str
    value_estimate: Decimal | None = None
    notes: str | None = None
    created_at: datetime


# --- real_estate ---
class RealEstateIn(_In):
    property_type: str
    address: str | None = None
    purchase_price: Decimal | None = None
    current_value: Decimal | None = None
    mortgage_balance: Decimal | None = None
    mortgage_apr: Decimal | None = None
    monthly_payment: Decimal | None = None
    monthly_rent: Decimal | None = None


class RealEstateOut(_Out):
    property_type: str
    address: str | None = None
    purchase_price: Decimal | None = None
    current_value: Decimal | None = None
    mortgage_balance: Decimal | None = None
    mortgage_apr: Decimal | None = None
    monthly_payment: Decimal | None = None
    monthly_rent: Decimal | None = None
    equity_estimate: Decimal | None = None  # computed: current_value - mortgage_balance
    created_at: datetime


# --- business_income ---
class BusinessIncomeIn(_In):
    business_name: str
    entity_type: str
    monthly_revenue: Decimal | None = None
    monthly_expenses: Decimal | None = None
    notes: str | None = None
    status: str | None = None


class BusinessIncomeOut(_Out):
    business_name: str
    entity_type: str
    monthly_revenue: Decimal | None = None
    monthly_expenses: Decimal | None = None
    net_margin: Decimal | None = None  # computed: revenue - expenses
    notes: str | None = None
    status: str
    created_at: datetime


# --- retirement_accounts ---
class RetirementAccountIn(_In):
    kind: str
    institution: str
    ytd_contribution: Decimal | None = None
    balance: Decimal | None = None
    notes: str | None = None


class RetirementAccountOut(_Out):
    kind: str
    institution: str
    ytd_contribution: Decimal | None = None
    balance: Decimal | None = None
    # deferred to Issue 8 (needs year-versioned tax constants from agent/principles.py)
    ytd_contribution_limit_remaining: Decimal | None = None
    notes: str | None = None
    created_at: datetime


# --- goals ---
class GoalIn(_In):
    title: str
    kind: str
    target_amount: Decimal | None = None
    deadline: date | None = None
    priority: int | None = None
    status: str | None = None


class GoalOut(_Out):
    title: str
    kind: str
    target_amount: Decimal | None = None
    current_amount: Decimal | None = None  # deferred to Issue 5 (computed from vault state)
    deadline: date | None = None
    priority: int | None = None
    status: str
    created_at: datetime


# --- career_position ---
class CareerPositionIn(_In):
    current_role: str
    current_employer: str
    current_comp_total: Decimal | None = None
    target_role: str | None = None
    target_comp_total: Decimal | None = None
    target_date: date | None = None
    cert_or_milestone_jsonb: dict[str, Any] | None = None
    notes: str | None = None


class CareerPositionOut(_Out):
    current_role: str
    current_employer: str
    current_comp_total: Decimal | None = None
    target_role: str | None = None
    target_comp_total: Decimal | None = None
    target_date: date | None = None
    cert_or_milestone_jsonb: dict[str, Any] | None = None
    notes: str | None = None
    updated_at: datetime


# --- career_history ---
class CareerHistoryIn(_In):
    role: str
    employer: str
    comp_total: Decimal | None = None
    start_date: date
    end_date: date | None = None
    reason_for_leaving: str | None = None
    notes: str | None = None


class CareerHistoryOut(_Out):
    role: str
    employer: str
    comp_total: Decimal | None = None
    start_date: date
    end_date: date | None = None
    reason_for_leaving: str | None = None
    notes: str | None = None
    created_at: datetime


# --- comp_benchmarks ---
class CompBenchmarkIn(_In):
    role: str
    metro: str
    source: str
    comp_p50: Decimal | None = None
    comp_p75: Decimal | None = None
    comp_p90: Decimal | None = None
    as_of_date: date
    notes: str | None = None


class CompBenchmarkOut(_Out):
    role: str
    metro: str
    source: str
    comp_p50: Decimal | None = None
    comp_p75: Decimal | None = None
    comp_p90: Decimal | None = None
    as_of_date: date
    notes: str | None = None
    created_at: datetime


# --- side_income_economics ---
class SideIncomeEconomicsIn(_In):
    income_stream_id: int
    period_start: date
    period_end: date
    gross: Decimal | None = None
    hours_worked: Decimal | None = None
    expenses_jsonb: dict[str, Decimal] | None = None


class SideIncomeEconomicsOut(_Out):
    income_stream_id: int
    period_start: date
    period_end: date
    gross: Decimal | None = None
    hours_worked: Decimal | None = None
    expenses_jsonb: dict[str, Decimal] | None = None
    net: Decimal | None = None         # computed: gross - sum(expenses)
    net_hourly: Decimal | None = None  # computed: net / hours_worked
    created_at: datetime


# --- tax_deductions_1099 ---
class TaxDeduction1099In(_In):
    tax_year: int
    category: str
    amount: Decimal | None = None
    evidence_note: str | None = None


class TaxDeduction1099Out(_Out):
    tax_year: int
    category: str
    amount: Decimal | None = None
    evidence_note: str | None = None
    created_at: datetime


# --- negotiation_milestones ---
class NegotiationMilestoneIn(_In):
    kind: str
    trigger_date: date
    related_role: str | None = None
    prep_notes: str | None = None
    status: str | None = None
    completed_at: datetime | None = None


class NegotiationMilestoneOut(_Out):
    kind: str
    trigger_date: date
    related_role: str | None = None
    prep_notes: str | None = None
    status: str
    completed_at: datetime | None = None
    created_at: datetime


# --- net_worth_snapshots ---
class NetWorthSnapshotIn(_In):
    snapshot_at: datetime
    assets_total: Decimal | None = None
    liabilities_total: Decimal | None = None
    asset_breakdown_jsonb: dict[str, Decimal] | None = None
    liability_breakdown_jsonb: dict[str, Decimal] | None = None
    source: str | None = None


class NetWorthSnapshotOut(_Out):
    snapshot_at: datetime
    assets_total: Decimal | None = None
    liabilities_total: Decimal | None = None
    net_worth: Decimal | None = None  # computed: assets_total - liabilities_total
    asset_breakdown_jsonb: dict[str, Decimal] | None = None
    liability_breakdown_jsonb: dict[str, Decimal] | None = None
    source: str
    created_at: datetime
