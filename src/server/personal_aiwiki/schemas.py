# -*- coding: utf-8 -*-
"""Personal AI Wiki API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.server.aiwiki.schemas import (
    AiwikiResultOut,
    JobStatus,
    UploadedFileOut,
)

PersonalAiwikiOperation = Literal["ingest", "query", "lint"]


class PersonalAiwikiJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    operation: PersonalAiwikiOperation
    title: str
    description: str | None = None
    status: JobStatus
    queue_position: int | None = None
    message: str | None = None
    workspace_dir: str
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[UploadedFileOut] = Field(default_factory=list)
    progress: dict[str, Any] = Field(default_factory=dict)
    log_tail: list[str] = Field(default_factory=list)


class PersonalAiwikiJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    operation: PersonalAiwikiOperation
    title: str
    description: str | None = None
    status: JobStatus
    message: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    files: list[UploadedFileOut] = Field(default_factory=list)
    summary: dict[str, Any] = Field(default_factory=dict)


class PersonalAiwikiStatsOut(BaseModel):
    ingest_count: int = 0
    query_count: int = 0
    lint_count: int = 0
    active_count: int = 0
    completed_count: int = 0
    total_count: int = 0


class PersonalAiwikiJobListOut(BaseModel):
    items: list[PersonalAiwikiJobSummaryOut]
    total: int
    limit: int
    offset: int
    stats: PersonalAiwikiStatsOut = Field(default_factory=PersonalAiwikiStatsOut)


class PersonalAiwikiJobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=1000)


class PersonalAiwikiResultOut(AiwikiResultOut):
    operation: PersonalAiwikiOperation | None = None
    answer_markdown: str | None = None
    workspace_dir: str | None = None

    model_config = ConfigDict(arbitrary_types_allowed=True)


class PersonalAiwikiEntryPageOut(BaseModel):
    slug: str
    path: str
    title: str
    type: str
    frontmatter: dict[str, Any] = Field(default_factory=dict)
    body_markdown: str = ""
    markdown: str = ""
