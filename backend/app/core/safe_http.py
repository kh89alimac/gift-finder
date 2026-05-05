"""SSRF-safe URL validation and HTTP client helpers.

Anything that takes a URL from external/untrusted input (scraper configs,
Instagram payloads, CSV imports, item display) must validate the URL before
either fetching it server-side or rendering it as an ``<a href>``. This module
centralizes that validation so we can audit it in one place.

Two layers:

* ``validate_safe_url`` — strict: scheme allowlist + DNS resolution + private
  IP rejection. Use before any server-side fetch.
* ``validate_display_url`` — lighter: scheme allowlist only. Use for URLs that
  will only ever be embedded in a response (no server-side fetch).
"""

from __future__ import annotations

import ipaddress
import socket
from typing import Any
from urllib.parse import urlparse

import httpx

ALLOWED_SCHEMES = {"http", "https"}

# RFC 1918 + loopback + link-local + IPv6 ULA/link-local. AWS IMDS gets its
# own check below.
PRIVATE_RANGES = [
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

# Cloud metadata endpoints we never want to be tricked into fetching.
BLOCKED_HOSTS = {"169.254.169.254", "fd00:ec2::254"}


def _is_private_ip(host: str) -> bool:
    """Return True if ``host`` resolves to any private/internal address.

    Resolves all A/AAAA records and rejects if *any* of them is private — a
    DNS that returns multiple records can otherwise trick us into TOCTOU
    bypasses. Fails closed on resolution errors.
    """
    try:
        results = socket.getaddrinfo(host, None)
        for *_, sockaddr in results:
            ip = ipaddress.ip_address(sockaddr[0])
            if ip.is_loopback or ip.is_link_local or ip.is_private or ip.is_reserved:
                return True
            for net in PRIVATE_RANGES:
                if ip in net:
                    return True
    except (socket.gaierror, ValueError):
        return True  # Fail closed
    return False


def validate_safe_url(url: str) -> str:
    """Validate URL is safe to fetch server-side. Returns ``url`` or raises.

    Raises ``ValueError`` if the scheme is wrong, the host is blocked, or the
    host resolves to a private/internal address.
    """
    parsed = urlparse(url)
    if parsed.scheme not in ALLOWED_SCHEMES:
        raise ValueError(
            f"URL scheme must be http or https, got: {parsed.scheme!r}"
        )
    if not parsed.hostname:
        raise ValueError("URL must have a valid hostname")
    if parsed.hostname in BLOCKED_HOSTS:
        raise ValueError(f"Blocked hostname: {parsed.hostname}")
    if _is_private_ip(parsed.hostname):
        raise ValueError("URL resolves to a private/internal IP address")
    return url


def validate_display_url(url: str | None) -> str | None:
    """Return ``url`` if safe to embed in a response, else ``None``.

    This is a lighter check than :func:`validate_safe_url` — we only validate
    the scheme. Use it for URLs the *frontend* will render (e.g. ``<a href>``)
    where we never make an outbound request ourselves.
    """
    if url is None:
        return None
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ALLOWED_SCHEMES:
            return None
        return url
    except Exception:
        return None


def safe_httpx_client(**kwargs: Any) -> httpx.AsyncClient:
    """Return an ``httpx.AsyncClient`` pre-configured for SSRF safety.

    Defaults to ``follow_redirects=False`` so callers must opt-in (and
    re-validate) any redirect they want to follow.
    """
    kwargs.setdefault("follow_redirects", False)
    kwargs.setdefault("timeout", 30.0)
    return httpx.AsyncClient(**kwargs)
