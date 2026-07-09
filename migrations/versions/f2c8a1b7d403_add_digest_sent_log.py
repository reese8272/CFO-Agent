"""add digest_sent_log for idempotent weekly digest

Revision ID: f2c8a1b7d403
Revises: a7e3f9c21b84
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa

revision = "f2c8a1b7d403"
down_revision = "a7e3f9c21b84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "digest_sent_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("year_week", sa.String(length=10), nullable=False, unique=True),
        sa.Column(
            "sent_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("digest_sent_log")
