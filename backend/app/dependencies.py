"""FastAPI dependencies.

Kept separate from ``main.py`` so any module can import them without pulling
in the full app object.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db as get_db_session
from app.core.exceptions import ForbiddenError, InvalidTokenError, UnauthorizedError
from app.core.logging import bind_user_id
from app.core.security import decode_token
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.unit_of_work import UnitOfWork

# OAuth2 password bearer so Swagger UI shows an Authorize button.
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl=f"{settings.API_V1_PREFIX}/auth/login",
    auto_error=False,
)


# ---------------------------------------------------------------------------
# Database / UoW
# ---------------------------------------------------------------------------


async def get_db() -> AsyncIterator[AsyncSession]:
    """Re-export the session dependency from ``core.database``."""
    async for session in get_db_session():
        yield session


async def get_uow() -> AsyncIterator[UnitOfWork]:
    """Yield a UnitOfWork that auto-commits on clean exit."""
    async with UnitOfWork() as uow:
        yield uow


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


async def get_current_user(
    token: Annotated[str | None, Depends(oauth2_scheme)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    """Resolve the authenticated user from the bearer token.

    Raises :class:`UnauthorizedError` when no token is sent and
    :class:`InvalidTokenError` when the token is bogus or expired.
    """
    if not token:
        raise UnauthorizedError("Missing bearer token")
    payload = decode_token(token)
    if payload.get("type") != "access":
        raise InvalidTokenError("Wrong token type")

    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError) as exc:
        raise InvalidTokenError("Token subject is not a valid UUID") from exc

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise InvalidTokenError("User no longer exists")

    bind_user_id(str(user.id))
    return user


async def get_current_user_optional(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User | None:
    """Return the user if a valid token is present, else None.

    Useful for endpoints whose response varies for logged-in users without
    requiring auth (e.g. discovery feed personalization).
    """
    auth = request.headers.get("Authorization")
    if not auth or not auth.lower().startswith("bearer "):
        return None
    token = auth.split(" ", 1)[1].strip()
    if not token:
        return None
    try:
        payload = decode_token(token)
    except InvalidTokenError:
        return None
    if payload.get("type") != "access":
        return None
    try:
        user_id = uuid.UUID(payload["sub"])
    except (KeyError, ValueError):
        return None
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is not None:
        bind_user_id(str(user.id))
    return user


async def require_admin(
    current_user: Annotated[User, Depends(get_current_user)],
) -> User:
    """Authorize: 403 unless the caller has the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise ForbiddenError("Admin role required")
    return current_user


# ---------------------------------------------------------------------------
# Type aliases for clean route signatures
# ---------------------------------------------------------------------------

DbSession = Annotated[AsyncSession, Depends(get_db)]
UowDep = Annotated[UnitOfWork, Depends(get_uow)]
CurrentUser = Annotated[User, Depends(get_current_user)]
OptionalUser = Annotated[User | None, Depends(get_current_user_optional)]
AdminUser = Annotated[User, Depends(require_admin)]
