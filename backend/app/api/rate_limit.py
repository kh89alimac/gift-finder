"""SlowAPI rate-limiting setup.

We rate-limit auth endpoints (to slow brute force) and admin ingestion
triggers (to prevent operators from accidentally DoSing themselves with
overlapping scrape jobs).

The key function prefers the user id from the bearer token (so two users
behind the same NAT don't share a budget) and otherwise falls back to the
real client IP. ``ProxyHeadersMiddleware`` is responsible for ensuring
``request.client.host`` reflects ``X-Forwarded-For`` behind a load balancer.
"""

from __future__ import annotations

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address


def _key_func(request: Request) -> str:
    # Prefer user id from a valid access token if present.
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        try:
            from app.core.security import decode_token

            payload = decode_token(auth[7:])
            sub = payload.get("sub")
            if sub:
                return f"user:{sub}"
        except Exception:
            # Invalid / expired token — fall through to IP-based limiting
            # rather than rejecting at the rate-limit layer.
            pass

    # Already-resolved user attribute set by auth middleware (legacy path).
    user_id = getattr(request.state, "user_id", None)
    if user_id:
        return f"user:{user_id}"

    # Fallback to client IP. With ProxyHeadersMiddleware in place this honors
    # X-Forwarded-For from trusted upstream proxies.
    return f"ip:{get_remote_address(request)}"


limiter = Limiter(key_func=_key_func, default_limits=["1000/minute"])
