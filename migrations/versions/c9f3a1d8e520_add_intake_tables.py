"""add intake, financial_snapshot, and user_profile tables

Revision ID: c9f3a1d8e520
Revises: b5e2a9c3f107
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa

revision = 'c9f3a1d8e520'
down_revision = 'b5e2a9c3f107'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'user_profile',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('age', sa.Integer(), nullable=True),
        sa.Column('household_size', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('dependents', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('state_of_residence', sa.String(2), nullable=True),
        sa.Column('tax_filing_status', sa.String(32), nullable=True),
        sa.Column('last_year_agi_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('has_hsa_eligible_plan', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('intake_completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'financial_snapshots',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('computed_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('net_worth_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('total_assets_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('total_liabilities_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('total_monthly_income_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('total_monthly_expenses_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('allocation_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('income_step', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('savings_rate_pct_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('debt_to_income_ratio_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('emergency_months_covered_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('roth_utilization_pct_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('k401_match_capture_pct_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('hsa_utilization_pct_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('career_comp_vs_p50_pct_encrypted', sa.LargeBinary(), nullable=True),
        sa.Column('analysis_jsonb', sa.LargeBinary(), nullable=True),
        sa.Column('vault_hash', sa.String(64), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'intake_submissions',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('submitted_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('raw_data', sa.LargeBinary(), nullable=True),
        sa.Column('snapshot_id', sa.Integer(), sa.ForeignKey('financial_snapshots.id'), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    op.drop_table('intake_submissions')
    op.drop_table('financial_snapshots')
    op.drop_table('user_profile')
