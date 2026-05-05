"""Async Redis client singleton.

Used for token JTI tracking, rate limiting, scrape job progress, and
recommendation caches. We use a single connection pool for the lifetime of
the process — created lazily so test code can monkey-patch settings before
the first request.
"""

from __future__ import annotations

from typing import Any

import redis.asyncio as redis_asyncio

from app.core.config import settings

_client: redis_asyncio.Redis | None = None


def get_redis() -> redis_asyncio.Redis:
    """Return the shared async Redis client, creating it on first use."""
    global _client
    if _client is None:
        _client = redis_asyncio.from_url(
            str(settings.REDIS_URL),
            encoding="utf-8",
            decode_responses=True,
            health_check_interval=30,
        )
    return _client


async def close_redis() -> None:
    """Close the shared client. Idempotent."""
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None


async def ping_redis() -> bool:
    """Best-effort liveness check used at startup."""
    client = get_redis()
    try:
        return bool(await client.ping())
    except Exception:  # pragma: no cover - depends on infra
        return False


def reset_for_testing(client: Any | None = None) -> None:
    """Replace the singleton client (tests only)."""
    global _client
    _client = client
