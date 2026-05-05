"""Instagram Graph API client.

The Graph API is straightforward but rate-limited per access token. We pass
the token in explicitly so callers can rotate or use page-specific tokens
rather than relying on a single global secret.
"""

from __future__ import annotations

from typing import Any

import httpx

from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger
from app.core.safe_http import validate_safe_url

log = get_logger(__name__)

GRAPH_API_BASE = "https://graph.instagram.com"
GRAPH_API_VERSION = "v18.0"

# Default fields we want for any post.
_DEFAULT_FIELDS = ",".join(
    [
        "id",
        "caption",
        "media_url",
        "media_type",
        "permalink",
        "thumbnail_url",
        "timestamp",
        "username",
    ]
)


async def _get(path: str, params: dict[str, Any]) -> dict[str, Any]:
    url = f"{GRAPH_API_BASE}/{GRAPH_API_VERSION}/{path.lstrip('/')}"
    # Defence in depth — even though GRAPH_API_BASE is a constant, we still
    # validate to catch any future code path that builds the URL from input.
    try:
        validate_safe_url(url)
    except ValueError as exc:
        raise ExternalServiceError(f"Refusing unsafe Instagram URL: {exc}") from exc
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.get(url, params=params)
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Instagram API error: {exc}") from exc
    if resp.status_code >= 400:
        log.warning(
            "instagram.api.error",
            status=resp.status_code,
            body=resp.text[:500],
            path=path,
        )
        raise ExternalServiceError(
            f"Instagram API returned {resp.status_code}",
            details={"body": resp.text[:500]},
        )
    return resp.json()


async def get_user_media(
    user_id: str, access_token: str, *, limit: int = 25
) -> list[dict[str, Any]]:
    """Return up to ``limit`` recent media items for a business/creator account."""
    params = {
        "fields": _DEFAULT_FIELDS,
        "limit": limit,
        "access_token": access_token,
    }
    data = await _get(f"{user_id}/media", params)
    items = data.get("data", [])
    if not isinstance(items, list):
        return []
    return items


async def get_hashtag_media(
    hashtag_id: str, access_token: str, *, limit: int = 25
) -> list[dict[str, Any]]:
    """Return recent posts for a tracked hashtag id.

    Note: hashtag ids must be obtained via the ``ig_hashtag_search`` endpoint
    first; we don't bake that lookup in because admins typically pin a small
    set of hashtags rather than discovering new ones at runtime.
    """
    params = {
        "user_id": hashtag_id,
        "fields": _DEFAULT_FIELDS,
        "limit": limit,
        "access_token": access_token,
    }
    data = await _get(f"{hashtag_id}/recent_media", params)
    items = data.get("data", [])
    if not isinstance(items, list):
        return []
    return items
