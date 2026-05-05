"""Cron-schedule admin schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


def _looks_like_cron_expr(expr: str) -> bool:
    """Best-effort sanity check on a 5-or-6-field cron expression."""
    parts = expr.strip().split()
    return len(parts) in (5, 6)


class CronScheduleIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    cron_expr: str = Field(min_length=9, max_length=100)
    task_name: str = Field(min_length=1, max_length=200)
    task_kwargs: dict[str, Any] = Field(default_factory=dict)
    is_active: bool = True

    @field_validator("cron_expr")
    @classmethod
    def _validate_cron(cls, v: str) -> str:
        if not _looks_like_cron_expr(v):
            raise ValueError("cron_expr must have 5 or 6 whitespace-separated fields")
        return v


class CronScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    cron_expr: str | None = Field(default=None, min_length=9, max_length=100)
    task_name: str | None = Field(default=None, min_length=1, max_length=200)
    task_kwargs: dict[str, Any] | None = None
    is_active: bool | None = None

    @field_validator("cron_expr")
    @classmethod
    def _validate_cron(cls, v: str | None) -> str | None:
        if v is not None and not _looks_like_cron_expr(v):
            raise ValueError("cron_expr must have 5 or 6 whitespace-separated fields")
        return v


class CronScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    cron_expr: str
    task_name: str
    task_kwargs: dict[str, Any]
    is_active: bool
    last_run_at: datetime | None
    next_run_at: datetime | None
    created_at: datetime
    updated_at: datetime
