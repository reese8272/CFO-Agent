"""Alembic environment.

Reads DATABASE_URL from the project's config.py (not alembic.ini) so the
migration runner uses the same connection string the app uses. Imports
the vault and memory model modules so Base.metadata is populated for
autogenerate.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings  # noqa: E402
from db import Base  # noqa: E402
import vault.models  # noqa: E402, F401 — register models with Base.metadata
import memory.models  # noqa: E402, F401 — register models with Base.metadata
import auth  # noqa: E402, F401 — register the User model with Base.metadata

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

alembic_config.set_main_option("sqlalchemy.url", get_settings().database_url)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = alembic_config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        # Fail fast instead of blocking indefinitely if a migration contends for
        # a lock during a deploy rollover (ISSUE-2026-07-02-01). SET LOCAL scopes
        # this to the migration transaction only.
        connection.exec_driver_sql("SET LOCAL lock_timeout = '30s'")
        context.run_migrations()


async def run_async_migrations() -> None:
    connectable = async_engine_from_config(
        alembic_config.get_section(alembic_config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
