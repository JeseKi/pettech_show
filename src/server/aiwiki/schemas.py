# -*- coding: utf-8 -*-
"""AI Wiki API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "completed", "failed"]


class UploadedFileOut(BaseModel):
    filename: str
    size_bytes: int
    raw_path: str
    workspace_raw_path: str | None = None
    raw_source_path: str | None = None
    upload_path: str | None = None
    extension: str | None = None
    mime_type: str | None = None
    category: Literal["graphic_text", "document"] | None = None
    preview_status: Literal["ready", "failed"] | None = None
    preview: dict[str, Any] = Field(default_factory=dict)


class JobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    title: str
    description: str | None = None
    status: JobStatus
    queue_position: int | None = None
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[UploadedFileOut] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    log_tail: list[str] = Field(default_factory=list)


class JobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    title: str
    description: str | None = None
    status: JobStatus
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[UploadedFileOut] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class AiwikiStatsOut(BaseModel):
    graphic_text_count: int = 0
    document_count: int = 0
    display_count: int = 0
    total_count: int = 0


class JobListOut(BaseModel):
    items: list[JobSummaryOut]
    total: int
    limit: int
    offset: int
    stats: AiwikiStatsOut = Field(default_factory=AiwikiStatsOut)


class JobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class AiwikiAuditLogOut(BaseModel):
    id: int
    actor_user_id: int
    actor_username: str
    action: str
    job_id: str | None = None
    target_filename: str
    message: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime


class AiwikiAuditLogListOut(BaseModel):
    items: list[AiwikiAuditLogOut]
    total: int
    limit: int
    offset: int
    scope: Literal["mine", "all"]


class MaterialOut(BaseModel):
    path: str
    title: str
    positioning: str | None = None
    pain_points: list[dict[str, Any]] = Field(default_factory=list)
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    solutions: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[str] = Field(default_factory=list)
    search_intents: list[dict[str, Any]] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class WikiReferenceOut(BaseModel):
    slug: str
    title: str
    path: str | None = None
    type: str | None = None


class WikiHomeOut(BaseModel):
    path: str
    title: str
    body_markdown: str
    references: list[str] = Field(default_factory=list)
    headings: list[dict[str, Any]] = Field(default_factory=list)


class WikiEntryOut(BaseModel):
    path: str
    slug: str
    type: str
    title: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_markdown: str = ""
    excerpt: str = ""
    created: str | None = None
    updated: str | None = None
    sections: list[dict[str, str]] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)
    reference_links: list[WikiReferenceOut] = Field(default_factory=list)


class AiwikiResultOut(BaseModel):
    job_id: str
    summary: dict[str, Any] = Field(default_factory=dict)
    materials: list[MaterialOut] = Field(default_factory=list)
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    pain_points: list[dict[str, Any]] = Field(default_factory=list)
    solutions: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[dict[str, Any]] = Field(default_factory=list)
    search_intents: list[dict[str, Any]] = Field(default_factory=list)
    wiki_home: WikiHomeOut | None = None
    wiki_entries: list[WikiEntryOut] = Field(default_factory=list)
    highlight_terms: list[str] = Field(default_factory=list)
    navigation: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
