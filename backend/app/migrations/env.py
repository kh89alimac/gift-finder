"""Alembic environment — async edition.

We run migrations against an ``AsyncEngine`` driven by ``asyncpg``. The
``run_migrations_online`` path uses ``connection.run_sync`` to invoke Alembic's
synchronous migration runner inside an async transaction, which is the
officially-supported pattern.

All models must be imported *before* ``target_metadata`` is read so that
autogenerate sees every table. Importing the ``app.models`` package is enough.
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# IMPORTANT: importing this package registers all model tables on Base.metadata.
from app.core.config import settings
from app.models import Base  # noqa: F401

# ---------------------------------------------------------------------------
# Alembic Config
# ---------------------------------------------------------------------------

config = context.config

# Inject the runtime DSN from app settings so the alembic.ini stub URL is
# never used in practice. We use the ASYNC URL — the engine factory below
# supports it.
config.set_main_option("sqlalchemy.url", str(settings.DATABASE_URL))

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

# pgvector and the custom ENUM types live in the public schema by default,
# so we don't need to set ``include_schemas`` here.


# ---------------------------------------------------------------------------
# Migration runners
# ---------------------------------------------------------------------------


def _run_migrations(connection: Connection) -> None:
    """Synchronous migration runner; called via ``connection.run_sync``."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Compare types and server defaults so autogenerate notices schema
        # drift, not just structural changes.
        compare_type=True,
        compare_server_default=True,
        # Render server-side defaults verbatim so we don't double-quote.
        render_as_batch=False,
        # Include any ENUM types we created manually.
        include_object=lambda *_: True,
        # Use a transaction per migration step.
        transaction_per_migration=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Run migrations against a URL string (no live DB connection).

    Useful for ``alembic upgrade --sql`` to generate raw SQL files.
    """
    context.configure(
        url=str(settings.DATABASE_URL),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations against the live (async) database."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
        future=True,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
