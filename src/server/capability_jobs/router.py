# -*- coding: utf-8 -*-
"""Generic capability job API routes."""

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
    CapabilityConfigOut,
    CapabilityCreate,
    CapabilityJobListOut,
    CapabilityJobOut,
    CapabilityResultOut,
)

router = APIRouter(prefix="/api/capability-jobs", tags=["内容能力"])


@router.get("/capabilities", response_model=list[CapabilityConfigOut], summary="列出内容能力入口")
async def list_capabilities():
    return service.get_capabilities()


@router.post("", response_model=CapabilityJobOut, status_code=status.HTTP_202_ACCEPTED, summary="创建内容能力任务")
async def create_capability_job(
    payload: CapabilityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.create_job(db, payload, current_user)


@router.get("", response_model=CapabilityJobListOut, summary="列出内容能力历史任务")
async def list_capability_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    capability_key: str | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        capability_key=capability_key,
        current_user=current_user,
    )


@router.get("/{job_id}", response_model=CapabilityJobOut, summary="获取内容能力任务状态")
async def get_capability_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.get("/{job_id}/result", response_model=CapabilityResultOut, summary="获取内容能力任务结果")
async def get_capability_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get("/{job_id}/download", summary="下载内容能力任务结果")
async def download_capability_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    path = service.result_zip_file(db, job_id, current_user)
    return FileResponse(path, media_type="application/zip", filename=f"{job_id}.zip")


@router.delete("/{job_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除内容能力任务")
async def delete_capability_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
