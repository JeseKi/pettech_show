# -*- coding: utf-8 -*-
"""Social card API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_SOCIAL_CARD_COUNT = 9
DEFAULT_SOCIAL_CARD_COUNT = 6
MAX_SOCIAL_POST_COUNT = 5
DEFAULT_SOCIAL_POST_COUNT = 1
SocialCardJobStatus = Literal["queued", "running", "completed", "failed"]


class SocialCardCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_daily_writer_job_id: str = Field(..., min_length=1, max_length=80)
    post_count: int = DEFAULT_SOCIAL_POST_COUNT
    cards_per_post: int = DEFAULT_SOCIAL_CARD_COUNT
    card_count: int | None = None

    @model_validator(mode="after")
    def validate_count(self) -> "SocialCardCreate":
        if self.card_count is not None:
            self.cards_per_post = self.card_count
        if not 1 <= self.post_count <= MAX_SOCIAL_POST_COUNT:
            raise ValueError(f"post_count 必须在 1 到 {MAX_SOCIAL_POST_COUNT} 之间")
        if not 1 <= self.cards_per_post <= MAX_SOCIAL_CARD_COUNT:
            raise ValueError(f"cards_per_post 必须在 1 到 {MAX_SOCIAL_CARD_COUNT} 之间")
        return self


class SocialCardJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_daily_writer_job_id: str
    status: SocialCardJobStatus
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


class SocialCardJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_daily_writer_job_id: str
    status: SocialCardJobStatus
    message: str | None = None
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class SocialCardJobListOut(BaseModel):
    items: list[SocialCardJobSummaryOut]
    total: int
    limit: int
    offset: int


class SocialCardAssetOut(BaseModel):
    key: str
    path: str
    url: str
    filename: str
    content_type: str


class SocialCardPostOut(BaseModel):
    key: str
    title: str
    images: list[SocialCardAssetOut] = Field(default_factory=list)
    markdown: str = ""
    main_path: str | None = None
    manifest_path: str | None = None
    index_path: str | None = None
    plan_path: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)


class SocialCardResultOut(BaseModel):
    job_id: str
    source_daily_writer_job_id: str
    images: list[SocialCardAssetOut] = Field(default_factory=list)
    posts: list[SocialCardPostOut] = Field(default_factory=list)
    markdown: str = ""
    main_path: str | None = None
    manifest_path: str | None = None
    index_path: str | None = None
    plan_path: str | None = None
    summary: dict[str, Any] = Field(default_factory=dict)
