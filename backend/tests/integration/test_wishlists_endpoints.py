"""Integration tests for /api/v1/wishlists endpoints."""

from __future__ import annotations

import uuid

import pytest

from app.models.enums import ItemStatus


BASE = "/api/v1/wishlists"


# ---------------------------------------------------------------------------
# Full CRUD cycle
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_wishlist(test_client, user_factory, auth_headers):
    user = await user_factory()
    resp = await test_client.post(
        BASE,
        json={"name": "Birthday Gifts", "is_public": False},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["name"] == "Birthday Gifts"
    assert body["user_id"] == str(user.id)


@pytest.mark.asyncio
async def test_get_wishlist_by_owner(test_client, user_factory, wishlist_factory, auth_headers):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id, name="My Wish List")

    resp = await test_client.get(f"{BASE}/{wl.id}", headers=auth_headers(user))
    assert resp.status_code == 200
    assert resp.json()["id"] == str(wl.id)


@pytest.mark.asyncio
async def test_update_wishlist(test_client, user_factory, wishlist_factory, auth_headers):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id, name="Old Name")

    resp = await test_client.patch(
        f"{BASE}/{wl.id}",
        json={"name": "New Name"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Name"


@pytest.mark.asyncio
async def test_delete_wishlist(test_client, user_factory, wishlist_factory, auth_headers):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)

    resp = await test_client.delete(f"{BASE}/{wl.id}", headers=auth_headers(user))
    assert resp.status_code == 204

    # Subsequent get should 404.
    get_resp = await test_client.get(f"{BASE}/{wl.id}", headers=auth_headers(user))
    assert get_resp.status_code == 404


@pytest.mark.asyncio
async def test_crud_cycle_full(test_client, user_factory, auth_headers):
    """End-to-end: create → get → update → delete."""
    user = await user_factory()
    headers = auth_headers(user)

    # Create
    create = await test_client.post(
        BASE, json={"name": "Cycle List"}, headers=headers
    )
    assert create.status_code == 201
    wl_id = create.json()["id"]

    # Get
    get = await test_client.get(f"{BASE}/{wl_id}", headers=headers)
    assert get.status_code == 200

    # Update
    update = await test_client.patch(
        f"{BASE}/{wl_id}", json={"name": "Updated List"}, headers=headers
    )
    assert update.status_code == 200
    assert update.json()["name"] == "Updated List"

    # Delete
    delete = await test_client.delete(f"{BASE}/{wl_id}", headers=headers)
    assert delete.status_code == 204


# ---------------------------------------------------------------------------
# Add / remove items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_item_to_wishlist(
    test_client, user_factory, wishlist_factory, item_factory, auth_headers
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)
    item = await item_factory(status=ItemStatus.ACTIVE)

    resp = await test_client.post(
        f"{BASE}/{wl.id}/items",
        json={"item_id": str(item.id)},
        headers=auth_headers(user),
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["item_id"] == str(item.id)


@pytest.mark.asyncio
async def test_remove_item_from_wishlist(
    test_client, user_factory, wishlist_factory, item_factory, auth_headers
):
    user = await user_factory()
    wl = await wishlist_factory(user_id=user.id)
    item = await item_factory(status=ItemStatus.ACTIVE)

    # Add first.
    await test_client.post(
        f"{BASE}/{wl.id}/items",
        json={"item_id": str(item.id)},
        headers=auth_headers(user),
    )

    # Remove.
    resp = await test_client.delete(
        f"{BASE}/{wl.id}/items/{item.id}",
        headers=auth_headers(user),
    )
    assert resp.status_code == 204


# ---------------------------------------------------------------------------
# Visibility rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_public_wishlist_works_without_auth(
    test_client, wishlist_factory, async_session
):
    wl = await wishlist_factory(is_public=True)

    resp = await test_client.get(f"{BASE}/{wl.id}")
    assert resp.status_code == 200


@pytest.mark.asyncio
async def test_get_private_wishlist_returns_403_for_non_owner(
    test_client, user_factory, wishlist_factory, auth_headers
):
    owner = await user_factory()
    other = await user_factory()
    wl = await wishlist_factory(user_id=owner.id, is_public=False)

    resp = await test_client.get(f"{BASE}/{wl.id}", headers=auth_headers(other))
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_create_wishlist_requires_auth(test_client):
    resp = await test_client.post(BASE, json={"name": "Needs Auth"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_update_wishlist_requires_auth(
    test_client, wishlist_factory
):
    wl = await wishlist_factory()
    resp = await test_client.patch(f"{BASE}/{wl.id}", json={"name": "Hack"})
    assert resp.status_code == 401
