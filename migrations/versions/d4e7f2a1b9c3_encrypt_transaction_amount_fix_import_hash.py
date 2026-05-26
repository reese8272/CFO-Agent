"""Encrypt transactions.amount; fix import_hash partial unique index; add FK indexes

Revision ID: d4e7f2a1b9c3
Revises: c9f3a1d8e520
Create Date: 2026-05-26
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy import text

revision = 'd4e7f2a1b9c3'
down_revision = 'c9f3a1d8e520'
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # --- 1. Encrypt transactions.amount ---
    # Add the new encrypted column (BYTEA — EncryptedNumeric uses LargeBinary)
    op.add_column("transactions", sa.Column("amount_encrypted", sa.LargeBinary(), nullable=True))

    # Encrypt existing rows using the Fernet key from the environment
    from crypto import encrypt  # noqa: PLC0415
    rows = conn.execute(text("SELECT id, amount FROM transactions WHERE amount IS NOT NULL")).fetchall()
    for row_id, amount in rows:
        ciphertext = encrypt(str(amount))
        conn.execute(
            text("UPDATE transactions SET amount_encrypted = :ct WHERE id = :id"),
            {"ct": ciphertext, "id": row_id},
        )

    # Make amount_encrypted NOT NULL now that all rows are populated
    op.alter_column("transactions", "amount_encrypted", nullable=False)

    # Drop the old plaintext column
    op.drop_column("transactions", "amount")

    # --- 2. Fix import_hash unique constraint → partial unique index ---
    # Drop the broad unique constraint (covers NULLs ambiguously in some DB paths)
    op.drop_constraint("uq_transactions_import_hash", "transactions", type_="unique")

    # Add a partial unique index: only enforce uniqueness for non-NULL hashes
    op.create_index(
        "ix_transactions_import_hash_notnull",
        "transactions",
        ["import_hash"],
        unique=True,
        postgresql_where=text("import_hash IS NOT NULL"),
    )

    # --- 3. FK indexes for common join columns (only columns verified to exist) ---
    op.create_index("ix_transactions_account_id", "transactions", ["account_id"])
    op.create_index("ix_transactions_import_batch_id", "transactions", ["import_batch_id"])
    op.create_index("ix_cards_account_id", "cards", ["account_id"])
    op.create_index("ix_expenses_account_id", "expenses", ["account_id"])
    op.create_index("ix_import_batches_account_id", "import_batches", ["account_id"])
    op.create_index("ix_holdings_account_id", "holdings", ["account_id"])
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])


def downgrade() -> None:
    conn = op.get_bind()

    # Restore plaintext amount column from encrypted data
    op.add_column("transactions", sa.Column("amount", sa.Numeric(precision=18, scale=4), nullable=True))

    from crypto import decrypt  # noqa: PLC0415
    rows = conn.execute(text("SELECT id, amount_encrypted FROM transactions WHERE amount_encrypted IS NOT NULL")).fetchall()
    for row_id, ciphertext in rows:
        plaintext = decrypt(bytes(ciphertext))
        conn.execute(
            text("UPDATE transactions SET amount = :amt WHERE id = :id"),
            {"amt": plaintext, "id": row_id},
        )

    op.alter_column("transactions", "amount", nullable=False)
    op.drop_column("transactions", "amount_encrypted")

    # Restore UniqueConstraint
    op.drop_index("ix_transactions_import_hash_notnull", table_name="transactions")
    op.create_unique_constraint("uq_transactions_import_hash", "transactions", ["import_hash"])

    # Drop FK indexes
    op.drop_index("ix_transactions_account_id", table_name="transactions")
    op.drop_index("ix_transactions_import_batch_id", table_name="transactions")
    op.drop_index("ix_cards_account_id", table_name="cards")
    op.drop_index("ix_expenses_account_id", table_name="expenses")
    op.drop_index("ix_import_batches_account_id", table_name="import_batches")
    op.drop_index("ix_holdings_account_id", table_name="holdings")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
