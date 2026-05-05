"""Etsy adapter using the public search HTML.

Etsy has a paid affiliate API that you should prefer for production; this
adapter exists for development and as a fallback. It scrapes the gift-search
results page using stable CSS selectors known at the time of writing.

If Etsy changes their markup (which they do periodically), update the
selector constants below. We deliberately keep the parsing tolerant — any
field that fails to extract is skipped rather than failing the whole row.
"""

from __future__ import annotations

import asyncio
import hashlib
import urllib.parse
from collections.abc import AsyncIterator
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

from app.adapters.base import BaseScrapeAdapter, ScrapeResult
from app.adapters.registry import register_adapter
from app.core.logging import get_logger

log = get_logger(__name__)

LISTING_SELECTOR = "li.wt-list-unstyled a.listing-link"
TITLE_SELECTOR = "h1[data-buy-box-listing-title]"
PRICE_SELECTOR = "p.wt-text-title-larger"
DESC_SELECTOR = "div[data-id='description-text']"
IMAGE_SELECTOR = "img[data-listing-image]"


@register_adapter
class EtsyAdapter(BaseScrapeAdapter):
    name = "etsy"

    @staticmethod
    def _to_decimal(text: str | None) -> Decimal | None:
        if not text:
            return None
        cleaned = "".join(ch for ch in text if ch.isdigit() or ch == ".")
        try:
            return Decimal(cleaned) if cleaned else None
        except InvalidOperation:
            return None

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        try:
            resp = await client.get(
                url,
                headers={
                    "User-Agent": self.user_agent,
                    "Accept-Language": "en-US,en;q=0.9",
                },
            )
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            log.warning("etsy.fetch.failed", url=url, error=str(exc))
            return None

    async def _parse_listing(
        self, client: httpx.AsyncClient, url: str
    ) -> ScrapeResult | None:
        html = await self._fetch(client, url)
        if html is None:
            return None
        soup = BeautifulSoup(html, "html.parser")

        title_node = soup.select_one(TITLE_SELECTOR)
        if not title_node:
            return None
        title = title_node.get_text(strip=True)

        price = self._to_decimal(
            (soup.select_one(PRICE_SELECTOR) or soup.new_tag("p")).get_text(strip=True)
        )
        desc_node = soup.select_one(DESC_SELECTOR)
        description = desc_node.get_text(separator="\n", strip=True) if desc_node else None

        img_node = soup.select_one(IMAGE_SELECTOR)
        image_url = None
        if img_node:
            src = img_node.get("src")
            if isinstance(src, str):
                image_url = src

        # Etsy listing ids are embedded in the URL: /listing/{id}/...
        parts = urllib.parse.urlsplit(url).path.split("/")
        external_id = next(
            (parts[i + 1] for i, p in enumerate(parts) if p == "listing" and i + 1 < len(parts)),
            hashlib.sha256(url.encode()).hexdigest()[:32],
        )

        return ScrapeResult(
            source_external_id=external_id,
            title=title,
            product_url=url,
            description=description,
            price=price,
            currency=self.config.get("currency", "USD"),
            image_url=image_url,
            retailer="Etsy",
            source_url=url,
        )

    async def scrape(self) -> AsyncIterator[ScrapeResult]:
        query = self.config.get("query", "gift")
        pages = int(self.config.get("list_pages", 1))
        rate_seconds = float(self.config.get("rate_limit_seconds", 1.5))

        async with httpx.AsyncClient(timeout=30.0, follow_redirects=True) as client:
            seen: set[str] = set()
            for page in range(1, pages + 1):
                search_url = (
                    f"https://www.etsy.com/search?q={urllib.parse.quote(query)}&page={page}"
                )
                html = await self._fetch(client, search_url)
                if html is None:
                    continue
                soup = BeautifulSoup(html, "html.parser")
                links = soup.select(LISTING_SELECTOR)
                for a in links:
                    href = a.get("href")
                    if not isinstance(href, str):
                        continue
                    # Strip query string variants pointing at the same listing.
                    canonical = href.split("?", 1)[0]
                    if canonical in seen:
                        continue
                    seen.add(canonical)
                    listing = await self._parse_listing(client, canonical)
                    if listing is not None:
                        yield listing
                    await asyncio.sleep(rate_seconds)

    async def health_check(self) -> bool:
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.get(
                    "https://www.etsy.com/search?q=gift",
                    headers={"User-Agent": self.user_agent},
                )
            except httpx.HTTPError:
                return False
            return resp.status_code < 500
