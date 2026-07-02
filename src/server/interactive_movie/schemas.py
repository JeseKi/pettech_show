# -*- coding: utf-8 -*-
"""Schemas for interactive movie editing."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class PromptTemplateOut(BaseModel):
    sections: list[str]
    example: str


class UploadedAssetOut(BaseModel):
    url: str | None = None
    storage_uri: str
    object_key: str
    filename: str
    content_type: str
    size: int = Field(ge=0)


class UploadedVideoOut(UploadedAssetOut):
    pass


class ImagePromptVisualBreakdown(BaseModel):
    subject: str = Field(description="主体、关键外观、姿态、动作、表情、材质、服装和道具")
    scene: str = Field(description="前景、中景、背景、环境和空间关系")
    composition: str = Field(description="画幅比例、镜头距离、视角、主体位置、留白、景深和透视")
    lighting: str = Field(description="主光方向、光质、色温、阴影、高光和氛围光")
    color: str = Field(description="主色、辅助色、色调、饱和度、对比度和后期调色风格")
    style_medium: str = Field(description="真实摄影、电影剧照、插画、3D、动漫、广告海报等风格媒介判断")
    texture: str = Field(description="皮肤、布料、金属、玻璃、颗粒、胶片感、锐度或渲染痕迹")
    ai_generation_trace: str = Field(description="可能的 AI 生成痕迹或模型风格特征，不臆造具体模型名")


class StableDiffusionPromptOut(BaseModel):
    positive_prompt: str = Field(description="Stable Diffusion 或 SDXL 可直接使用的正向提示词")
    negative_prompt: str = Field(description="Stable Diffusion 或 SDXL 可直接使用的负向提示词")


class ImagePromptChoicesOut(BaseModel):
    generic_english_prompt: str = Field(description="适合 GPT Image、Midjourney、Gemini、DALL-E 等模型的通用英文提示词")
    gpt_image_prompt: str = Field(description="适合 GPT Image 的自然语言提示词，强调需要保持的视觉元素")
    sd_prompt: StableDiffusionPromptOut = Field(description="Stable Diffusion 或 SDXL 关键词密集提示词")


class ImagePromptAdvancedOut(BaseModel):
    parameter_suggestions: str = Field(description="画幅比例、风格强度、创意强度、image-to-image 和 denoise/strength 等建议")
    reusable_style_template: str = Field(description="使用变量占位符的可复用风格模板")


class ImagePromptReverseResultOut(BaseModel):
    visual_breakdown: ImagePromptVisualBreakdown
    prompt_choices: ImagePromptChoicesOut
    advanced: ImagePromptAdvancedOut


class ImagePromptReverseRecordOut(BaseModel):
    id: str
    project_id: str | None = None
    filename: str
    content_type: str
    size: int = Field(ge=0)
    object_key: str
    storage_uri: str
    image_url: str | None = None
    result: ImagePromptReverseResultOut
    created_at: str


class CanvasViewportIn(BaseModel):
    x: float
    y: float
    zoom: float


class SelectedObjectIn(BaseModel):
    type: Literal["scene", "choice", "text", "image", "video", "nodeLink"]
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
    videoNodeId: str = ""
    coverImageNodeId: str = ""
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
    offsetX: float = 0
    offsetY: float = 0


class AssetMediaIn(BaseModel):
    url: str = ""
    objectKey: str = ""
    storageUri: str = ""
    contentType: str = ""
    size: int = Field(default=0, ge=0)
    status: Literal["empty", "ready"] = "empty"


class AssetNodeIn(BaseModel):
    id: str
    type: Literal["text", "image", "video"]
    title: str
    position: dict[str, float] = Field(default_factory=lambda: {"x": 0, "y": 0})
    text: str = ""
    media: AssetMediaIn = Field(default_factory=AssetMediaIn)


class NodeLinkEndpointIn(BaseModel):
    type: Literal["scene", "text", "image", "video"]
    id: str
    handle: Literal["top", "right", "bottom", "left"] = "right"


class NodeLinkIn(BaseModel):
    id: str
    from_: NodeLinkEndpointIn = Field(alias="from")
    to: NodeLinkEndpointIn
    offsetX: float = 0
    offsetY: float = 0


class InteractiveMovieDocumentIn(BaseModel):
    id: str
    title: str
    updatedAt: str | None = None
    scenes: list[SceneNodeIn] = Field(default_factory=list)
    choices: list[ChoiceEdgeIn] = Field(default_factory=list)
    assetNodes: list[AssetNodeIn] = Field(default_factory=list)
    nodeLinks: list[NodeLinkIn] = Field(default_factory=list)
    selectedObject: SelectedObjectIn | None = None
    viewport: CanvasViewportIn = Field(default_factory=lambda: CanvasViewportIn(x=360, y=160, zoom=1))


class InteractiveMovieProjectCreateIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)
    document: InteractiveMovieDocumentIn


class InteractiveMovieProjectRenameIn(BaseModel):
    title: str = Field(..., min_length=1, max_length=200)


class InteractiveMovieProjectSummaryOut(BaseModel):
    id: str
    title: str
    version: int
    content_hash: str
    updated_at: str
    scene_count: int
    choice_count: int
    is_published: bool = False
    published_release_id: str | None = None
    published_version_no: int | None = None
    published_at: str | None = None
    public_path: str | None = None


class InteractiveMovieProjectOut(BaseModel):
    id: str
    title: str
    version: int
    content_hash: str
    updated_at: str
    document: dict[str, Any]
    is_published: bool = False
    published_release_id: str | None = None
    published_version_no: int | None = None
    published_at: str | None = None
    public_path: str | None = None


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
    asset_nodes: EntityPatchIn = Field(default_factory=EntityPatchIn)
    node_links: EntityPatchIn = Field(default_factory=EntityPatchIn)
    script_lines: EntityPatchIn = Field(default_factory=EntityPatchIn)
    viewport: dict[str, Any] = Field(default_factory=dict)
    selected_object: dict[str, Any] = Field(default_factory=dict)


class InteractiveMoviePublishIn(BaseModel):
    base_version: int
    base_hash: str


class InteractiveMovieSetPublishedReleaseIn(BaseModel):
    release_id: str = Field(..., min_length=1, max_length=80)


class InteractiveMovieReleaseOut(BaseModel):
    id: str
    project_id: str
    version_no: int
    title: str
    content_hash: str
    created_at: str
    is_current: bool = False


class InteractiveMoviePublishOut(BaseModel):
    project: InteractiveMovieProjectOut
    release: InteractiveMovieReleaseOut


class InteractiveMoviePublicProjectOut(BaseModel):
    id: str
    title: str
    release_id: str
    version_no: int
    content_hash: str
    published_at: str
    document: dict[str, Any]
