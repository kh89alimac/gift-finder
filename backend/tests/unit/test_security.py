"""Unit tests for app.core.security.

Tests cover:
- Password hashing & verification
- JWT creation and decoding
- Token family rotation (Redis-backed)
"""

from __future__ import annotations

import time
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import jwt
import pytest

from app.core.exceptions import InvalidTokenError
from app.core.security import (
    REFRESH_JTI_PREFIX,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_refresh_jti_valid,
    revoke_refresh_jti,
    rotate_refresh_token,
    store_refresh_jti,
    verify_password,
)


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def test_hash_password_produces_different_hashes_for_same_input():
    """bcrypt uses a random salt, so identical inputs yield different hashes."""
    h1 = hash_password("MySecret1")
    h2 = hash_password("MySecret1")
    assert h1 != h2


def test_hash_password_rejects_empty_string():
    with pytest.raises(ValueError, match="not be empty"):
        hash_password("")


def test_verify_password_succeeds_with_correct_password():
    plain = "CorrectHorse99"
    hashed = hash_password(plain)
    assert verify_password(plain, hashed) is True


def test_verify_password_fails_with_wrong_password():
    hashed = hash_password("RightPassword1")
    assert verify_password("WrongPassword1", hashed) is False


def test_verify_password_returns_false_for_empty_inputs():
    assert verify_password("", "somehash") is False
    assert verify_password("password", "") is False


def test_verify_password_handles_malformed_hash_gracefully():
    """A corrupted hash string must not raise — just return False."""
    assert verify_password("anypassword", "not-a-valid-hash") is False


# ---------------------------------------------------------------------------
# JWT creation + decoding
# ---------------------------------------------------------------------------


def test_create_access_token_encodes_user_id_and_role():
    uid = uuid.uuid4()
    role = "admin"
    token = create_access_token(uid, role)
    payload = decode_token(token)
    assert payload["sub"] == str(uid)
    assert payload["role"] == role
    assert payload["type"] == "access"


def test_access_token_has_correct_expiry_window():
    uid = uuid.uuid4()
    token = create_access_token(uid, "user")
    payload = decode_token(token)
    now = int(datetime.now(timezone.utc).timestamp())
    # Should expire in ~15 minutes (±5 seconds leeway for slow machines)
    assert 14 * 60 < (payload["exp"] - now) <= 15 * 60 + 5


def test_decode_token_raises_on_expired_token():
    """Forge a token whose exp is in the past."""
    from app.core.config import settings

    secret = settings.JWT_SECRET.get_secret_value()
    past = int((datetime.now(timezone.utc) - timedelta(seconds=1)).timestamp())
    payload = {
        "sub": str(uuid.uuid4()),
        "role": "user",
        "type": "access",
        "iat": past - 60,
        "exp": past,
        "jti": "test",
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(InvalidTokenError, match="expired"):
        decode_token(token)


def test_decode_token_raises_on_malformed_token():
    with pytest.raises(InvalidTokenError):
        decode_token("totally.not.a.jwt")


def test_decode_token_raises_on_empty_token():
    with pytest.raises(InvalidTokenError):
        decode_token("")


def test_decode_token_raises_when_required_claims_missing():
    from app.core.config import settings

    secret = settings.JWT_SECRET.get_secret_value()
    payload = {
        "exp": int((datetime.now(timezone.utc) + timedelta(minutes=15)).timestamp()),
    }
    token = jwt.encode(payload, secret, algorithm="HS256")
    with pytest.raises(InvalidTokenError, match="missing required claims"):
        decode_token(token)


def test_decode_token_raises_on_wrong_signature():
    uid = uuid.uuid4()
    token = create_access_token(uid, "user")
    tampered = token[:-4] + "XXXX"
    with pytest.raises(InvalidTokenError):
        decode_token(tampered)


# ---------------------------------------------------------------------------
# Refresh token + Redis family tracking
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_store_and_validate_refresh_jti(mock_redis):
    user_id = uuid.uuid4()
    _, jti = create_refresh_token(user_id)
    await store_refresh_jti(user_id, jti)
    assert await is_refresh_jti_valid(jti) is True


@pytest.mark.asyncio
async def test_revoke_refresh_jti_makes_it_invalid(mock_redis):
    user_id = uuid.uuid4()
    _, jti = create_refresh_token(user_id)
    await store_refresh_jti(user_id, jti)
    await revoke_refresh_jti(jti)
    assert await is_refresh_jti_valid(jti) is False


@pytest.mark.asyncio
async def test_rotate_refresh_token_returns_new_token(mock_redis):
    user_id = uuid.uuid4()
    _old_token, old_jti = create_refresh_token(user_id)
    await store_refresh_jti(user_id, old_jti)

    new_token, new_jti = await rotate_refresh_token(user_id, old_jti)
    assert new_token != _old_token
    assert new_jti != old_jti
    # Old JTI must be gone, new JTI must be present.
    assert await is_refresh_jti_valid(old_jti) is False
    assert await is_refresh_jti_valid(new_jti) is True


@pytest.mark.asyncio
async def test_token_family_rotation_replaying_revoked_jti_raises(mock_redis):
    """Replaying a previously-used JTI triggers theft detection and full revocation."""
    user_id = uuid.uuid4()
    _token, jti = create_refresh_token(user_id)
    await store_refresh_jti(user_id, jti)

    # Perform a legitimate rotation.
    _new_token, _new_jti = await rotate_refresh_token(user_id, jti)

    # Re-attempt with the old (now revoked) JTI — must raise.
    with pytest.raises(InvalidTokenError, match="revoked"):
        await rotate_refresh_token(user_id, jti)

    # The entire family must now be invalidated.
    assert await is_refresh_jti_valid(_new_jti) is False


@pytest.mark.asyncio
async def test_rotate_refresh_token_raises_for_unknown_jti(mock_redis):
    user_id = uuid.uuid4()
    with pytest.raises(InvalidTokenError):
        await rotate_refresh_token(user_id, "nonexistent-jti")
