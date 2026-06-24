# -*- coding: utf-8 -*-
"""Interactive movie editor routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, File, Security, UploadFile, status

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.dao.dao_base import run_in_thread

from .schemas import PromptTemplateOut, UploadedVideoOut
from .service import prompt_template, read_video_upload, upload_video

router = APIRouter(prefix="/api/interactive-movie", tags=["互动电影"])


@router.get("/prompt-template", response_model=PromptTemplateOut, summary="获取视频提示词结构")
async def get_prompt_template(
    _: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return prompt_template()


@router.post(
    "/videos",
    response_model=UploadedVideoOut,
    status_code=status.HTTP_201_CREATED,
    summary="上传互动电影场景视频",
)
async def upload_scene_video(
    file: Annotated[UploadFile, File(description="场景视频文件")],
    _: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    content = await read_video_upload(file)
    return await run_in_thread(lambda: upload_video(file, content))
