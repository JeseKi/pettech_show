# -*- coding: utf-8 -*-
"""Social card video API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

SocialCardVideoJobStatus = Literal["queued", "running", "completed", "failed"]


class SocialCardVideoJobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class SocialCardVideoJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_social_card_job_id: str
    title: str | None = None
    status: SocialCardVideoJobStatus
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


class SocialCardVideoJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_social_card_job_id: str
    title: str | None = None
    status: SocialCardVideoJobStatus
    message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SocialCardVideoJobListOut(BaseModel):
    items: list[SocialCardVideoJobSummaryOut]
    total: int
    limit: int
    offset: int


class SocialCardVideoAssetOut(BaseModel):
    key: str
    path: str
    url: str
    filename: str
    content_type: str
    markdown_path: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class SocialCardVideoResultOut(BaseModel):
    job_id: str
    source_social_card_job_id: str
    videos: list[SocialCardVideoAssetOut] = Field(default_factory=list)
    markdown: str = ""
    summary: dict[str, Any] = Field(default_factory=dict)
