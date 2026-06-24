# -*- coding: utf-8 -*-
"""Schemas for user chat."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["system", "user", "assistant"]


class ChatMessageIn(BaseModel):
    role: ChatRole
    content: str = Field(..., min_length=1, max_length=20_000)


class ChatCompletionIn(BaseModel):
    messages: list[ChatMessageIn] = Field(..., min_length=1, max_length=30)
    agent_id: str | None = Field(default=None, min_length=2, max_length=80)
    model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)


class ChatUsageOut(BaseModel):
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


class ChatCompletionOut(BaseModel):
    id: str | None = None
    model: str
    role: Literal["assistant"] = "assistant"
    content: str
    usage: ChatUsageOut | None = None
    raw: dict[str, Any] | None = None


class ChatSessionSummaryOut(BaseModel):
    id: str
    title: str
    agent_id: str | None = None
    agent_revision_id: str | None = None
    agent_name: str | None = None
    created_at: str
    updated_at: str
    message_count: int = 0


class ChatMessageOut(BaseModel):
    id: str
    role: ChatRole
    content: str
    created_at: str


class ChatSessionRenameIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class ChatSessionStreamIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=80)
    agent_id: str | None = Field(default=None, min_length=2, max_length=80)
    content: str = Field(..., min_length=1, max_length=20_000)
    model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)
