"""add missing FK + sort indexes (assessment 2026-07-02)

The head migration d4e7f2a1b9c3 already indexed most FK columns; this adds the
remaining ones the ORM models never declared, plus the two ORDER BY/filter
columns the per-request retrieval + snapshot lookups hit.

Plain `create_index` (not CONCURRENTLY): these are small single-user tables and
this matches the d4e7 precedent; `migrations/env.py` sets a 30s SET LOCAL
lock_timeout so a blocked build fails fast rather than hanging the deploy.

Revision ID: a7e3f9c21b84
Revises: d4e7f2a1b9c3
Create Date: 2026-07-02
"""
from alembic import op

revision = "a7e3f9c21b84"
down_revision = "d4e7f2a1b9c3"
branch_labels = None
depends_on = None

_INDEXES = [
    ("ix_expenses_card_id", "expenses", ["card_id"]),
    ("ix_side_income_economics_income_stream_id", "side_income_economics", ["income_stream_id"]),
    ("ix_intake_submissions_snapshot_id", "intake_submissions", ["snapshot_id"]),
    ("ix_patterns_detected_at", "patterns", ["detected_at"]),
    ("ix_financial_snapshots_computed_at", "financial_snapshots", ["computed_at"]),
]


def upgrade() -> None:
    for name, table, cols in _INDEXES:
        op.create_index(name, table, cols)


def downgrade() -> None:
    for name, table, _cols in reversed(_INDEXES):
        op.drop_index(name, table_name=table)
