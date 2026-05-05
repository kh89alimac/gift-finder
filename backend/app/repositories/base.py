"""Generic CRUD repository.

Concrete repositories should inherit from ``BaseRepository`` and add
domain-specific methods. The base intentionally exposes only the most generic
operations — anything that requires joins, filters, or business logic belongs
on the subclass.
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from sqlalchemy import delete as sa_delete, func, select
from sqlalchemy.exc import NoResultFound
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import Base

ModelT = TypeVar("ModelT", bound=Base)


class BaseRepository(Generic[ModelT]):
    """Generic CRUD repository over a SQLAlchemy mapped class."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession, model: type[ModelT] | None = None) -> None:
        self.session = session
        if model is not None:
            self.model = model
        if not hasattr(self, "model"):
            raise TypeError(
                f"{type(self).__name__} requires a 'model' class attribute or "
                "the model to be passed to __init__."
            )

    # ------------------------------------------------------------------ get
    async def get_by_id(self, id_: Any) -> ModelT | None:
        """Return a row by primary key or ``None`` if not found."""
        return await self.session.get(self.model, id_)

    async def get_by_id_or_raise(self, id_: Any) -> ModelT:
        """Like ``get_by_id`` but raises ``NoResultFound`` instead of returning None."""
        obj = await self.get_by_id(id_)
        if obj is None:
            raise NoResultFound(f"{self.model.__name__} {id_!r} not found")
        return obj

    # ------------------------------------------------------------------ list
    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        order_by: Any | None = None,
    ) -> list[ModelT]:
        """Page through rows. Caller supplies ``order_by`` for stable pagination."""
        stmt = select(self.model).limit(limit).offset(offset)
        if order_by is not None:
            stmt = stmt.order_by(order_by)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count(self) -> int:
        """Return total row count for this model."""
        stmt = select(func.count()).select_from(self.model)
        result = await self.session.execute(stmt)
        return int(result.scalar_one())

    # ---------------------------------------------------------------- create
    async def create(self, **kwargs: Any) -> ModelT:
        """Construct a model from kwargs, persist it, and return it.

        Note: this flushes (so the row gets a server-generated PK) but does
        *not* commit. Commit responsibility lives with the unit of work.
        """
        obj = self.model(**kwargs)
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def add(self, obj: ModelT) -> ModelT:
        """Persist an already-constructed model instance."""
        self.session.add(obj)
        await self.session.flush()
        return obj

    # ---------------------------------------------------------------- update
    async def update(self, obj: ModelT, **changes: Any) -> ModelT:
        """Apply attribute changes and flush."""
        for key, value in changes.items():
            setattr(obj, key, value)
        await self.session.flush()
        return obj

    # ---------------------------------------------------------------- delete
    async def delete(self, obj: ModelT) -> None:
        """Delete the given persisted object."""
        await self.session.delete(obj)
        await self.session.flush()

    async def delete_by_id(self, id_: Any) -> bool:
        """Delete by PK. Returns True if a row was deleted."""
        stmt = sa_delete(self.model).where(self.model.__table__.c.id == id_)
        result = await self.session.execute(stmt)
        return (result.rowcount or 0) > 0
