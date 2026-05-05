"""Auth-related request/response schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

from app.models.enums import UserRole


class RegisterRequest(BaseModel):
    """New user signup."""

    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr = Field(min_length=8, max_length=128)
    display_name: str | None = Field(default=None, max_length=100)

    @field_validator("password")
    @classmethod
    def _strong_enough(cls, v: SecretStr) -> SecretStr:
        # Cheap-but-useful check; fancy entropy estimation is overkill here.
        plain = v.get_secret_value()
        if plain.lower() == plain or plain.isalpha() or plain.isdigit():
            raise ValueError(
                "Password must contain a mix of upper/lowercase letters and digits"
            )
        return v


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: EmailStr
    password: SecretStr


class RefreshRequest(BaseModel):
    """Legacy body shape — retained so internal helpers / tests can still use
    it, but the public refresh endpoint now reads the refresh token from an
    httpOnly cookie. New code should not depend on this schema."""

    model_config = ConfigDict(extra="forbid")

    refresh_token: str = Field(min_length=10)


class TokenResponse(BaseModel):
    """Returned by login + refresh.

    The refresh token is set as an httpOnly cookie by the API, never in the
    JSON body. ``access_token`` is the only credential the client should hold
    in memory.
    """

    access_token: str
    token_type: str = "bearer"
    expires_in: int = Field(description="Access token lifetime in seconds")


class UserOut(BaseModel):
    """Public user representation (never includes password hash)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    role: UserRole
    display_name: str | None
    avatar_url: str | None
    default_currency: str
    onboarding_done: bool
    email_verified: bool
    last_login_at: datetime | None
    created_at: datetime
