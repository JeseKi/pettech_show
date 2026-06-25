# -*- coding: utf-8 -*-
"""Daily writer API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

MAX_VARIANT_COUNT = 5
DailyWriterJobStatus = Literal["queued", "running", "completed", "failed", "partial_failed"]


class DailyWriterCreate(BaseModel):
    source_seed_matrix_job_id: str = Field(..., min_length=1, max_length=80)
    seed_id: str = Field(..., min_length=1, max_length=128)
    output_date: str | None = Field(default=None, pattern=r"^\d{6}$")
    generate_variants: bool = False
    variant_count: int = 5
    generate_artwork: bool = False

    @model_validator(mode="after")
    def validate_variant_count(self) -> "DailyWriterCreate":
        if self.generate_variants and not 1 <= self.variant_count <= MAX_VARIANT_COUNT:
            raise ValueError(f"variant_count 必须在 1 到 {MAX_VARIANT_COUNT} 之间")
        return self


class DailyWriterJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_seed_matrix_job_id: str
    source_aiwiki_job_id: str
    seed_id: str
    status: DailyWriterJobStatus
    queue_position: int | None = None
    message: str | None = None
    row: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    article_path: str | None = None
    metadata_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    log_tail: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class DailyWriterJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    source_seed_matrix_job_id: str
    source_aiwiki_job_id: str
    seed_id: str
    status: DailyWriterJobStatus
    message: str | None = None
    row: dict[str, str] = Field(default_factory=dict)
    params: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    article_path: str | None = None
    metadata_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class DailyWriterJobListOut(BaseModel):
    items: list[DailyWriterJobSummaryOut]
    total: int
    limit: int
    offset: int


class DailyWriterResultOut(BaseModel):
    job_id: str
    source_seed_matrix_job_id: str
    source_aiwiki_job_id: str
    seed_id: str
    article_path: str
    metadata_path: str
    markdown: str
    illustrated_markdown: str
    metadata: dict[str, Any]
    summary: dict[str, Any] = Field(default_factory=dict)
    variants: list["DailyWriterVariantOut"] = Field(default_factory=list)
    artwork: "DailyWriterArtworkOut" = Field(default_factory=lambda: DailyWriterArtworkOut())


class DailyWriterVariantOut(BaseModel):
    angle: str
    directory: str
    markdown_path: str
    metadata_path: str
    markdown: str
    illustrated_markdown: str
    metadata: dict[str, Any]


class DailyWriterArtworkAssetOut(BaseModel):
    key: str
    path: str
    url: str
    kind: Literal["cover", "inline"]
    filename: str
    content_type: str


class DailyWriterArtworkOut(BaseModel):
    cover_images: list[DailyWriterArtworkAssetOut] = Field(default_factory=list)
    inline_images: list[DailyWriterArtworkAssetOut] = Field(default_factory=list)
    assets_path: str | None = None
