"""Integration tests for /api/v1/auth endpoints."""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

from app.core.security import create_refresh_token, store_refresh_jti

BASE = "/api/v1/auth"
REFRESH_COOKIE = "refresh_token"


# ---------------------------------------------------------------------------
# POST /register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_creates_user_returns_tokens(test_client, mock_redis):
    resp = await test_client.post(
        f"{BASE}/register",
        json={
            "email": f"newuser-{uuid.uuid4().hex[:6]}@example.com",
            "password": "Secure1Pass",
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "access_token" in body
    # Refresh token is sent as an httpOnly cookie, not in the body.
    assert REFRESH_COOKIE in resp.cookies
    assert body["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_register_with_duplicate_email_returns_409(
    test_client, user_factory, mock_redis
):
    email = f"dup-{uuid.uuid4().hex[:6]}@example.com"
    await user_factory(email=email)

    resp = await test_client.post(
        f"{BASE}/register",
        json={"email": email, "password": "Secure1Pass"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_register_with_weak_password_returns_422(test_client):
    resp = await test_client.post(
        f"{BASE}/register",
        json={"email": "test@example.com", "password": "alllower"},
    )
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# POST /login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_with_valid_credentials_returns_tokens(
    test_client, user_factory, mock_redis
):
    email = f"login-{uuid.uuid4().hex[:6]}@example.com"
    password = "Valid1Pass"
    await user_factory(email=email, password=password)

    resp = await test_client.post(
        f"{BASE}/login",
        json={"email": email, "password": password},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    # Refresh token is in cookie, not body.
    assert REFRESH_COOKIE in resp.cookies


@pytest.mark.asyncio
async def test_login_with_wrong_password_returns_401(
    test_client, user_factory
):
    email = f"wrongpw-{uuid.uuid4().hex[:6]}@example.com"
    await user_factory(email=email, password="Correct1Pass")

    resp = await test_client.post(
        f"{BASE}/login",
        json={"email": email, "password": "WrongPass1"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_login_with_nonexistent_user_returns_401(test_client):
    resp = await test_client.post(
        f"{BASE}/login",
        json={"email": "nobody@example.com", "password": "SomePass1"},
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# POST /refresh
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_refresh_with_valid_refresh_token_returns_new_token_pair(
    test_client, user_factory, mock_redis
):
    user = await user_factory()
    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_jti(user.id, jti)

    resp = await test_client.post(
        f"{BASE}/refresh",
        cookies={REFRESH_COOKIE: refresh_token},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "access_token" in body
    # New refresh token issued via cookie.
    assert REFRESH_COOKIE in resp.cookies
    assert resp.cookies[REFRESH_COOKIE] != refresh_token


@pytest.mark.asyncio
async def test_refresh_with_expired_token_returns_401(test_client):
    resp = await test_client.post(
        f"{BASE}/refresh",
        cookies={REFRESH_COOKIE: "eyJhbGciOiJIUzI1NiJ9.FAKE.FAKE"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_with_revoked_token_returns_401(
    test_client, user_factory, mock_redis
):
    """After rotation the old JTI is revoked; replaying it must return 401."""
    user = await user_factory()
    refresh_token, jti = create_refresh_token(user.id)
    await store_refresh_jti(user.id, jti)

    # Rotate once.
    await test_client.post(
        f"{BASE}/refresh", cookies={REFRESH_COOKIE: refresh_token}
    )

    # Replay the old token.
    resp = await test_client.post(
        f"{BASE}/refresh", cookies={REFRESH_COOKIE: refresh_token}
    )
    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# GET /me
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_me_with_valid_bearer_token_returns_user(
    test_client, user_factory, auth_headers
):
    user = await user_factory(email=f"me-{uuid.uuid4().hex[:6]}@example.com")
    resp = await test_client.get(f"{BASE}/me", headers=auth_headers(user))
    assert resp.status_code == 200
    body = resp.json()
    assert body["email"] == user.email
    assert body["id"] == str(user.id)


@pytest.mark.asyncio
async def test_get_me_without_token_returns_401(test_client):
    resp = await test_client.get(f"{BASE}/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_get_me_with_invalid_token_returns_401(test_client):
    resp = await test_client.get(
        f"{BASE}/me", headers={"Authorization": "Bearer invalidtoken"}
    )
    assert resp.status_code == 401
