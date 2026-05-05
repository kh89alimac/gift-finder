"""Authentication service: registration, login, token rotation, profile."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select

from app.core.exceptions import (
    ConflictError,
    InvalidTokenError,
    NotFoundError,
    UnauthorizedError,
)
from app.core.security import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    revoke_refresh_jti,
    rotate_refresh_token,
    store_refresh_jti,
    verify_password,
)
from app.models.enums import UserRole
from app.models.user import User
from app.repositories.unit_of_work import UnitOfWork
from app.schemas.auth import LoginRequest, RegisterRequest, TokenResponse


class AuthService:
    def __init__(self, uow: UnitOfWork) -> None:
        self.uow = uow

    # ------------------------------------------------------------- register
    async def register(
        self, data: RegisterRequest
    ) -> tuple[User, TokenResponse, str]:
        """Create the account and return ``(user, tokens, refresh_token)``.

        The raw refresh token is returned separately so the API layer can set
        it as an httpOnly cookie — it is never embedded in ``tokens``.
        """
        existing = await self.uow.session.execute(
            select(User).where(User.email == data.email.lower())
        )
        if existing.scalar_one_or_none() is not None:
            raise ConflictError("An account with that email already exists")

        user = User(
            email=data.email.lower(),
            password_hash=hash_password(data.password.get_secret_value()),
            display_name=data.display_name,
            role=UserRole.USER,
        )
        self.uow.session.add(user)
        await self.uow.session.flush()

        tokens, refresh_token = await self._issue_tokens(user)
        return user, tokens, refresh_token

    # --------------------------------------------------------------- login
    async def login(
        self, data: LoginRequest
    ) -> tuple[User, TokenResponse, str]:
        """Same shape as :meth:`register`."""
        result = await self.uow.session.execute(
            select(User).where(User.email == data.email.lower())
        )
        user = result.scalar_one_or_none()
        if user is None or user.password_hash is None:
            # Don't differentiate "no such user" vs "wrong password".
            raise UnauthorizedError("Invalid email or password")
        if not verify_password(data.password.get_secret_value(), user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        user.last_login_at = datetime.now(timezone.utc)
        await self.uow.session.flush()

        tokens, refresh_token = await self._issue_tokens(user)
        return user, tokens, refresh_token

    # -------------------------------------------------------------- refresh
    async def refresh(self, refresh_token: str) -> tuple[TokenResponse, str]:
        """Rotate ``refresh_token`` and return ``(tokens, new_refresh_token)``."""
        payload = decode_token(refresh_token)
        if payload.get("type") != "refresh":
            raise InvalidTokenError("Wrong token type for refresh")
        try:
            user_id = uuid.UUID(payload["sub"])
            jti = payload["jti"]
        except (KeyError, ValueError) as exc:
            raise InvalidTokenError("Refresh token missing required claims") from exc

        user = await self.uow.session.get(User, user_id)
        if user is None:
            raise InvalidTokenError("User no longer exists")

        new_refresh, _new_jti = await rotate_refresh_token(user_id, jti)
        access = create_access_token(user_id, user.role.value)
        tokens = TokenResponse(
            access_token=access,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return tokens, new_refresh

    # --------------------------------------------------------------- logout
    async def logout(self, refresh_token: str) -> None:
        try:
            payload = decode_token(refresh_token)
            jti = payload.get("jti")
            if jti:
                await revoke_refresh_jti(jti)
        except InvalidTokenError:
            # Logout on a bad token is still a successful logout.
            return

    # ------------------------------------------------------------------ me
    async def get_user(self, user_id: uuid.UUID) -> User:
        user = await self.uow.session.get(User, user_id)
        if user is None:
            raise NotFoundError(f"User {user_id} not found")
        return user

    # --------------------------------------------------------------- helper
    async def _issue_tokens(self, user: User) -> tuple[TokenResponse, str]:
        """Mint access + refresh and return ``(tokens, raw_refresh)``."""
        access = create_access_token(user.id, user.role.value)
        refresh, jti = create_refresh_token(user.id)
        await store_refresh_jti(user.id, jti)
        tokens = TokenResponse(
            access_token=access,
            expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )
        return tokens, refresh
