# -*- coding: utf-8 -*-
"""Schemas for interactive movie editing."""

from __future__ import annotations

from pydantic import BaseModel, Field


class PromptTemplateOut(BaseModel):
    sections: list[str]
    example: str


class UploadedVideoOut(BaseModel):
    url: str | None = None
    storage_uri: str
    object_key: str
    filename: str
    content_type: str
    size: int = Field(ge=0)
