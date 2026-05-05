"""Admin taxonomy CRUD + tag merge."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.dependencies import AdminUser, UowDep
from app.schemas.taxonomy import (
    TagCreate,
    TagMergeRequest,
    TagOut,
    TagTypeCreate,
    TagTypeOut,
    TagTypeUpdate,
    TagUpdate,
)
from app.services.taxonomy_service import TaxonomyService

router = APIRouter(prefix="/admin/taxonomy", tags=["admin"])


# ---------------------------------------------------------------- TagType


@router.get("/tag-types", response_model=list[TagTypeOut])
async def list_tag_types(uow: UowDep, _admin: AdminUser) -> list[TagTypeOut]:
    service = TaxonomyService(uow)
    return await service.list_types()


@router.post(
    "/tag-types",
    response_model=TagTypeOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag_type(
    payload: TagTypeCreate, uow: UowDep, _admin: AdminUser
) -> TagTypeOut:
    service = TaxonomyService(uow)
    return await service.create_type(payload)


@router.patch("/tag-types/{type_id}", response_model=TagTypeOut)
async def update_tag_type(
    type_id: int, payload: TagTypeUpdate, uow: UowDep, _admin: AdminUser
) -> TagTypeOut:
    service = TaxonomyService(uow)
    return await service.update_type(type_id, payload)


@router.delete("/tag-types/{type_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag_type(type_id: int, uow: UowDep, _admin: AdminUser) -> None:
    service = TaxonomyService(uow)
    await service.delete_type(type_id)


# -------------------------------------------------------------------- Tag


@router.post(
    "/tags",
    response_model=TagOut,
    status_code=status.HTTP_201_CREATED,
)
async def create_tag(
    payload: TagCreate, uow: UowDep, _admin: AdminUser
) -> TagOut:
    service = TaxonomyService(uow)
    return await service.create_tag(payload)


@router.patch("/tags/{tag_id}", response_model=TagOut)
async def update_tag(
    tag_id: int, payload: TagUpdate, uow: UowDep, _admin: AdminUser
) -> TagOut:
    service = TaxonomyService(uow)
    return await service.update_tag(tag_id, payload)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tag(tag_id: int, uow: UowDep, _admin: AdminUser) -> None:
    service = TaxonomyService(uow)
    await service.delete_tag(tag_id)


@router.post("/tags/merge")
async def merge_tags(
    payload: TagMergeRequest, uow: UowDep, _admin: AdminUser
) -> dict[str, int]:
    service = TaxonomyService(uow)
    moved = await service.merge_tags(payload.source_tag_id, payload.target_tag_id)
    return {"moved_item_tags": moved}
