# -*- coding: utf-8 -*-
"""Social card slideshow video public API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.database import get_db

from . import service
from .schemas import (
    SocialCardVideoJobListOut,
    SocialCardVideoJobOut,
    SocialCardVideoJobUpdate,
    SocialCardVideoResultOut,
)
from src.server.social_card_videos.service.jobs.mutations import (
    update_job_title as update_social_card_video_job_title,
)

router = APIRouter(prefix="/api/social-card-videos", tags=["小红书轮播视频"])


@router.post(
    "/jobs",
    response_model=SocialCardVideoJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建小红书轮播视频生成任务",
)
async def create_social_card_video_job(
    source_social_card_job_id: Annotated[str, Form(min_length=1, max_length=80)],
    title: Annotated[str, Form(min_length=1, max_length=120)],
    voice_text: Annotated[str, Form(max_length=2000)] = "",
    bgm_start: Annotated[float, Form(ge=0)] = 0,
    bgm_file: UploadFile | None = File(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_job(
        db,
        source_social_card_job_id=source_social_card_job_id,
        title=title,
        voice_text=voice_text,
        bgm_start=bgm_start,
        bgm_file=bgm_file,
        current_user=current_user,
    )


@router.get(
    "/jobs",
    response_model=SocialCardVideoJobListOut,
    summary="列出小红书轮播视频历史任务",
)
async def list_social_card_video_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_social_card_job_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        source_social_card_job_id=source_social_card_job_id,
        current_user=current_user,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=SocialCardVideoJobOut,
    summary="获取小红书轮播视频任务状态",
)
async def get_social_card_video_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.patch(
    "/jobs/{job_id}",
    response_model=SocialCardVideoJobOut,
    summary="更新小红书轮播视频任务",
)
async def update_social_card_video_job(
    job_id: str,
    payload: SocialCardVideoJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_social_card_video_job_title(db, job_id, payload, current_user)


@router.get(
    "/jobs/{job_id}/result",
    response_model=SocialCardVideoResultOut,
    summary="获取小红书轮播视频结果",
)
async def get_social_card_video_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get(
    "/jobs/{job_id}/videos/{asset_key}",
    summary="获取小红书轮播视频文件",
)
async def get_social_card_video_file(
    job_id: str,
    asset_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path, media_type = service.video_file(db, job_id, asset_key, current_user)
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get(
    "/jobs/{job_id}/download",
    summary="下载小红书轮播视频文件",
)
async def download_social_card_video_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = service.result_zip_file(db, job_id, current_user)
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}.zip")


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除小红书轮播视频任务",
)
async def delete_social_card_video_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
