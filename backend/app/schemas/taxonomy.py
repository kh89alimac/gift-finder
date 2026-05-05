"""Tag taxonomy schemas (admin CRUD + discovery filter UI)."""

from __future__ import annotations

import re
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class TagSlim(BaseModel):
    """Minimal tag representation embedded in item responses."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    slug: str
    tag_type_id: int


class TagOut(TagSlim):
    """Full tag with metadata + parent reference."""

    parent_tag_id: int | None
    sort_order: int
    is_active: bool
    tag_metadata: dict[str, Any] = Field(default_factory=dict, alias="tag_metadata")


class TagCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tag_type_id: int = Field(ge=1)
    name: str = Field(min_length=1, max_length=100)
    slug: str = Field(min_length=1, max_length=100)
    parent_tag_id: int | None = None
    sort_order: int = 0
    is_active: bool = True
    tag_metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError("Slug must be lowercase letters/digits with hyphen separators")
        return v


class TagUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    slug: str | None = Field(default=None, min_length=1, max_length=100)
    parent_tag_id: int | None = None
    sort_order: int | None = None
    is_active: bool | None = None
    tag_metadata: dict[str, Any] | None = None

    @field_validator("slug")
    @classmethod
    def _slug_format(cls, v: str | None) -> str | None:
        if v is not None and not _SLUG_RE.match(v):
            raise ValueError("Slug must be lowercase letters/digits with hyphen separators")
        return v


class TagTypeOut(BaseModel):
    """A category of tags (e.g. 'occasion'). Includes its child tags."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    description: str | None
    is_filterable: bool
    sort_order: int
    tags: list[TagOut] = Field(default_factory=list)


class TagTypeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=50)
    description: str | None = None
    is_filterable: bool = True
    sort_order: int = 0


class TagTypeUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=50)
    description: str | None = None
    is_filterable: bool | None = None
    sort_order: int | None = None


class TaxonomyTree(BaseModel):
    """Complete filterable taxonomy used to render the discovery sidebar."""

    types: list[TagTypeOut]


class TagMergeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_tag_id: int = Field(ge=1)
    target_tag_id: int = Field(ge=1)

    @field_validator("target_tag_id")
    @classmethod
    def _no_self_merge(cls, v: int, info: Any) -> int:
        # ``info.data`` carries previously-validated fields.
        if info.data.get("source_tag_id") == v:
            raise ValueError("Source and target must differ")
        return v
