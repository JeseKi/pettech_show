# -*- coding: utf-8 -*-
"""Schemas for user chat."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ChatRole = Literal["system", "user", "assistant", "tool"]


class ChatMessageIn(BaseModel):
    role: ChatRole
    content: str = Field(default="", max_length=20_000)
    reasoning_content: str | None = Field(default=None, max_length=200_000)
    name: str | None = Field(default=None, max_length=100)
    tool_call_id: str | None = Field(default=None, max_length=200)
    tool_calls: list[dict[str, Any]] | None = None


class ChatCompletionIn(BaseModel):
    messages: list[ChatMessageIn] = Field(..., min_length=1, max_length=30)
    agent_id: str | None = Field(default=None, min_length=2, max_length=80)
    model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)
    tools: list[dict[str, Any]] | None = None


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


class ChatToolStepOut(BaseModel):
    content: str | None = None
    kind: Literal["model_output", "tool_call", "tool_result"]
    name: str | None = None
    status: Literal["done", "error", "running"] | None = None
    title: str


class ChatMessageOut(BaseModel):
    id: str
    role: ChatRole
    content: str
    created_at: str
    tool_steps: list[ChatToolStepOut] = Field(default_factory=list)


class ChatSessionRenameIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class ChatSessionStreamIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=80)
    agent_id: str | None = Field(default=None, min_length=2, max_length=80)
    content: str = Field(..., min_length=1, max_length=20_000)
    model: str | None = Field(default=None, max_length=100)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int | None = Field(default=None, ge=1, le=32_000)
    tools: list[dict[str, Any]] | None = None


class ChatSessionPersistIn(BaseModel):
    session_id: str | None = Field(default=None, max_length=80)
    agent_id: str | None = Field(default=None, min_length=2, max_length=80)
    user_content: str = Field(..., min_length=1, max_length=20_000)
    assistant_content: str = Field(..., min_length=1, max_length=20_000)
    model: str | None = Field(default=None, max_length=100)
    rollout_items: list[dict[str, Any]] | None = None
