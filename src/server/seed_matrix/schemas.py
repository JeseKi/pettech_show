# -*- coding: utf-8 -*-
"""Seed matrix API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

SeedMatrixJobStatus = Literal["queued", "running", "completed", "failed"]


class SeedMatrixCreate(BaseModel):
    source_aiwiki_job_id: str = Field(..., min_length=1, max_length=64)
    expected_seed_count: int = Field(default=10, ge=1, le=500)
    slots_per_day: int = Field(default=3, ge=1, le=24)
    hooks: list[str] = Field(default_factory=list, max_length=20)

    @field_validator("hooks")
    @classmethod
    def normalize_hooks(cls, value: list[str]) -> list[str]:
        return [item.strip() for item in value if item.strip()]


class SeedMatrixJobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class SeedMatrixJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_aiwiki_job_id: str
    title: str | None = None
    status: SeedMatrixJobStatus
    queue_position: int | None = None
    message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    log_tail: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class SeedMatrixJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_aiwiki_job_id: str
    title: str | None = None
    status: SeedMatrixJobStatus
    message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SeedMatrixJobListOut(BaseModel):
    items: list[SeedMatrixJobSummaryOut]
    total: int
    limit: int
    offset: int


class SeedMatrixResultOut(BaseModel):
    job_id: str
    source_aiwiki_job_id: str
    csv_path: str
    summary: dict[str, Any] = Field(default_factory=dict)
    columns: list[str] = Field(default_factory=list)
    rows: list[dict[str, str]] = Field(default_factory=list)
