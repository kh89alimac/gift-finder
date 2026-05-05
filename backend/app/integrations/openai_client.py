"""OpenAI client wrapper.

Two responsibilities:

1. Embed text for vector search and item-similarity (``embed_texts``).
2. Extract structured gift filters from a natural-language search query using
   function calling (``extract_gift_filters``).

Both functions are async and degrade gracefully: callers should already be
prepared to fall back to keyword search when these fail.
"""

from __future__ import annotations

import json
from typing import Any

from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.logging import get_logger

log = get_logger(__name__)


# ---------------------------------------------------------------------------
# Client management
# ---------------------------------------------------------------------------


_client: AsyncOpenAI | None = None


def get_openai_client() -> AsyncOpenAI:
    """Return the shared async client. Raises if no API key is configured."""
    global _client
    if settings.OPENAI_API_KEY is None:
        raise ExternalServiceError("OPENAI_API_KEY is not configured")
    if _client is None:
        _client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY.get_secret_value())
    return _client


# ---------------------------------------------------------------------------
# Embeddings
# ---------------------------------------------------------------------------


# OpenAI's batch limit for embeddings is generous (2048 inputs) but we batch
# in 96s for safety and to keep individual requests under their 8K-token
# total. Adjust based on your average input length.
_EMBED_BATCH = 96


async def embed_texts(texts: list[str]) -> list[list[float]]:
    """Return one embedding per input string, in order.

    Empty strings are replaced with a single space so the API doesn't error.
    """
    if not texts:
        return []
    client = get_openai_client()
    cleaned = [t if t.strip() else " " for t in texts]

    out: list[list[float]] = []
    for i in range(0, len(cleaned), _EMBED_BATCH):
        batch = cleaned[i : i + _EMBED_BATCH]
        try:
            resp = await client.embeddings.create(
                model=settings.OPENAI_EMBEDDING_MODEL,
                input=batch,
            )
        except Exception as exc:
            log.error("openai.embed.failed", error=str(exc), batch_size=len(batch))
            raise ExternalServiceError(f"OpenAI embeddings call failed: {exc}") from exc
        # ``data`` is documented to come back in input order.
        out.extend([d.embedding for d in resp.data])
    return out


async def embed_one(text: str) -> list[float]:
    """Convenience wrapper for the common single-text case."""
    result = await embed_texts([text])
    return result[0]


# ---------------------------------------------------------------------------
# Filter extraction (function calling)
# ---------------------------------------------------------------------------


class GiftFilterExtraction(BaseModel):
    """Structured filter set parsed from a natural-language gift query."""

    interest_keywords: list[str] = Field(default_factory=list)
    occasion_keywords: list[str] = Field(default_factory=list)
    recipient_keywords: list[str] = Field(default_factory=list)
    price_min: float | None = None
    price_max: float | None = None
    cleaned_query: str = Field(
        default="",
        description="The original query stripped of price/occasion phrases",
    )


_EXTRACTION_TOOL = {
    "type": "function",
    "function": {
        "name": "extract_gift_filters",
        "description": (
            "Pull structured gift-search filters from a user's natural-language "
            "query. Identify interests, the occasion, who the gift is for, and "
            "any budget constraints."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "interest_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Hobbies, themes, product categories",
                },
                "occasion_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Birthday, anniversary, wedding, etc.",
                },
                "recipient_keywords": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Relationship or persona (mom, coworker, kids)",
                },
                "price_min": {"type": ["number", "null"]},
                "price_max": {"type": ["number", "null"]},
                "cleaned_query": {
                    "type": "string",
                    "description": "Query with price + occasion phrasing stripped, kept descriptive",
                },
            },
            "required": [
                "interest_keywords",
                "occasion_keywords",
                "recipient_keywords",
                "price_min",
                "price_max",
                "cleaned_query",
            ],
        },
    },
}


async def extract_gift_filters(query: str) -> GiftFilterExtraction:
    """Use a small model + function calling to parse ``query`` into filters.

    On any failure we return an empty extraction with ``cleaned_query=query``
    so the caller can still run a vanilla full-text search.
    """
    if not query.strip():
        return GiftFilterExtraction(cleaned_query="")

    try:
        client = get_openai_client()
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You parse gift-search queries into structured filters. "
                        "Always call extract_gift_filters."
                    ),
                },
                {"role": "user", "content": query},
            ],
            tools=[_EXTRACTION_TOOL],  # type: ignore[arg-type]
            tool_choice={
                "type": "function",
                "function": {"name": "extract_gift_filters"},
            },
        )
    except Exception as exc:
        log.warning("openai.extract.failed", error=str(exc), query=query)
        return GiftFilterExtraction(cleaned_query=query)

    choice = resp.choices[0].message
    tool_calls = getattr(choice, "tool_calls", None) or []
    if not tool_calls:
        return GiftFilterExtraction(cleaned_query=query)

    raw_args = tool_calls[0].function.arguments or "{}"
    try:
        data: dict[str, Any] = json.loads(raw_args)
    except json.JSONDecodeError:
        return GiftFilterExtraction(cleaned_query=query)

    try:
        return GiftFilterExtraction.model_validate(data)
    except Exception as exc:
        log.warning("openai.extract.invalid_payload", error=str(exc), payload=data)
        return GiftFilterExtraction(cleaned_query=query)


# ---------------------------------------------------------------------------
# Auto-categorization (function calling) — used by scrapers
# ---------------------------------------------------------------------------


_CATEGORIZE_TOOL = {
    "type": "function",
    "function": {
        "name": "suggest_tags",
        "description": (
            "Suggest taxonomy tags for a product based on its title and description. "
            "Pick interest categories, age range, occasion, and recipient personas."
        ),
        "parameters": {
            "type": "object",
            "additionalProperties": False,
            "properties": {
                "interest_slugs": {"type": "array", "items": {"type": "string"}},
                "occasion_slugs": {"type": "array", "items": {"type": "string"}},
                "recipient_slugs": {"type": "array", "items": {"type": "string"}},
                "confidence": {"type": "number", "minimum": 0, "maximum": 1},
            },
            "required": [
                "interest_slugs",
                "occasion_slugs",
                "recipient_slugs",
                "confidence",
            ],
        },
    },
}


class CategorizationSuggestion(BaseModel):
    interest_slugs: list[str] = Field(default_factory=list)
    occasion_slugs: list[str] = Field(default_factory=list)
    recipient_slugs: list[str] = Field(default_factory=list)
    confidence: float = 0.0


async def suggest_tags_for_item(
    title: str, description: str | None
) -> CategorizationSuggestion:
    """Ask the model to suggest tag slugs for a freshly scraped item."""
    if not title.strip():
        return CategorizationSuggestion()

    try:
        client = get_openai_client()
        prompt = title + ("\n\n" + description if description else "")
        resp = await client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You categorize gift items. Always call suggest_tags. "
                        "Use lowercase-hyphen slugs (e.g. 'home-decor', 'birthday')."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            tools=[_CATEGORIZE_TOOL],  # type: ignore[arg-type]
            tool_choice={
                "type": "function",
                "function": {"name": "suggest_tags"},
            },
        )
    except Exception as exc:
        log.warning("openai.categorize.failed", error=str(exc))
        return CategorizationSuggestion()

    tool_calls = getattr(resp.choices[0].message, "tool_calls", None) or []
    if not tool_calls:
        return CategorizationSuggestion()
    try:
        data = json.loads(tool_calls[0].function.arguments or "{}")
        return CategorizationSuggestion.model_validate(data)
    except Exception:
        return CategorizationSuggestion()
