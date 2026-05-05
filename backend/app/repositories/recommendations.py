"""Recommendation signal repository.

Signals are per-(user, tag) scores updated whenever a user interacts with an
item. We use INSERT ... ON CONFLICT to upsert atomically — interactions are
high volume and we want each event to be one round-trip.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.admin import RecommendationSignal
from app.models.taxonomy import Tag
from app.repositories.base import BaseRepository


class RecommendationRepository(BaseRepository[RecommendationSignal]):
    model = RecommendationSignal

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, RecommendationSignal)

    async def upsert_signal(
        self,
        user_id: uuid.UUID,
        tag_id: int,
        *,
        score_delta: Decimal,
    ) -> None:
        """Add ``score_delta`` to the user's score for ``tag_id``.

        Creates the row if it doesn't exist; otherwise increments score and
        interaction_count atomically. Single statement, no read-modify-write
        race.
        """
        stmt = pg_insert(RecommendationSignal).values(
            user_id=user_id,
            tag_id=tag_id,
            score=score_delta,
            interaction_count=1,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "tag_id"],
            set_={
                "score": RecommendationSignal.score + stmt.excluded.score,
                "interaction_count": RecommendationSignal.interaction_count + 1,
                "updated_at": func.now(),
            },
        )
        await self.session.execute(stmt)

    async def upsert_signals_bulk(
        self,
        user_id: uuid.UUID,
        tag_score_pairs: Sequence[tuple[int, Decimal]],
    ) -> None:
        """Upsert many signals at once — useful when one item has many tags."""
        if not tag_score_pairs:
            return
        rows = [
            {
                "user_id": user_id,
                "tag_id": tag_id,
                "score": score_delta,
                "interaction_count": 1,
            }
            for tag_id, score_delta in tag_score_pairs
        ]
        stmt = pg_insert(RecommendationSignal).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["user_id", "tag_id"],
            set_={
                "score": RecommendationSignal.score + stmt.excluded.score,
                "interaction_count": (
                    RecommendationSignal.interaction_count
                    + stmt.excluded.interaction_count
                ),
                "updated_at": func.now(),
            },
        )
        await self.session.execute(stmt)

    async def top_tags_for_user(
        self, user_id: uuid.UUID, *, limit: int = 20
    ) -> list[tuple[Tag, Decimal]]:
        """Return the user's highest-scoring tags with the Tag eagerly joined."""
        stmt = (
            select(Tag, RecommendationSignal.score)
            .join(RecommendationSignal, RecommendationSignal.tag_id == Tag.id)
            .where(RecommendationSignal.user_id == user_id)
            .order_by(RecommendationSignal.score.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return [(row.Tag, row.score) for row in result.all()]
