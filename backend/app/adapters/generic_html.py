"""CSS-selector-driven HTML adapter.

The point of this adapter is to add a new retailer without writing Python:
configure CSS selectors in ``scraper_sites.config`` and point the site at
this adapter. Adequate for ~80% of retailer sites; the rest get bespoke
adapters (Amazon, Etsy, etc.).

Expected ``config`` shape::

    {
        "list_url": "https://example.com/category/gifts",
        "list_pages": 3,
        "next_page_param": "page",
        "item_link_selector": "a.product-card",
        "fields": {
            "title": "h1.product-title",
            "price": "span.price",
            "description": "div.product-description",
            "image": "img.product-image"
        },
        "rate_limit_seconds": 1.0
    }
"""

from __future__ import annotations

import asyncio
import hashlib
from collections.abc import AsyncIterator
from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from bs4 import BeautifulSoup, Tag

from app.adapters.base import BaseScrapeAdapter, ScrapeResult
from app.adapters.registry import register_adapter
from app.core.logging import get_logger
from app.core.safe_http import safe_httpx_client, validate_safe_url

log = get_logger(__name__)


@register_adapter
class GenericHtmlAdapter(BaseScrapeAdapter):
    name = "generic_html"

    async def _fetch(self, client: httpx.AsyncClient, url: str) -> str | None:
        # SSRF guard — refuse to fetch private/internal addresses or
        # non-http(s) schemes, even if a misconfigured site config supplies
        # them. Validation re-runs after every redirect we choose to follow.
        try:
            validate_safe_url(url)
        except ValueError as exc:
            log.warning("scraper.fetch.unsafe_url", url=url, error=str(exc))
            return None
        try:
            resp = await client.get(url, headers={"User-Agent": self.user_agent})
            resp.raise_for_status()
            return resp.text
        except httpx.HTTPError as exc:
            log.warning("scraper.fetch.failed", url=url, error=str(exc))
            return None

    @staticmethod
    def _text(soup: Tag, selector: str | None) -> str | None:
        if not selector:
            return None
        node = soup.select_one(selector)
        return node.get_text(strip=True) if node else None

    @staticmethod
    def _attr(soup: Tag, selector: str | None, attr: str) -> str | None:
        if not selector:
            return None
        node = soup.select_one(selector)
        if not node:
            return None
        value = node.get(attr)
        if isinstance(value, list):
            return value[0] if value else None
        return value

    @staticmethod
    def _to_decimal(text: str | None) -> Decimal | None:
        if not text:
            return None
        # Strip everything except digits, decimal points, commas.
        cleaned = "".join(ch for ch in text if ch.isdigit() or ch in ".,")
        # Heuristic: if both a comma and a dot appear, dot is decimal sep.
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(",", "")
        elif "," in cleaned and "." not in cleaned:
            cleaned = cleaned.replace(",", ".")
        if not cleaned:
            return None
        try:
            return Decimal(cleaned)
        except InvalidOperation:
            return None

    async def _parse_item(
        self, client: httpx.AsyncClient, url: str
    ) -> ScrapeResult | None:
        html = await self._fetch(client, url)
        if html is None:
            return None
        soup = BeautifulSoup(html, "html.parser")
        fields: dict[str, Any] = self.config.get("fields", {})

        title = self._text(soup, fields.get("title"))
        if not title:
            log.debug("scraper.item.no_title", url=url)
            return None

        price = self._to_decimal(self._text(soup, fields.get("price")))
        description = self._text(soup, fields.get("description"))
        image = self._attr(soup, fields.get("image"), "src")
        brand = self._text(soup, fields.get("brand"))

        external_id = hashlib.sha256(url.encode()).hexdigest()[:32]

        return ScrapeResult(
            source_external_id=external_id,
            title=title,
            product_url=url,
            description=description,
            price=price,
            currency=self.config.get("currency", "USD"),
            image_url=image,
            brand=brand,
            retailer=self.config.get("retailer"),
            source_url=url,
        )

    async def scrape(self) -> AsyncIterator[ScrapeResult]:
        list_url = self.config.get("list_url")
        if not list_url:
            log.warning("scraper.config.missing_list_url")
            return
        link_selector = self.config.get("item_link_selector", "a")
        pages = int(self.config.get("list_pages", 1))
        next_param = self.config.get("next_page_param")
        rate_seconds = float(self.config.get("rate_limit_seconds", 1.0))

        async with safe_httpx_client() as client:
            seen_urls: set[str] = set()
            for page in range(1, pages + 1):
                page_url = list_url
                if next_param:
                    sep = "&" if "?" in list_url else "?"
                    page_url = f"{list_url}{sep}{next_param}={page}"

                html = await self._fetch(client, page_url)
                if html is None:
                    continue

                soup = BeautifulSoup(html, "html.parser")
                links = soup.select(link_selector)
                for a in links:
                    href = a.get("href")
                    if not href or isinstance(href, list):
                        continue
                    if href.startswith("/"):
                        # Resolve relative against the configured base.
                        base = self.config.get("base_url", "")
                        href = base.rstrip("/") + href
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    item = await self._parse_item(client, href)
                    if item is not None:
                        yield item
                    await asyncio.sleep(rate_seconds)

    async def health_check(self) -> bool:
        url = self.config.get("list_url")
        if not url:
            return False
        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                resp = await client.head(url, headers={"User-Agent": self.user_agent})
            except httpx.HTTPError:
                return False
            return resp.status_code < 500
