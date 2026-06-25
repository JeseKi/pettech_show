# -*- coding: utf-8 -*-
"""Daily writer public API routes."""

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
    DailyWriterCreate,
    DailyWriterJobListOut,
    DailyWriterJobOut,
    DailyWriterJobUpdate,
    DailyWriterResultOut,
)
from .service.jobs.mutations import update_job_title as update_daily_writer_job_title

router = APIRouter(prefix="/api/daily-writer", tags=["生成长文"])


@router.post(
    "/jobs",
    response_model=DailyWriterJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建长文生成任务",
)
async def create_daily_writer_job(
    payload: DailyWriterCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_job(db, payload, current_user)


@router.get(
    "/jobs",
    response_model=DailyWriterJobListOut,
    summary="列出长文生成历史任务",
)
async def list_daily_writer_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_seed_matrix_job_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
        current_user=current_user,
    )


@router.get(
    "/jobs/{job_id}",
    response_model=DailyWriterJobOut,
    summary="获取长文生成任务状态",
)
async def get_daily_writer_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.patch(
    "/jobs/{job_id}",
    response_model=DailyWriterJobOut,
    summary="更新长文生成任务",
)
async def update_daily_writer_job(
    job_id: str,
    payload: DailyWriterJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return update_daily_writer_job_title(db, job_id, payload, current_user)


@router.get(
    "/jobs/{job_id}/result",
    response_model=DailyWriterResultOut,
    summary="获取长文结果",
)
async def get_daily_writer_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get(
    "/jobs/{job_id}/download",
    summary="下载长文文件",
)
async def download_daily_writer_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = service.result_zip_file(db, job_id, current_user)
    return FileResponse(
        path,
        media_type="application/zip",
        filename=f"{job_id}.zip",
    )


@router.get(
    "/jobs/{job_id}/artwork/{asset_key}",
    summary="获取长文封面或插图",
)
async def get_daily_writer_artwork(
    job_id: str,
    asset_key: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path, media_type = service.artwork_file(db, job_id, asset_key, current_user)
    return FileResponse(path, media_type=media_type, filename=path.name)


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除长文生成任务",
)
async def delete_daily_writer_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
