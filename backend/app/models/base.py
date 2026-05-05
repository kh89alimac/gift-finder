"""Declarative base + reusable mixins.

All models inherit from ``Base``; tables that need ``created_at`` / ``updated_at``
columns inherit from ``TimestampMixin`` as well.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import MetaData, text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

# A consistent naming convention so Alembic autogenerate produces stable, sane
# constraint names. Without this you'll get random hex suffixes that change
# between machines and break diffs.
NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}

metadata = MetaData(naming_convention=NAMING_CONVENTION)


class Base(DeclarativeBase):
    """Project-wide declarative base. Every model inherits from this class."""

    metadata = metadata


class TimestampMixin:
    """Adds ``created_at`` and ``updated_at`` managed by the database.

    ``updated_at`` is bumped by a Postgres trigger (installed in the initial
    migration) so it is consistent regardless of how the row was modified —
    including bulk updates that bypass the ORM.
    """

    created_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"),
        nullable=False,
        index=True,
    )
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text("NOW()"),
        nullable=False,
    )
