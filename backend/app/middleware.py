"""HTTP middleware: per-request structlog logger + request id propagation +
security response headers."""

from __future__ import annotations

import time
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import bind_request_id, get_logger, new_request_id

log = get_logger("http")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Inject a request id, log start + finish, attach duration_ms."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Allow callers (gateways, tests) to supply their own correlation id.
        rid = request.headers.get("x-request-id") or new_request_id()
        bind_request_id(rid)
        request.state.request_id = rid

        start = time.perf_counter()
        log.info(
            "request.start",
            method=request.method,
            path=request.url.path,
            client=request.client.host if request.client else None,
        )
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            log.error(
                "request.error",
                method=request.method,
                path=request.url.path,
                duration_ms=round(duration_ms, 2),
                error=str(exc),
            )
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        log.info(
            "request.finish",
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=round(duration_ms, 2),
        )
        response.headers["x-request-id"] = rid
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach a baseline set of security response headers to every reply.

    Most of these are "set once and forget" hardening moves that browsers
    already understand:

    * **X-Content-Type-Options** stops MIME-sniffing attacks.
    * **X-Frame-Options / frame-ancestors** prevents clickjacking.
    * **Strict-Transport-Security** forces HTTPS for two years on
      subsequent visits (assuming the response is served over TLS).
    * **Content-Security-Policy** blocks inline scripts and untrusted
      origins; tighten ``connect-src`` if you call third-party APIs from
      the browser.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = (
            "camera=(), microphone=(), geolocation=()"
        )
        response.headers["Strict-Transport-Security"] = (
            "max-age=63072000; includeSubDomains; preload"
        )
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' https: data:; "
            "connect-src 'self'; "
            "frame-ancestors 'none'; "
            "base-uri 'self'; "
            "form-action 'self'"
        )
        return response
