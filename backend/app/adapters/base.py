"""Adapter base class + result dataclass.

Adapters must be async iterators so they can stream results without holding
the whole catalog in memory. The orchestrator drains the iterator and feeds
results into the dedup + persistence pipeline.
"""

from __future__ import annotations

import abc
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


@dataclass
class ScrapeResult:
    """One product yielded by an adapter.

    ``source_external_id`` is used together with the site id for dedup; it
    must be stable across runs. If the source has no obvious id we fall back
    to a hash of the product URL.
    """

    source_external_id: str
    title: str
    product_url: str
    description: str | None = None
    price: Decimal | None = None
    currency: str = "USD"
    image_url: str | None = None
    brand: str | None = None
    retailer: str | None = None
    source_url: str | None = None
    published_at: datetime | None = None
    raw: dict[str, Any] = field(default_factory=dict)


class BaseScrapeAdapter(abc.ABC):
    """Abstract base for all retailer scrape adapters.

    Subclasses receive the ``ScraperSite`` config dict on init and must
    implement ``scrape`` (an async iterator) and ``health_check``.
    """

    name: str = "base"

    def __init__(self, config: dict[str, Any], *, user_agent: str = "GiftFinderBot") -> None:
        self.config = config
        self.user_agent = user_agent

    @abc.abstractmethod
    def scrape(self) -> AsyncIterator[ScrapeResult]:
        """Yield ``ScrapeResult`` instances. Must be an async generator."""
        ...

    @abc.abstractmethod
    async def health_check(self) -> bool:
        """Return True if the source is reachable + the adapter still parses it."""
        ...
