"""FastAPI application factory.

This module is intentionally thin — every responsibility (routing, error
handling, middleware, dependencies) lives in its own module so the app
factory just wires them together.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from sqlalchemy.exc import NoResultFound
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.api.rate_limit import limiter
from app.api.v1.router import api_router
from app.core.config import settings
from app.core.database import dispose_engine
from app.core.exceptions import (
    ConflictError,
    ExternalServiceError,
    ForbiddenError,
    GiftFinderError,
    InvalidTokenError,
    NotFoundError,
    RateLimitError,
    UnauthorizedError,
    ValidationError,
)
from app.core.logging import configure_logging, get_logger, get_request_id
from app.core.redis import close_redis, ping_redis
from app.middleware import RequestLoggingMiddleware, SecurityHeadersMiddleware
from app.schemas.common import ErrorResponse, HealthResponse


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------


log = get_logger("startup")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Run startup/shutdown hooks.

    Startup: configure logging, ping Redis, log effective settings.
    Shutdown: dispose the SQLAlchemy engine and close Redis.
    """
    configure_logging(level=settings.LOG_LEVEL, json_logs=settings.is_production)
    log.info(
        "app.startup",
        env=settings.APP_ENV,
        debug=settings.DEBUG,
        cors_origins=settings.CORS_ORIGINS,
    )

    if not await ping_redis():
        log.warning("redis.ping.failed")

    try:
        yield
    finally:
        log.info("app.shutdown")
        await dispose_engine()
        await close_redis()


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_app() -> FastAPI:
    app = FastAPI(
        title="Gift Finder API",
        description="Personalized gift discovery and recommendation backend.",
        version="0.1.0",
        lifespan=lifespan,
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        docs_url=f"{settings.API_V1_PREFIX}/docs",
        redoc_url=f"{settings.API_V1_PREFIX}/redoc",
    )

    # ----- Middleware (innermost first because Starlette wraps in reverse)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    # Always attach baseline hardening headers — sits after CORS so browsers
    # see them even on preflight responses.
    app.add_middleware(SecurityHeadersMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
    app.add_middleware(SlowAPIMiddleware)
    # Trust X-Forwarded-* from upstream proxies (LB / reverse proxy). In
    # production, restrict ``trusted_hosts`` to the LB's actual IP/range.
    app.add_middleware(ProxyHeadersMiddleware, trusted_hosts="*")

    # ----- Rate limiter
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ----- Domain exception handlers
    _install_exception_handlers(app)

    # ----- Health check (outside the versioned namespace)
    @app.get("/health", response_model=HealthResponse, tags=["health"])
    async def health() -> HealthResponse:
        return HealthResponse(
            status="ok",
            version=app.version,
            environment=settings.APP_ENV,
        )

    # ----- Routes
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    return app


# ---------------------------------------------------------------------------
# Exception handling
# ---------------------------------------------------------------------------


def _install_exception_handlers(app: FastAPI) -> None:
    """Translate domain errors -> structured JSON. One handler per family."""

    handlers_log = get_logger("errors")

    def _envelope(exc: GiftFinderError) -> JSONResponse:
        body = ErrorResponse(
            code=exc.code,
            message=exc.message,
            details=exc.details,
            request_id=get_request_id(),
        )
        return JSONResponse(status_code=exc.status_code, content=body.model_dump())

    @app.exception_handler(NotFoundError)
    async def _not_found(_req: Request, exc: NotFoundError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(ConflictError)
    async def _conflict(_req: Request, exc: ConflictError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(ForbiddenError)
    async def _forbidden(_req: Request, exc: ForbiddenError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(UnauthorizedError)
    async def _unauthorized(_req: Request, exc: UnauthorizedError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(InvalidTokenError)
    async def _invalid_token(_req: Request, exc: InvalidTokenError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(ValidationError)
    async def _validation(_req: Request, exc: ValidationError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(RateLimitError)
    async def _rate_limit(_req: Request, exc: RateLimitError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(ExternalServiceError)
    async def _external(_req: Request, exc: ExternalServiceError) -> JSONResponse:
        handlers_log.warning("external.error", code=exc.code, details=exc.details)
        return _envelope(exc)

    @app.exception_handler(GiftFinderError)
    async def _generic_domain(_req: Request, exc: GiftFinderError) -> JSONResponse:
        return _envelope(exc)

    @app.exception_handler(NoResultFound)
    async def _no_result(_req: Request, exc: NoResultFound) -> JSONResponse:
        domain = NotFoundError(str(exc) or "Resource not found")
        return _envelope(domain)

    @app.exception_handler(RequestValidationError)
    async def _request_validation(
        _req: Request, exc: RequestValidationError
    ) -> JSONResponse:
        # Pydantic v2 field_validator errors include ctx={"error": ExcInstance}
        # which is not JSON-serializable. Sanitize by converting exception
        # objects in ctx to their string representation.
        def _sanitize(errors: list) -> list:
            out = []
            for e in errors:
                e = dict(e)
                if "ctx" in e:
                    e["ctx"] = {
                        k: str(v) if isinstance(v, Exception) else v
                        for k, v in e["ctx"].items()
                    }
                out.append(e)
            return out

        domain = ValidationError(
            "Request payload failed validation",
            details={"errors": _sanitize(exc.errors())},
        )
        return _envelope(domain)

    @app.exception_handler(Exception)
    async def _unhandled(_req: Request, exc: Exception) -> JSONResponse:
        handlers_log.exception("unhandled.exception", error=str(exc))
        domain = GiftFinderError(
            "Internal server error",
            details={"type": type(exc).__name__},
        )
        return _envelope(domain)


# ---------------------------------------------------------------------------
# Module-level app for ``uvicorn app.main:app``
# ---------------------------------------------------------------------------

app = create_app()
