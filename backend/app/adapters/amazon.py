"""Amazon adapter — STUB.

Amazon aggressively blocks scraping (CAPTCHA, JS-rendered content) so a
production implementation needs a headless browser pool with residential
proxies, plus careful adherence to their TOS. We log a warning and yield
nothing; deployment teams should replace this with the real implementation
plus proper auth/proxy infrastructure.
"""

from __future__ import annotations

from collections.abc import AsyncIterator

from app.adapters.base import BaseScrapeAdapter, ScrapeResult
from app.adapters.registry import register_adapter
from app.core.logging import get_logger

log = get_logger(__name__)


@register_adapter
class AmazonAdapter(BaseScrapeAdapter):
    name = "amazon"

    async def scrape(self) -> AsyncIterator[ScrapeResult]:
        log.warning(
            "amazon.adapter.stub_invoked",
            note=(
                "AmazonAdapter is a stub. Implement with a headless browser "
                "pool and proper anti-bot mitigation before enabling in prod."
            ),
        )
        if False:  # pragma: no cover - empty generator pattern
            yield  # type: ignore[unreachable]

    async def health_check(self) -> bool:
        # Always healthy in stub mode so we don't trip alerts.
        return True
