"""Integration tests for /api/v1/items endpoints."""

from __future__ import annotations

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.models.enums import ItemStatus


BASE = "/api/v1/items"


# ---------------------------------------------------------------------------
# GET /items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_items_returns_paginated_list(
    test_client, item_factory
):
    for i in range(3):
        await item_factory(title=f"List Item {i}", status=ItemStatus.ACTIVE)

    resp = await test_client.get(BASE)
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert isinstance(body["items"], list)
    assert len(body["items"]) >= 3


@pytest.mark.asyncio
async def test_list_items_budget_filter_filters_by_price(
    test_client, item_factory
):
    await item_factory(title="Cheap", price=Decimal("5.00"), status=ItemStatus.ACTIVE)
    await item_factory(title="Mid", price=Decimal("30.00"), status=ItemStatus.ACTIVE)
    await item_factory(title="Pricey", price=Decimal("500.00"), status=ItemStatus.ACTIVE)

    resp = await test_client.get(
        BASE, params={"price_min": "10.00", "price_max": "100.00"}
    )
    assert resp.status_code == 200
    titles = {item["title"] for item in resp.json()["items"]}
    assert "Mid" in titles
    assert "Cheap" not in titles
    assert "Pricey" not in titles


@pytest.mark.asyncio
async def test_list_items_returns_only_active_items(
    test_client, item_factory
):
    await item_factory(title="ActiveOne", status=ItemStatus.ACTIVE)
    await item_factory(title="PendingOne", status=ItemStatus.PENDING_REVIEW)

    resp = await test_client.get(BASE)
    assert resp.status_code == 200
    titles = {i["title"] for i in resp.json()["items"]}
    assert "ActiveOne" in titles
    assert "PendingOne" not in titles


# ---------------------------------------------------------------------------
# GET /items/{id}
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_item_returns_item_detail(test_client, item_factory):
    item = await item_factory(title="Specific Item", status=ItemStatus.ACTIVE)

    resp = await test_client.get(f"{BASE}/{item.id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["id"] == str(item.id)
    assert body["title"] == "Specific Item"


@pytest.mark.asyncio
async def test_get_item_unknown_id_returns_404(test_client):
    resp = await test_client.get(f"{BASE}/{uuid.uuid4()}")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# GET /items/categories
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_categories_returns_list(test_client):
    resp = await test_client.get(f"{BASE}/categories")
    # Returns 200 with an (potentially empty) list of tags.
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)


# ---------------------------------------------------------------------------
# POST /search/ai (mocked OpenAI)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ai_search_returns_items_and_interpretation(
    test_client, item_factory, mock_openai, mocker
):
    await item_factory(title="Tech Gadget", status=ItemStatus.ACTIVE)

    # Mock the service methods at the service layer.
    fake_items = []
    from app.schemas.items import ItemSummary
    from app.schemas.search import AISearchResponse, ExtractedFilters

    mocker.patch(
        "app.services.search_service.SearchService.ai_natural_language_search",
        new_callable=AsyncMock,
        return_value=AISearchResponse(
            items=fake_items,
            extracted=ExtractedFilters(
                interest_keywords=["tech"],
                occasion_keywords=["birthday"],
                recipient_keywords=[],
                price_min=None,
                price_max=None,
            ),
            mode="vector",
        ),
    )

    resp = await test_client.post(
        "/api/v1/search/ai",
        json={"query": "birthday gift for tech lover"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "items" in body
    assert "extracted" in body


@pytest.mark.asyncio
async def test_ai_search_requires_query_field(test_client):
    resp = await test_client.post("/api/v1/search/ai", json={})
    # Missing 'query' field → 422.
    assert resp.status_code == 422
