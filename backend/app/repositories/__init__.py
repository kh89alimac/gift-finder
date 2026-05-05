"""Repository layer.

Each repository encapsulates queries for a single aggregate. Higher-level
business logic should use repositories (or the ``UnitOfWork``) rather than
issuing raw queries against the session.
"""

from app.repositories.base import BaseRepository
from app.repositories.instagram import InstagramQueueRepository
from app.repositories.items import ItemRepository
from app.repositories.recommendations import RecommendationRepository
from app.repositories.scraper_jobs import ScraperJobRepository
from app.repositories.tags import TagRepository
from app.repositories.unit_of_work import UnitOfWork
from app.repositories.wishlists import WishlistRepository

__all__ = [
    "BaseRepository",
    "InstagramQueueRepository",
    "ItemRepository",
    "RecommendationRepository",
    "ScraperJobRepository",
    "TagRepository",
    "UnitOfWork",
    "WishlistRepository",
]
