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
    InteractiveMoviePublicProjectOut,
    InteractiveMoviePublishIn,
    InteractiveMoviePublishOut,
    InteractiveMovieProjectCreateIn,
    InteractiveMovieProjectOut,
    InteractiveMovieProjectPatchIn,
    InteractiveMovieProjectRenameIn,
    InteractiveMovieProjectSummaryOut,
    InteractiveMovieReleaseOut,
    InteractiveMovieSetPublishedReleaseIn,
    InteractiveMovieSyncStateOut,
    PromptTemplateOut,
    UploadedVideoOut,
)
from .service import (
    close_publication,
    create_project,
    delete_project,
    get_public_project,
    get_project,
    get_sync_state,
    list_releases,
    list_projects,
    patch_project,
    publish_project,
    prompt_template,
    read_video_upload,
    rename_project,
    set_published_release,
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


@router.get(
    "/projects/{project_id}/releases",
    response_model=list[InteractiveMovieReleaseOut],
    summary="列出互动电影正式版历史",
)
async def list_movie_project_releases(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_releases(db, current_user, project_id))


@router.post(
    "/projects/{project_id}/releases",
    response_model=InteractiveMoviePublishOut,
    status_code=status.HTTP_201_CREATED,
    summary="发表当前互动电影草稿为正式版",
)
async def publish_movie_project(
    project_id: str,
    payload: InteractiveMoviePublishIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: publish_project(db, current_user, project_id, payload))


@router.put(
    "/projects/{project_id}/published-release",
    response_model=InteractiveMovieProjectOut,
    summary="切换互动电影线上正式版",
)
async def set_movie_project_published_release(
    project_id: str,
    payload: InteractiveMovieSetPublishedReleaseIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: set_published_release(db, current_user, project_id, payload))


@router.delete(
    "/projects/{project_id}/published-release",
    response_model=InteractiveMovieProjectOut,
    summary="关闭互动电影发表",
)
async def close_movie_project_publication(
    project_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: close_publication(db, current_user, project_id))


@router.patch("/projects/{project_id}", response_model=InteractiveMovieProjectOut, summary="增量保存互动电影项目")
async def patch_movie_project(
    project_id: str,
    payload: InteractiveMovieProjectPatchIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: patch_project(db, current_user, project_id, payload))


@router.patch(
    "/projects/{project_id}/title",
    response_model=InteractiveMovieProjectOut,
    summary="重命名互动电影项目",
)
async def rename_movie_project(
    project_id: str,
    payload: InteractiveMovieProjectRenameIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: rename_project(db, current_user, project_id, payload))


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


@router.get(
    "/public/{project_id}",
    response_model=InteractiveMoviePublicProjectOut,
    summary="公开读取已发表互动电影",
)
async def get_public_movie_project(
    project_id: str,
    db: Session = Depends(get_db),
):
    return await run_in_thread(lambda: get_public_project(db, project_id))
