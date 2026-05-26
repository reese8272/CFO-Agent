"""add import_batches, category_mappings, and transactions tables

Revision ID: b5e2a9c3f107
Revises: a3f1c8d2e749
Create Date: 2026-05-25
"""
from alembic import op
import sqlalchemy as sa

revision = "b5e2a9c3f107"
down_revision = "a3f1c8d2e749"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "import_batches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("file_format", sa.String(8), nullable=False),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "category_mappings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("pattern", sa.String(256), unique=True, nullable=False),
        sa.Column("category", sa.String(64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_id", sa.Integer(), sa.ForeignKey("accounts.id"), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=False),
        sa.Column("description", sa.String(512), nullable=True),
        sa.Column("category", sa.String(64), nullable=True),
        sa.Column("import_batch_id", sa.Integer(), sa.ForeignKey("import_batches.id"), nullable=True),
        sa.Column("import_hash", sa.String(64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.UniqueConstraint("import_hash", name="uq_transactions_import_hash"),
    )


def downgrade() -> None:
    op.drop_table("transactions")
    op.drop_table("category_mappings")
    op.drop_table("import_batches")
