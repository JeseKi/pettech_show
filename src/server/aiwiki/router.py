# -*- coding: utf-8 -*-
"""AI Wiki public API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile, status
from sqlalchemy.orm import Session

from src.server.database import get_db
from . import service
from .schemas import AiwikiResultOut, JobListOut, JobOut

router = APIRouter(prefix="/api/aiwiki", tags=["AI Wiki"])


@router.post(
    "/jobs",
    response_model=JobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建 AI Wiki 生成任务",
)
async def create_aiwiki_job(
    files: Annotated[list[UploadFile], File(description="支持 .docx、.md、.txt")],
    db: Session = Depends(get_db),
):
    return await service.create_job(db, files)


@router.get(
    "/jobs",
    response_model=JobListOut,
    summary="列出 AI Wiki 历史任务",
)
async def list_aiwiki_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
):
    return service.list_jobs(db, limit=limit, offset=offset)


@router.get(
    "/jobs/{job_id}",
    response_model=JobOut,
    summary="获取 AI Wiki 任务状态",
)
async def get_aiwiki_job(
    job_id: str,
    db: Session = Depends(get_db),
):
    return service.get_job(db, job_id)


@router.get(
    "/jobs/{job_id}/result",
    response_model=AiwikiResultOut,
    summary="获取 AI Wiki 结构化结果",
)
async def get_aiwiki_result(
    job_id: str,
    db: Session = Depends(get_db),
):
    return service.get_result(db, job_id)
