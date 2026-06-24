# -*- coding: utf-8 -*-
"""Schemas for agent marketplace."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


AgentVisibility = Literal["public", "admin"]


class AgentCategoryOut(BaseModel):
    id: str
    name: str
    description: str
    visibility: AgentVisibility
    sort_order: int
    enabled: bool


class AgentCategoryCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)
    visibility: AgentVisibility = "public"


class AgentCategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    visibility: AgentVisibility | None = None
    enabled: bool | None = None


class AgentTagOut(BaseModel):
    id: str
    name: str
    sort_order: int
    enabled: bool


class AgentTagCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)


class AgentTagUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None


class AgentPromptRevisionOut(BaseModel):
    id: str
    agent_id: str
    version: int
    active: bool
    change_note: str
    created_by_user_id: int | None
    created_at: str
    system_prompt: str | None = None


class AgentOut(BaseModel):
    id: str
    slug: str
    name: str
    title: str
    category: str
    category_id: str
    category_label: str
    visibility: AgentVisibility
    summary: str
    description: str
    tags: list[str]
    tag_ids: list[str]
    enabled: bool
    is_default: bool
    protected: bool
    added: bool = False
    current_revision_id: str | None
    current_version: int | None
    system_prompt: str | None = None


class UserAgentOut(AgentOut):
    added_at: str


class AgentPageOut(BaseModel):
    items: list[AgentOut]
    total: int
    page: int
    page_size: int


class UserAgentPageOut(BaseModel):
    items: list[UserAgentOut]
    total: int
    page: int
    page_size: int


class AgentCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    category_id: str = Field(..., min_length=2, max_length=61)
    tag_ids: list[str] = Field(default_factory=list, max_length=20)
    visibility: AgentVisibility = "public"
    system_prompt: str = Field(..., min_length=1, max_length=60_000)
    change_note: str = Field(default="初始版本", max_length=2000)


class AgentUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    category_id: str | None = Field(default=None, min_length=2, max_length=61)
    tag_ids: list[str] | None = Field(default=None, max_length=20)
    visibility: AgentVisibility | None = None
    enabled: bool | None = None
    system_prompt: str | None = Field(default=None, min_length=1, max_length=60_000)
    change_note: str | None = Field(default=None, max_length=2000)
