# -*- coding: utf-8 -*-
"""Schemas for interactive movie editing."""

from __future__ import annotations

from typing import Any, Literal

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


class CanvasViewportIn(BaseModel):
    x: float
    y: float
    zoom: float


class SelectedObjectIn(BaseModel):
    type: Literal["scene", "choice"]
    id: str


class VideoPromptPartsIn(BaseModel):
    subject: str = ""
    action: str = ""
    scene: str = ""
    camera: str = ""
    timeline: str = ""
    style: str = ""
    constraints: str = ""


class ScriptLineIn(BaseModel):
    id: str
    speaker: str = ""
    text: str = ""


class SceneScriptIn(BaseModel):
    synopsis: str = ""
    visualDescription: str = ""
    lines: list[ScriptLineIn] = Field(default_factory=list)
    videoPrompt: str = ""
    promptParts: VideoPromptPartsIn = Field(default_factory=VideoPromptPartsIn)


class SceneMediaIn(BaseModel):
    kind: Literal["image", "video", "placeholder"] = "placeholder"
    url: str = ""
    objectKey: str = ""
    storageUri: str = ""
    posterUrl: str = ""
    status: Literal["empty", "mock", "ready"] = "mock"


class SceneNodeIn(BaseModel):
    id: str
    title: str
    role: Literal["start", "middle", "ending"] = "middle"
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    script: SceneScriptIn
    media: SceneMediaIn = Field(default_factory=SceneMediaIn)


class ChoiceEdgeIn(BaseModel):
    id: str
    fromSceneId: str
    toSceneId: str
    label: str
    trigger: Literal["after_scene"] = "after_scene"
    offsetY: float = 0


class InteractiveMovieDocumentIn(BaseModel):
    id: str
    title: str
    updatedAt: str | None = None
    scenes: list[SceneNodeIn] = Field(default_factory=list)
    choices: list[ChoiceEdgeIn] = Field(default_factory=list)
    selectedObject: SelectedObjectIn | None = None
    viewport: CanvasViewportIn = Field(default_factory=lambda: CanvasViewportIn(x=360, y=160, zoom=1))


class InteractiveMovieProjectCreateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    document: InteractiveMovieDocumentIn


class InteractiveMovieProjectSummaryOut(BaseModel):
    id: str
    title: str
    version: int
    content_hash: str
    updated_at: str
    scene_count: int
    choice_count: int


class InteractiveMovieProjectOut(BaseModel):
    id: str
    title: str
    version: int
    content_hash: str
    updated_at: str
    document: dict[str, Any]


class InteractiveMovieSyncStateOut(BaseModel):
    project_id: str
    version: int
    content_hash: str
    updated_at: str


class EntityPatchIn(BaseModel):
    upsert: list[dict[str, Any]] = Field(default_factory=list)
    delete: list[str] = Field(default_factory=list)


class InteractiveMovieProjectPatchIn(BaseModel):
    base_version: int
    base_hash: str
    project: dict[str, Any] = Field(default_factory=dict)
    scenes: EntityPatchIn = Field(default_factory=EntityPatchIn)
    choices: EntityPatchIn = Field(default_factory=EntityPatchIn)
    script_lines: EntityPatchIn = Field(default_factory=EntityPatchIn)
    viewport: dict[str, Any] = Field(default_factory=dict)
    selected_object: dict[str, Any] = Field(default_factory=dict)
