"""Structured logging configuration via structlog.

Every log line is a JSON object containing at minimum a ``request_id`` and a
``timestamp``. ``request_id`` is propagated through a ``ContextVar`` so any
code path inside a request — including code that doesn't have access to the
``Request`` object — automatically tags its logs.
"""

from __future__ import annotations

import logging
import sys
import uuid
from contextvars import ContextVar
from typing import Any

import structlog
from structlog.types import EventDict, Processor

# ---------------------------------------------------------------------------
# Context vars
# ---------------------------------------------------------------------------

# Set per-request by the request-logging middleware. ``None`` outside requests.
request_id_var: ContextVar[str | None] = ContextVar("request_id", default=None)
user_id_var: ContextVar[str | None] = ContextVar("user_id", default=None)


def new_request_id() -> str:
    """Generate a fresh request id (used when the client doesn't supply one)."""
    return uuid.uuid4().hex


def bind_request_id(request_id: str) -> None:
    request_id_var.set(request_id)


def bind_user_id(user_id: str | None) -> None:
    user_id_var.set(user_id)


def get_request_id() -> str | None:
    return request_id_var.get()


def _inject_context(
    _logger: Any, _name: str, event_dict: EventDict
) -> EventDict:
    """Attach context vars to every log record automatically."""
    rid = request_id_var.get()
    if rid is not None:
        event_dict.setdefault("request_id", rid)
    uid = user_id_var.get()
    if uid is not None:
        event_dict.setdefault("user_id", uid)
    return event_dict


def configure_logging(level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structlog + the stdlib logger to emit one JSON line per event.

    Idempotent — safe to call multiple times (tests do this).
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        _inject_context,
    ]

    renderer: Processor
    if json_logs:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(colors=True)

    structlog.configure(
        processors=[*shared_processors, renderer],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Route stdlib logging (uvicorn, sqlalchemy, etc.) through the same handler.
    handler = logging.StreamHandler(sys.stdout)
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    # Replace existing handlers — important when uvicorn's own handlers have
    # already been installed before we run.
    for h in list(root.handlers):
        root.removeHandler(h)
    root.addHandler(handler)
    root.setLevel(log_level)

    for noisy in ("uvicorn", "uvicorn.access", "uvicorn.error", "sqlalchemy.engine"):
        logging.getLogger(noisy).handlers = [handler]
        logging.getLogger(noisy).propagate = False


def get_logger(name: str | None = None) -> Any:
    """Return a structlog BoundLogger; convenience wrapper."""
    return structlog.get_logger(name) if name else structlog.get_logger()
