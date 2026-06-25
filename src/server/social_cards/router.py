# -*- coding: utf-8 -*-
"""Social card public API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.database import get_db

from . import service
from .schemas import (
    SocialCardCreate,
    SocialCardJobListOut,
    SocialCardJobOut,
    SocialCardJobUpdate,
    SocialCardResultOut,
)
from src.server.social_cards.service.jobs.mutations import (
    update_job_title as update_social_card_job_title,
)

router = APIRouter(prefix="/api/social-cards", tags=["小红书图文卡"])


@router.post(
    "/jobs",
    response_model=SocialCardJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建小红书图文卡生成任务",
)
async def create_social_card_job(
    payload: SocialCardCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_job(db, payload, current_user)


@router.get(
    "/jobs",
    response_model=SocialCardJobListOut,
    summary="列出小红书图文卡生成历史任务",
)
async def list_social_card_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_daily_writer_job_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        source_daily_writer_job_id=source_daily_writer_job_id,
        current_user=current_user,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=SocialCardJobOut,
    summary="获取小红书图文卡任务状态",
)
async def get_social_card_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.patch(
    "/jobs/{job_id}",
    response_model=SocialCardJobOut,
    summary="更新小红书图文卡任务",
)
async def update_social_card_job(
    job_id: str,
    payload: SocialCardJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_social_card_job_title(db, job_id, payload, current_user)


@router.get(
    "/jobs/{job_id}/result",
    response_model=SocialCardResultOut,
    summary="获取小红书图文卡结果",
)
async def get_social_card_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get(
    "/jobs/{job_id}/images/{asset_key}",
    summary="获取小红书图文卡图片",
)
async def get_social_card_image(
    job_id: str,
    asset_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path, media_type = service.image_file(db, job_id, asset_key, current_user)
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.get(
    "/jobs/{job_id}/download",
    summary="下载小红书图文卡文件",
)
async def download_social_card_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = service.result_zip_file(db, job_id, current_user)
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}.zip")


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除小红书图文卡任务",
)
async def delete_social_card_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
