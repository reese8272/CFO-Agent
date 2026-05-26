"""Vault ORM models — all financial data lives here, encrypted at rest.

Columns named `*_encrypted` in the DB store Fernet ciphertext (bytea).
The Python attribute uses the clean name and exposes the decrypted value
via the EncryptedString / EncryptedNumeric / EncryptedJSON TypeDecorators
in crypto.py. Money is always Decimal, never float.
"""
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Date, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, event, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from crypto import EncryptedJSON, EncryptedNumeric, EncryptedString
from db import Base


class AuditLogImmutableError(RuntimeError):
    """Raised when code attempts to mutate or delete an AuditLog row."""


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    type: Mapped[str] = mapped_column(String(32))
    institution: Mapped[str] = mapped_column(String(128))
    nickname: Mapped[str] = mapped_column(String(128))
    current_balance: Mapped[Decimal | None] = mapped_column(
        "current_balance_encrypted", EncryptedNumeric(), nullable=True
    )
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    plaid_account_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Card(Base):
    __tablename__ = "cards"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    issuer: Mapped[str] = mapped_column(String(64))
    network: Mapped[str] = mapped_column(String(32))
    last4: Mapped[str | None] = mapped_column(
        "last4_encrypted", EncryptedString(), nullable=True
    )
    benefits_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    credit_limit: Mapped[Decimal | None] = mapped_column(
        "credit_limit_encrypted", EncryptedNumeric(), nullable=True
    )
    statement_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    due_day: Mapped[int | None] = mapped_column(Integer, nullable=True)
    autopay: Mapped[bool] = mapped_column(default=False)
    current_cycle_spend: Mapped[Decimal | None] = mapped_column(
        "current_cycle_spend_encrypted", EncryptedNumeric(), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class IncomeStream(Base):
    __tablename__ = "income_streams"

    id: Mapped[int] = mapped_column(primary_key=True)
    source: Mapped[str] = mapped_column(String(128))
    source_type: Mapped[str] = mapped_column(String(32))
    cadence: Mapped[str] = mapped_column(String(32))
    typical_gross_amount: Mapped[Decimal | None] = mapped_column(
        "typical_gross_amount_encrypted", EncryptedNumeric(), nullable=True
    )
    tax_treatment_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    rolling_4wk_avg: Mapped[Decimal | None] = mapped_column(
        "rolling_4wk_avg_encrypted", EncryptedNumeric(), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Expense(Base):
    __tablename__ = "expenses"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    cadence: Mapped[str] = mapped_column(String(32))
    typical_amount: Mapped[Decimal | None] = mapped_column(
        "typical_amount_encrypted", EncryptedNumeric(), nullable=True
    )
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id"), nullable=True)
    card_id: Mapped[int | None] = mapped_column(ForeignKey("cards.id"), nullable=True)
    active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Debt(Base):
    __tablename__ = "debts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    balance: Mapped[Decimal | None] = mapped_column(
        "balance_encrypted", EncryptedNumeric(), nullable=True
    )
    apr: Mapped[Decimal | None] = mapped_column(
        "apr_encrypted", EncryptedNumeric(), nullable=True
    )
    minimum_payment: Mapped[Decimal | None] = mapped_column(
        "minimum_payment_encrypted", EncryptedNumeric(), nullable=True
    )
    strategy: Mapped[str] = mapped_column(String(32), default="avalanche")
    priority_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Asset(Base):
    __tablename__ = "assets"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    nickname: Mapped[str] = mapped_column(String(128))
    value_estimate: Mapped[Decimal | None] = mapped_column(
        "value_estimate_encrypted", EncryptedNumeric(), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RealEstate(Base):
    __tablename__ = "real_estate"

    id: Mapped[int] = mapped_column(primary_key=True)
    address: Mapped[str | None] = mapped_column(
        "address_encrypted", EncryptedString(), nullable=True
    )
    purchase_price: Mapped[Decimal | None] = mapped_column(
        "purchase_price_encrypted", EncryptedNumeric(), nullable=True
    )
    current_value: Mapped[Decimal | None] = mapped_column(
        "current_value_encrypted", EncryptedNumeric(), nullable=True
    )
    mortgage_balance: Mapped[Decimal | None] = mapped_column(
        "mortgage_balance_encrypted", EncryptedNumeric(), nullable=True
    )
    mortgage_apr: Mapped[Decimal | None] = mapped_column(
        "mortgage_apr_encrypted", EncryptedNumeric(), nullable=True
    )
    monthly_payment: Mapped[Decimal | None] = mapped_column(
        "monthly_payment_encrypted", EncryptedNumeric(), nullable=True
    )
    property_type: Mapped[str] = mapped_column(String(32))
    monthly_rent: Mapped[Decimal | None] = mapped_column(
        "monthly_rent_encrypted", EncryptedNumeric(), nullable=True
    )
    equity_estimate: Mapped[Decimal | None] = mapped_column(
        "equity_estimate_encrypted", EncryptedNumeric(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class BusinessIncome(Base):
    __tablename__ = "business_income"

    id: Mapped[int] = mapped_column(primary_key=True)
    business_name: Mapped[str] = mapped_column(String(128))
    entity_type: Mapped[str] = mapped_column(String(32))
    monthly_revenue: Mapped[Decimal | None] = mapped_column(
        "monthly_revenue_encrypted", EncryptedNumeric(), nullable=True
    )
    monthly_expenses: Mapped[Decimal | None] = mapped_column(
        "monthly_expenses_encrypted", EncryptedNumeric(), nullable=True
    )
    net_margin: Mapped[Decimal | None] = mapped_column(
        "net_margin_encrypted", EncryptedNumeric(), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class RetirementAccount(Base):
    __tablename__ = "retirement_accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    institution: Mapped[str] = mapped_column(String(128))
    ytd_contribution: Mapped[Decimal | None] = mapped_column(
        "ytd_contribution_encrypted", EncryptedNumeric(), nullable=True
    )
    balance: Mapped[Decimal | None] = mapped_column(
        "balance_encrypted", EncryptedNumeric(), nullable=True
    )
    ytd_contribution_limit_remaining: Mapped[Decimal | None] = mapped_column(
        "ytd_contribution_limit_remaining_encrypted", EncryptedNumeric(), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(256))
    kind: Mapped[str] = mapped_column(String(32))
    target_amount: Mapped[Decimal | None] = mapped_column(
        "target_amount_encrypted", EncryptedNumeric(), nullable=True
    )
    current_amount: Mapped[Decimal | None] = mapped_column(
        "current_amount_encrypted", EncryptedNumeric(), nullable=True
    )
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    priority: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CareerPosition(Base):
    __tablename__ = "career_position"

    id: Mapped[int] = mapped_column(primary_key=True)
    current_role: Mapped[str] = mapped_column(String(128))
    current_employer: Mapped[str] = mapped_column(String(128))
    current_comp_total: Mapped[Decimal | None] = mapped_column(
        "current_comp_total_encrypted", EncryptedNumeric(), nullable=True
    )
    target_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    target_comp_total: Mapped[Decimal | None] = mapped_column(
        "target_comp_total_encrypted", EncryptedNumeric(), nullable=True
    )
    target_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    cert_or_milestone_jsonb: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class CareerHistory(Base):
    __tablename__ = "career_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(128))
    employer: Mapped[str] = mapped_column(String(128))
    comp_total: Mapped[Decimal | None] = mapped_column(
        "comp_total_encrypted", EncryptedNumeric(), nullable=True
    )
    start_date: Mapped[date] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    reason_for_leaving: Mapped[str | None] = mapped_column(String(32), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CompBenchmark(Base):
    __tablename__ = "comp_benchmarks"

    id: Mapped[int] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(String(128))
    metro: Mapped[str] = mapped_column(String(128))
    source: Mapped[str] = mapped_column(String(32))
    comp_p50: Mapped[Decimal | None] = mapped_column(
        "comp_p50_encrypted", EncryptedNumeric(), nullable=True
    )
    comp_p75: Mapped[Decimal | None] = mapped_column(
        "comp_p75_encrypted", EncryptedNumeric(), nullable=True
    )
    comp_p90: Mapped[Decimal | None] = mapped_column(
        "comp_p90_encrypted", EncryptedNumeric(), nullable=True
    )
    as_of_date: Mapped[date] = mapped_column(Date)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SideIncomeEconomics(Base):
    __tablename__ = "side_income_economics"

    id: Mapped[int] = mapped_column(primary_key=True)
    income_stream_id: Mapped[int] = mapped_column(ForeignKey("income_streams.id"))
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    gross: Mapped[Decimal | None] = mapped_column(
        "gross_encrypted", EncryptedNumeric(), nullable=True
    )
    hours_worked: Mapped[Decimal | None] = mapped_column(
        "hours_worked_encrypted", EncryptedNumeric(), nullable=True
    )
    expenses_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    net: Mapped[Decimal | None] = mapped_column(
        "net_encrypted", EncryptedNumeric(), nullable=True
    )
    net_hourly: Mapped[Decimal | None] = mapped_column(
        "net_hourly_encrypted", EncryptedNumeric(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class TaxDeduction1099(Base):
    __tablename__ = "tax_deductions_1099"

    id: Mapped[int] = mapped_column(primary_key=True)
    tax_year: Mapped[int] = mapped_column(Integer)
    category: Mapped[str] = mapped_column(String(32))
    amount: Mapped[Decimal | None] = mapped_column(
        "amount_encrypted", EncryptedNumeric(), nullable=True
    )
    evidence_note: Mapped[str | None] = mapped_column(
        "evidence_note_encrypted", EncryptedString(), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NegotiationMilestone(Base):
    __tablename__ = "negotiation_milestones"

    id: Mapped[int] = mapped_column(primary_key=True)
    kind: Mapped[str] = mapped_column(String(32))
    trigger_date: Mapped[date] = mapped_column(Date)
    related_role: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prep_notes: Mapped[str | None] = mapped_column(
        "prep_notes_encrypted", EncryptedString(), nullable=True
    )
    status: Mapped[str] = mapped_column(String(32), default="upcoming")
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class NetWorthSnapshot(Base):
    __tablename__ = "net_worth_snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    snapshot_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    assets_total: Mapped[Decimal | None] = mapped_column(
        "assets_total_encrypted", EncryptedNumeric(), nullable=True
    )
    liabilities_total: Mapped[Decimal | None] = mapped_column(
        "liabilities_total_encrypted", EncryptedNumeric(), nullable=True
    )
    net_worth: Mapped[Decimal | None] = mapped_column(
        "net_worth_encrypted", EncryptedNumeric(), nullable=True
    )
    asset_breakdown_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    liability_breakdown_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    source: Mapped[str] = mapped_column(String(32), default="manual")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Holdings(Base):
    __tablename__ = "holdings"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"))
    ticker: Mapped[str] = mapped_column(String(16))
    share_count: Mapped[Decimal | None] = mapped_column(
        "share_count_encrypted", EncryptedNumeric(), nullable=True
    )
    cost_basis: Mapped[Decimal | None] = mapped_column(
        "cost_basis_encrypted", EncryptedNumeric(), nullable=True
    )
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_known_price: Mapped[Decimal | None] = mapped_column(
        "last_known_price", EncryptedNumeric(), nullable=True
    )
    last_priced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class SideIncomeEvent(Base):
    __tablename__ = "side_income_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    income_stream_id: Mapped[int] = mapped_column(ForeignKey("income_streams.id"))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    gross: Mapped[Decimal | None] = mapped_column(
        "gross_encrypted", EncryptedNumeric(), nullable=True
    )
    stream_specific_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    notes: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    actor: Mapped[str] = mapped_column(String(128))
    action: Mapped[str] = mapped_column(String(32))
    entity_type: Mapped[str] = mapped_column(String(64))
    entity_id: Mapped[int] = mapped_column(Integer)
    before_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)
    after_jsonb: Mapped[dict | None] = mapped_column(EncryptedJSON(), nullable=True)


def _block_audit_log_mutation(mapper, connection, target) -> None:
    raise AuditLogImmutableError(
        "audit_log is append-only; UPDATE and DELETE are not permitted"
    )


event.listen(AuditLog, "before_update", _block_audit_log_mutation)
event.listen(AuditLog, "before_delete", _block_audit_log_mutation)


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    file_format: Mapped[str] = mapped_column(String(8), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CategoryMapping(Base):
    __tablename__ = "category_mappings"

    id: Mapped[int] = mapped_column(primary_key=True)
    pattern: Mapped[str] = mapped_column(String(256), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class Transaction(Base):
    """Promoted from Phase 2 stub to v1 for CSV/OFX import (Issue 4c)."""

    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("import_hash", name="uq_transactions_import_hash"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False)
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(precision=18, scale=4), nullable=False)
    description: Mapped[str | None] = mapped_column(String(512), nullable=True)
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    import_batch_id: Mapped[int | None] = mapped_column(
        ForeignKey("import_batches.id"), nullable=True
    )
    import_hash: Mapped[str | None] = mapped_column(String(64), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
