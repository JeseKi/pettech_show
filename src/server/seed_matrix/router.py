# -*- coding: utf-8 -*-
"""Seed matrix public API routes."""

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
    SeedMatrixCreate,
    SeedMatrixJobListOut,
    SeedMatrixJobOut,
    SeedMatrixResultOut,
)

router = APIRouter(prefix="/api/seed-matrices", tags=["选题矩阵"])


@router.post(
    "",
    response_model=SeedMatrixJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建选题矩阵生成任务",
)
async def create_seed_matrix_job(
    payload: SeedMatrixCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_job(db, payload, current_user)


@router.get(
    "",
    response_model=SeedMatrixJobListOut,
    summary="列出选题矩阵历史任务",
)
async def list_seed_matrix_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    source_aiwiki_job_id: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        source_aiwiki_job_id=source_aiwiki_job_id,
        current_user=current_user,
    )


@router.get(
    "/{job_id}",
    response_model=SeedMatrixJobOut,
    summary="获取选题矩阵任务状态",
)
async def get_seed_matrix_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.get(
    "/{job_id}/result",
    response_model=SeedMatrixResultOut,
    summary="获取选题矩阵结构化结果",
)
async def get_seed_matrix_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get(
    "/{job_id}/download",
    summary="下载选题矩阵 CSV",
)
async def download_seed_matrix_csv(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = service.result_csv_file(db, job_id, current_user)
    return FileResponse(
        path,
        media_type="text/csv; charset=utf-8",
        filename=f"{job_id}.csv",
    )


@router.delete(
    "/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除选题矩阵任务",
)
async def delete_seed_matrix_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
