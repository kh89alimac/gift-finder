"""Scraper adapters.

Each retailer site defines its own concrete adapter that yields ``ScrapeResult``
items. Adapters are loaded dynamically from the ``scraper_sites.adapter_class``
column so adding a new site is purely a configuration change once the class
is registered in :mod:`app.adapters.registry`.
"""

from app.adapters.base import BaseScrapeAdapter, ScrapeResult
from app.adapters.registry import ADAPTERS, register_adapter, resolve_adapter

__all__ = [
    "ADAPTERS",
    "BaseScrapeAdapter",
    "ScrapeResult",
    "register_adapter",
    "resolve_adapter",
]
