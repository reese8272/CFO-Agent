"""Alembic environment.

Reads DATABASE_URL from the project's config.py (not alembic.ini) so the
migration runner uses the same connection string the app uses.

The model modules (vault, memory, auth) are imported ONLY for
``alembic revision --autogenerate``, which needs a populated ``Base.metadata``
to diff against. ``alembic upgrade`` (the deploy path) just replays migration
scripts and never consults the metadata, so we skip those imports there —
importing ``auth`` alone drags in the FastAPI/jwt/bcrypt graph and is the bulk
of the multi-minute alembic startup on the deploy host.
"""
import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import MetaData, pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

from alembic import context

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config import get_settings  # noqa: E402
from db import Base  # noqa: E402

alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

alembic_config.set_main_option("sqlalchemy.url", get_settings().database_url)


def _load_model_metadata() -> MetaData:
    """Populate Base.metadata by importing every model module (autogenerate only)."""
    import vault.models  # noqa: F401 — register models with Base.metadata
    import memory.models  # noqa: F401 — register models with Base.metadata
    import auth  # noqa: F401 — register the User model with Base.metadata
    return Base.metadata


# Only autogenerate needs the models loaded; upgrade/downgrade do not.
_cmd_opts = getattr(alembic_config, "cmd_opts", None)
if getattr(_cmd_opts, "autogenerate", False):
    target_metadata = _load_model_metadata()
else:
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
