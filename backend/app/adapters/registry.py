"""Dynamic adapter registry.

Adapters register themselves at import time. The orchestrator looks up the
class by the dotted-path stored in ``scraper_sites.adapter_class``, which
makes adding a new site a config-only operation.
"""

from __future__ import annotations

import importlib
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.adapters.base import BaseScrapeAdapter

ADAPTERS: dict[str, type["BaseScrapeAdapter"]] = {}


def register_adapter(cls: type["BaseScrapeAdapter"]) -> type["BaseScrapeAdapter"]:
    """Class decorator: register ``cls`` under its dotted import path."""
    path = f"{cls.__module__}.{cls.__qualname__}"
    ADAPTERS[path] = cls
    return cls


def resolve_adapter(adapter_class_path: str) -> type["BaseScrapeAdapter"]:
    """Look up an adapter class by dotted path, importing the module if needed."""
    if adapter_class_path in ADAPTERS:
        return ADAPTERS[adapter_class_path]

    module_path, _, attr = adapter_class_path.rpartition(".")
    if not module_path:
        raise KeyError(f"Adapter path is not fully qualified: {adapter_class_path!r}")
    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise KeyError(f"Cannot import adapter module {module_path!r}: {exc}") from exc

    cls = getattr(module, attr, None)
    if cls is None:
        raise KeyError(f"Module {module_path!r} has no attribute {attr!r}")

    # Cache for next time.
    ADAPTERS[adapter_class_path] = cls
    return cls
