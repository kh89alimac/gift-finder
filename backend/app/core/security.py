"""Password hashing + JWT issuance / verification.

JWTs are short-lived (15 min) for access and longer-lived (7 days) for
refresh. Refresh tokens carry a ``jti`` (token id) that we track in Redis so
we can revoke a single refresh token (logout) or all of a user's refresh
tokens (security event) without scanning the DB.

Token family rotation: each successful refresh issues a new refresh JTI and
deletes the old one in the same transaction; if a stale JTI is replayed we
treat it as theft and revoke the entire family.
"""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Final

import bcrypt as _bcrypt
import jwt

from app.core.config import settings
from app.core.exceptions import InvalidTokenError
from app.core.redis import get_redis

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

ACCESS_TOKEN_EXPIRE_MINUTES: Final[int] = 15
REFRESH_TOKEN_EXPIRE_DAYS: Final[int] = 7
REFRESH_JTI_PREFIX: Final[str] = "refresh_jti:"
REFRESH_FAMILY_PREFIX: Final[str] = "refresh_family:"


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Hash ``plain`` with bcrypt + a random salt."""
    if not plain:
        raise ValueError("Password must not be empty")
    return _bcrypt.hashpw(plain.encode(), _bcrypt.gensalt(rounds=12)).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verification."""
    if not plain or not hashed:
        return False
    try:
        return _bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    secret = settings.JWT_SECRET.get_secret_value()
    return jwt.encode(payload, secret, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID, role: str) -> str:
    """Mint a short-lived access token. Stateless — never stored server-side."""
    now = _now()
    payload = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
        "jti": secrets.token_hex(8),
    }
    return _encode(payload)


def create_refresh_token(user_id: uuid.UUID, jti: str | None = None) -> tuple[str, str]:
    """Mint a refresh token and return ``(token, jti)``.

    Caller is responsible for storing the JTI via :func:`store_refresh_jti`
    before returning the token to the client.
    """
    now = _now()
    jti = jti or secrets.token_urlsafe(24)
    payload = {
        "sub": str(user_id),
        "type": "refresh",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS)).timestamp()),
        "jti": jti,
    }
    return _encode(payload), jti


def decode_token(token: str) -> dict[str, Any]:
    """Decode + validate signature/expiry. Raises :class:`InvalidTokenError`."""
    if not token:
        raise InvalidTokenError("Token is empty")
    secret = settings.JWT_SECRET.get_secret_value()
    try:
        payload = jwt.decode(token, secret, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise InvalidTokenError("Token has expired") from exc
    except jwt.PyJWTError as exc:
        raise InvalidTokenError(f"Token is invalid: {exc}") from exc

    if "sub" not in payload or "type" not in payload:
        raise InvalidTokenError("Token is missing required claims")
    return payload


# ---------------------------------------------------------------------------
# Refresh-token family tracking (Redis)
# ---------------------------------------------------------------------------


async def store_refresh_jti(user_id: uuid.UUID, jti: str) -> None:
    """Record a fresh refresh JTI. TTL matches token expiry so it self-cleans."""
    redis = get_redis()
    ttl_seconds = REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60
    # Per-token marker so we can check "is this jti still valid?".
    await redis.setex(f"{REFRESH_JTI_PREFIX}{jti}", ttl_seconds, str(user_id))
    # Per-user set so we can revoke an entire family on theft detection.
    await redis.sadd(f"{REFRESH_FAMILY_PREFIX}{user_id}", jti)
    await redis.expire(f"{REFRESH_FAMILY_PREFIX}{user_id}", ttl_seconds)


async def is_refresh_jti_valid(jti: str) -> bool:
    redis = get_redis()
    return bool(await redis.exists(f"{REFRESH_JTI_PREFIX}{jti}"))


async def revoke_refresh_jti(jti: str) -> None:
    redis = get_redis()
    await redis.delete(f"{REFRESH_JTI_PREFIX}{jti}")


async def revoke_user_family(user_id: uuid.UUID) -> None:
    """Wipe every active refresh token for ``user_id``. Used on theft."""
    redis = get_redis()
    family_key = f"{REFRESH_FAMILY_PREFIX}{user_id}"
    jtis = await redis.smembers(family_key)
    if jtis:
        await redis.delete(*[f"{REFRESH_JTI_PREFIX}{j}" for j in jtis])
    await redis.delete(family_key)


async def rotate_refresh_token(
    user_id: uuid.UUID, old_jti: str
) -> tuple[str, str]:
    """Atomically retire ``old_jti`` and mint a new refresh token.

    If ``old_jti`` has already been revoked we treat this as a replay attack
    and revoke the entire family before raising.
    """
    if not await is_refresh_jti_valid(old_jti):
        # Replay or theft — burn the family.
        await revoke_user_family(user_id)
        raise InvalidTokenError("Refresh token has been revoked")
    await revoke_refresh_jti(old_jti)
    token, jti = create_refresh_token(user_id)
    await store_refresh_jti(user_id, jti)
    return token, jti
