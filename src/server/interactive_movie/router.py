# -*- coding: utf-8 -*-
"""Interactive movie editor routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Response, Security, UploadFile, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from .schemas import (
    InteractiveMovieProjectCreateIn,
    InteractiveMovieProjectOut,
    InteractiveMovieProjectPatchIn,
    InteractiveMovieProjectSummaryOut,
    InteractiveMovieSyncStateOut,
    PromptTemplateOut,
    UploadedVideoOut,
)
from .service import (
    create_project,
    delete_project,
    get_project,
    get_sync_state,
    list_projects,
    patch_project,
    prompt_template,
    read_video_upload,
    upload_video,
)

router = APIRouter(prefix="/api/interactive-movie", tags=["互动电影"])


@router.get("/prompt-template", response_model=PromptTemplateOut, summary="获取视频提示词结构")
async def get_prompt_template(
    _: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return prompt_template()


@router.get("/projects", response_model=list[InteractiveMovieProjectSummaryOut], summary="列出互动电影项目")
async def list_movie_projects(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_projects(db, current_user))


@router.post(
    "/projects",
    response_model=InteractiveMovieProjectOut,
    status_code=status.HTTP_201_CREATED,
    summary="创建互动电影项目",
)
async def create_movie_project(
    payload: InteractiveMovieProjectCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: create_project(db, current_user, payload))


@router.get("/projects/{project_id}", response_model=InteractiveMovieProjectOut, summary="获取互动电影项目")
async def get_movie_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: get_project(db, current_user, project_id))


@router.get(
    "/projects/{project_id}/sync-state",
    response_model=InteractiveMovieSyncStateOut,
    summary="获取互动电影项目轻量同步状态",
)
async def get_movie_project_sync_state(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: get_sync_state(db, current_user, project_id))


@router.patch("/projects/{project_id}", response_model=InteractiveMovieProjectOut, summary="增量保存互动电影项目")
async def patch_movie_project(
    project_id: str,
    payload: InteractiveMovieProjectPatchIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: patch_project(db, current_user, project_id, payload))


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除互动电影项目")
async def delete_movie_project(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    await run_in_thread(lambda: delete_project(db, current_user, project_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


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
