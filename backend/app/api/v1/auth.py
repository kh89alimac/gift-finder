"""Authentication endpoints.

The refresh token is stored in an httpOnly cookie scoped to ``/api/v1/auth``
so it can never be read by JavaScript (mitigating XSS-driven token theft).
The access token continues to be returned in the JSON body so callers can
attach it to subsequent ``Authorization`` headers from in-memory state.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.api.rate_limit import limiter
from app.core.config import settings
from app.dependencies import CurrentUser, UowDep
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)
from app.services.auth_service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


REFRESH_COOKIE_NAME = "refresh_token"
REFRESH_COOKIE_PATH = "/api/v1/auth"
# 7 days — matches REFRESH_TOKEN_EXPIRE_DAYS in core.security.
REFRESH_COOKIE_MAX_AGE = 60 * 60 * 24 * 7


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=refresh_token,
        httponly=True,
        secure=settings.is_production,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
        max_age=REFRESH_COOKIE_MAX_AGE,
    )


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    request: Request,
    response: Response,
    payload: RegisterRequest,
    uow: UowDep,
) -> TokenResponse:
    """Create an account and return the access token.

    The refresh token is sent as an httpOnly cookie.
    """
    service = AuthService(uow)
    _user, tokens, refresh_token = await service.register(payload)
    _set_refresh_cookie(response, refresh_token)
    return tokens


@router.post("/login", response_model=TokenResponse)
@limiter.limit("10/minute")
async def login(
    request: Request,
    response: Response,
    payload: LoginRequest,
    uow: UowDep,
) -> TokenResponse:
    """Exchange email/password for an access token + refresh-cookie pair."""
    service = AuthService(uow)
    _user, tokens, refresh_token = await service.login(payload)
    _set_refresh_cookie(response, refresh_token)
    return tokens


@router.post("/refresh", response_model=TokenResponse)
@limiter.limit("30/minute")
async def refresh(
    request: Request,
    response: Response,
    uow: UowDep,
) -> TokenResponse:
    """Rotate the refresh cookie and mint a new access token."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing refresh token",
        )
    service = AuthService(uow)
    tokens, new_refresh = await service.refresh(refresh_token)
    _set_refresh_cookie(response, new_refresh)
    return tokens


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    request: Request,
    response: Response,
    uow: UowDep,
) -> None:
    """Revoke the refresh-cookie token (if any) and clear the cookie."""
    refresh_token = request.cookies.get(REFRESH_COOKIE_NAME)
    if refresh_token:
        service = AuthService(uow)
        await service.logout(refresh_token)
    response.delete_cookie(REFRESH_COOKIE_NAME, path=REFRESH_COOKIE_PATH)


@router.get("/me", response_model=UserOut)
async def me(current_user: CurrentUser) -> UserOut:
    """Return the current authenticated user."""
    return UserOut.model_validate(current_user)
