# -*- coding: utf-8 -*-
"""API schemas for Info Distribution uploads."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

DistributionSourceType = Literal["daily_writer", "social_cards", "social_card_videos"]
DistributionUploadType = Literal["article", "image_text", "video"]
DistributionUploadStatus = Literal["running", "completed", "failed"]


class DistributionDirectoryOut(BaseModel):
    accounts: list[dict[str, Any]]
    project_themes: dict[str, Any]


class DistributionUploadRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: DistributionSourceType
    source_job_id: str = Field(..., min_length=1, max_length=100)
    project_id: int = Field(..., ge=1)
    theme_id: int = Field(..., ge=1)
    scheduled_date: date
    per_account_count: int = Field(default=1, ge=1, le=100)
    ignore_history: bool = False
    account_platforms: list[str] = Field(default_factory=list)
    account_query: str | None = Field(default=None, max_length=120)
    user_query: str | None = Field(default=None, max_length=120)
    account_ids: list[int] = Field(default_factory=list)


class DistributionPlanItemOut(BaseModel):
    source_key: str
    source_label: str
    source_path: str | None = None
    title: str
    keyword: str
    content_sha256: str
    markdown_content: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class DistributionPlanBatchOut(BaseModel):
    account: dict[str, Any]
    payload: dict[str, Any]
    items: list[DistributionPlanItemOut]
    article_count: int


class DistributionUploadPlanOut(BaseModel):
    source_type: DistributionSourceType
    source_job_id: str
    upload_type: DistributionUploadType
    scheduled_date: date
    project: dict[str, Any]
    theme: dict[str, Any]
    account_count: int
    batch_count: int
    item_count: int
    skipped: list[dict[str, Any]] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    batches: list[DistributionPlanBatchOut]


class DistributionUploadResultBatchOut(BaseModel):
    account: dict[str, Any]
    created_count: int
    response: Any = None


class DistributionUploadJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    source_type: str
    source_job_id: str
    upload_type: str
    project_id: int
    theme_id: int
    scheduled_date: date
    status: DistributionUploadStatus
    message: str | None = None
    remote_base_url: str
    plan: dict[str, Any] = Field(default_factory=dict)
    result: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DistributionUploadJobListOut(BaseModel):
    items: list[DistributionUploadJobSummaryOut]
    total: int
    limit: int
    offset: int


class DistributionUploadResultOut(BaseModel):
    job: DistributionUploadJobSummaryOut
    plan: DistributionUploadPlanOut
    results: list[DistributionUploadResultBatchOut]
