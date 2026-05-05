"""Shared schema primitives: pagination, error envelopes, bulk-action results.

The pagination helpers support both offset-based (admin tables) and cursor
based (discovery feed) styles. Cursors are opaque base64 to clients; we
intentionally don't expose the keyset shape so we can change it later.
"""

from __future__ import annotations

import base64
import json
import uuid
from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------


class ErrorResponse(BaseModel):
    """Wire format for every non-2xx response.

    Mirrors :class:`app.core.exceptions.GiftFinderError.to_dict` so handlers
    can pass ``exc.to_dict()`` straight in.
    """

    model_config = ConfigDict(extra="forbid")

    code: str = Field(description="Machine-friendly error code")
    message: str = Field(description="Human-readable message")
    details: dict[str, Any] = Field(default_factory=dict)
    request_id: str | None = Field(
        default=None,
        description="Server-generated id for correlating logs with the response",
    )


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------


class PageMeta(BaseModel):
    """Metadata for offset-style pagination."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(ge=1)
    page_size: int = Field(ge=1, le=100)
    total: int = Field(ge=0)
    total_pages: int = Field(ge=0)


class PaginatedResponse(BaseModel, Generic[T]):
    """Generic paginated envelope. Use as ``PaginatedResponse[ItemSummary]``."""

    items: list[T]
    meta: PageMeta


class CursorPage(BaseModel, Generic[T]):
    """Cursor-paginated envelope used for the discovery feed."""

    items: list[T]
    next_cursor: str | None = Field(
        default=None,
        description="Opaque cursor for the next page; null when at end",
    )


def encode_cursor(payload: dict[str, Any]) -> str:
    """Pack ``payload`` into an opaque base64 string.

    UUIDs and datetimes are serialized to ISO/hex so they round-trip cleanly.
    """

    def _default(o: Any) -> Any:
        if isinstance(o, uuid.UUID):
            return o.hex
        if isinstance(o, datetime):
            return o.isoformat()
        raise TypeError(f"Unserializable type: {type(o).__name__}")

    raw = json.dumps(payload, default=_default, separators=(",", ":")).encode()
    return base64.urlsafe_b64encode(raw).decode().rstrip("=")


def decode_cursor(cursor: str) -> dict[str, Any]:
    """Reverse of :func:`encode_cursor`. Raises ``ValueError`` on garbage."""
    pad = "=" * (-len(cursor) % 4)
    try:
        raw = base64.urlsafe_b64decode(cursor + pad)
        data = json.loads(raw.decode())
    except (ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"Malformed cursor: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError("Cursor payload is not an object")
    return data


# ---------------------------------------------------------------------------
# Bulk actions
# ---------------------------------------------------------------------------


class BulkActionFailure(BaseModel):
    id: str
    reason: str


class BulkActionResult(BaseModel):
    """Returned by endpoints that operate on a list of ids.

    ``successes`` is the count of items the operation succeeded for. We don't
    fail the whole request when only one row fails — partial success is
    the right tradeoff for admin tooling.
    """

    successes: int = Field(ge=0)
    failures: list[BulkActionFailure] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Health
# ---------------------------------------------------------------------------


class HealthResponse(BaseModel):
    status: str
    version: str
    environment: str
