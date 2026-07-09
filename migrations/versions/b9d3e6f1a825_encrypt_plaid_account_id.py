"""encrypt accounts.plaid_account_id at rest

Revision ID: b9d3e6f1a825
Revises: f2c8a1b7d403
Create Date: 2026-07-09
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = "b9d3e6f1a825"
down_revision = "f2c8a1b7d403"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # New encrypted column (BYTEA — EncryptedString uses LargeBinary)
    op.add_column(
        "accounts", sa.Column("plaid_account_id_encrypted", sa.LargeBinary(), nullable=True)
    )

    # Encrypt existing values using the Fernet key from the environment
    from crypto import encrypt  # noqa: PLC0415
    rows = conn.execute(
        text("SELECT id, plaid_account_id FROM accounts WHERE plaid_account_id IS NOT NULL")
    ).fetchall()
    for row_id, plaintext in rows:
        conn.execute(
            text("UPDATE accounts SET plaid_account_id_encrypted = :ct WHERE id = :id"),
            {"ct": encrypt(plaintext), "id": row_id},
        )

    # Column stays nullable (Plaid is deferred; most rows have no value)
    op.drop_column("accounts", "plaid_account_id")


def downgrade() -> None:
    conn = op.get_bind()

    op.add_column(
        "accounts", sa.Column("plaid_account_id", sa.String(length=128), nullable=True)
    )

    from crypto import decrypt  # noqa: PLC0415
    rows = conn.execute(
        text(
            "SELECT id, plaid_account_id_encrypted FROM accounts "
            "WHERE plaid_account_id_encrypted IS NOT NULL"
        )
    ).fetchall()
    for row_id, ciphertext in rows:
        conn.execute(
            text("UPDATE accounts SET plaid_account_id = :pt WHERE id = :id"),
            {"pt": decrypt(bytes(ciphertext)), "id": row_id},
        )

    op.drop_column("accounts", "plaid_account_id_encrypted")
