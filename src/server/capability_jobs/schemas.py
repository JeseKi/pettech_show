# -*- coding: utf-8 -*-
"""Capability job API schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

CapabilityJobStatus = Literal["queued", "running", "completed", "failed"]


class CapabilityInputOut(BaseModel):
    key: str
    label: str
    type: str
    required: bool
    placeholder: str = ""


class CapabilityConfigOut(BaseModel):
    key: str
    group: str
    path: str
    nav_label: str
    title: str
    description: str
    button_text: str
    inputs: list[CapabilityInputOut]
    outputs: list[str]
    steps: list[str]


class CapabilityCreate(BaseModel):
    capability_key: str = Field(..., min_length=1, max_length=80)
    inputs: dict[str, Any] = Field(default_factory=dict)


class CapabilityJobUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)


class CapabilityJobOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    capability_key: str
    title: str | None = None
    status: CapabilityJobStatus
    queue_position: int | None = None
    message: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    result_markdown_path: str | None = None
    result_json_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    progress: dict[str, Any] = Field(default_factory=dict)
    log_tail: list[str] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class CapabilityJobSummaryOut(BaseModel):
    id: str
    owner_user_id: int | None = None
    owner_username: str | None = None
    capability_key: str
    title: str | None = None
    status: CapabilityJobStatus
    message: str | None = None
    inputs: dict[str, Any] = Field(default_factory=dict)
    summary: dict[str, Any] = Field(default_factory=dict)
    result_markdown_path: str | None = None
    result_json_path: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class CapabilityJobListOut(BaseModel):
    items: list[CapabilityJobSummaryOut]
    total: int
    limit: int
    offset: int


class CapabilityResultOut(BaseModel):
    job_id: str
    capability_key: str
    markdown: str
    data: dict[str, Any]
    summary: dict[str, Any] = Field(default_factory=dict)
