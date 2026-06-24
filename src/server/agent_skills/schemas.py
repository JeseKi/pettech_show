# -*- coding: utf-8 -*-
"""Schemas for agent skills."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


SkillVisibility = Literal["public", "admin"]


class AgentSkillCategoryOut(BaseModel):
    id: str
    name: str
    description: str
    sort_order: int
    enabled: bool


class AgentSkillCategoryCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(default="", max_length=2000)


class AgentSkillCategoryUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    enabled: bool | None = None


class AgentSkillTagOut(BaseModel):
    id: str
    name: str
    sort_order: int
    enabled: bool


class AgentSkillTagCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)


class AgentSkillTagUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    enabled: bool | None = None


class AgentSkillOut(BaseModel):
    id: str
    slug: str
    mention: str
    name: str
    title: str
    category: str
    category_id: str
    category_label: str
    visibility: SkillVisibility
    summary: str
    description: str
    tags: list[str]
    tag_ids: list[str]
    added: bool = False
    skill_markdown: str | None = None


class UserAgentSkillOut(AgentSkillOut):
    added_at: str


class AgentSkillPageOut(BaseModel):
    items: list[AgentSkillOut]
    total: int
    page: int
    page_size: int


class UserAgentSkillPageOut(BaseModel):
    items: list[UserAgentSkillOut]
    total: int
    page: int
    page_size: int


class AgentSkillCreateIn(BaseModel):
    id: str = Field(..., min_length=2, max_length=61)
    name: str = Field(..., min_length=1, max_length=120)
    description: str = Field(..., min_length=1, max_length=2000)
    category_id: str = Field(..., min_length=2, max_length=61)
    tag_ids: list[str] = Field(default_factory=list, max_length=20)
    visibility: SkillVisibility = "public"
    skill_markdown: str = Field(..., min_length=1, max_length=40_000)


class AgentSkillUpdateIn(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, min_length=1, max_length=2000)
    category_id: str | None = Field(default=None, min_length=2, max_length=61)
    tag_ids: list[str] | None = Field(default=None, max_length=20)
    visibility: SkillVisibility | None = None
    skill_markdown: str | None = Field(default=None, min_length=1, max_length=40_000)
