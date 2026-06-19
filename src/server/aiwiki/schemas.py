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


class JobOut(BaseModel):
    id: str
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
    status: JobStatus
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[UploadedFileOut] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class JobListOut(BaseModel):
    items: list[JobSummaryOut]
    total: int
    limit: int
    offset: int


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


class WikiEntryOut(BaseModel):
    path: str
    slug: str
    type: str
    title: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    sections: list[dict[str, str]] = Field(default_factory=list)
    references: list[str] = Field(default_factory=list)


class AiwikiResultOut(BaseModel):
    job_id: str
    summary: dict[str, Any] = Field(default_factory=dict)
    materials: list[MaterialOut] = Field(default_factory=list)
    hotspots: list[dict[str, Any]] = Field(default_factory=list)
    pain_points: list[dict[str, Any]] = Field(default_factory=list)
    solutions: list[dict[str, Any]] = Field(default_factory=list)
    topics: list[dict[str, Any]] = Field(default_factory=list)
    search_intents: list[dict[str, Any]] = Field(default_factory=list)
    wiki_entries: list[WikiEntryOut] = Field(default_factory=list)
    highlight_terms: list[str] = Field(default_factory=list)
    navigation: list[dict[str, Any]] = Field(default_factory=list)

    model_config = ConfigDict(arbitrary_types_allowed=True)
