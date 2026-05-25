"""Add holdings and side_income_events tables.

Revision ID: a3f1c8d2e749
Revises: 7f3a9c2b5e81
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "a3f1c8d2e749"
down_revision = "7f3a9c2b5e81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "holdings",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("account_id", sa.Integer, sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("share_count_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("cost_basis_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("purchase_date", sa.Date, nullable=True),
        sa.Column("last_known_price", sa.LargeBinary, nullable=True),
        sa.Column("last_priced_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_holdings_account_ticker", "holdings", ["account_id", "ticker"])

    op.create_table(
        "side_income_events",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column(
            "income_stream_id",
            sa.Integer,
            sa.ForeignKey("income_streams.id"),
            nullable=False,
        ),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("duration_minutes", sa.Integer, nullable=True),
        sa.Column("gross_encrypted", sa.LargeBinary, nullable=True),
        sa.Column("stream_specific_jsonb", sa.LargeBinary, nullable=True),
        sa.Column("notes", sa.String(1024), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_side_income_events_stream_occurred",
        "side_income_events",
        ["income_stream_id", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_side_income_events_stream_occurred", table_name="side_income_events")
    op.drop_table("side_income_events")
    op.drop_index("ix_holdings_account_ticker", table_name="holdings")
    op.drop_table("holdings")
