"""Domain exception hierarchy.

The API layer translates these into structured JSON error responses.
Service code should *only* raise these (or built-in exceptions for truly
unexpected conditions) so the API never has to know about repository or
SQLAlchemy errors.
"""

from __future__ import annotations

from typing import Any


class GiftFinderError(Exception):
    """Base class for all domain-specific errors.

    Carries an optional ``code`` (machine-friendly identifier) and ``details``
    (extra structured info) so handlers can render rich error responses
    without losing context.
    """

    status_code: int = 500
    code: str = "internal_error"

    def __init__(
        self,
        message: str = "",
        *,
        code: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message or self.__class__.__name__)
        self.message = message or self.__class__.__name__
        if code is not None:
            self.code = code
        self.details = details or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "code": self.code,
            "message": self.message,
            "details": self.details,
        }


class NotFoundError(GiftFinderError):
    """Aggregate or row missing."""

    status_code = 404
    code = "not_found"


class ConflictError(GiftFinderError):
    """Constraint violated, duplicate key, optimistic-lock failure, etc."""

    status_code = 409
    code = "conflict"


class ForbiddenError(GiftFinderError):
    """Authenticated but not authorized for the requested action."""

    status_code = 403
    code = "forbidden"


class UnauthorizedError(GiftFinderError):
    """Missing or invalid credentials."""

    status_code = 401
    code = "unauthorized"


class InvalidTokenError(UnauthorizedError):
    """JWT failed to decode, expired, or has been revoked."""

    code = "invalid_token"


class ValidationError(GiftFinderError):
    """Request payload failed business-rule validation (after Pydantic)."""

    status_code = 422
    code = "validation_error"


class RateLimitError(GiftFinderError):
    """Caller exceeded a rate-limit window."""

    status_code = 429
    code = "rate_limited"


class ExternalServiceError(GiftFinderError):
    """A third-party (OpenAI, Instagram, S3, retailer site) call failed."""

    status_code = 502
    code = "external_service_error"
