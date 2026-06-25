# -*- coding: utf-8 -*-
"""Personal AI Wiki API routes."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Query, UploadFile, status
from fastapi import Response
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.database import get_db

from . import service
from .schemas import (
    PersonalAiwikiJobListOut,
    PersonalAiwikiJobOut,
    PersonalAiwikiJobUpdate,
    PersonalAiwikiOperation,
    PersonalAiwikiEntryPageOut,
    PersonalAiwikiResultOut,
)

router = APIRouter(prefix="/api/personal-aiwiki", tags=["个人 AI Wiki"])


@router.post(
    "/jobs",
    response_model=PersonalAiwikiJobOut,
    status_code=status.HTTP_202_ACCEPTED,
    summary="创建个人 AI Wiki 任务",
)
async def create_personal_aiwiki_job(
    operation: Annotated[PersonalAiwikiOperation, Form(description="任务类型：ingest")] = "ingest",
    input_text: Annotated[str | None, Form(description="导入文本")] = None,
    title: Annotated[str | None, Form(description="任务标题")] = None,
    description: Annotated[str | None, Form(description="任务描述")] = None,
    files: Annotated[
        list[UploadFile] | None,
        File(description="支持 Markdown、TXT、XLSX、CSV、PDF"),
    ] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await service.create_job(
        db,
        files=files,
        current_user=current_user,
        operation=operation,
        input_text=input_text,
        title=title,
        description=description,
    )


@router.get(
    "/jobs",
    response_model=PersonalAiwikiJobListOut,
    summary="列出个人 AI Wiki 历史任务",
)
async def list_personal_aiwiki_jobs(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: Annotated[str | None, Query(pattern="^(queued|running|completed|failed)$")] = None,
    operation: Annotated[str | None, Query(pattern="^(ingest|query|lint)$")] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.list_jobs(
        db,
        limit=limit,
        offset=offset,
        status=status,
        operation=operation,
        current_user=current_user,
    )


@router.get(
    "/workspace",
    response_model=PersonalAiwikiResultOut,
    summary="获取当前用户个人 AI Wiki workspace",
)
async def get_personal_aiwiki_workspace(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_workspace(db, current_user)


@router.get(
    "/entries/{page:path}",
    response_model=PersonalAiwikiEntryPageOut,
    summary="读取当前用户个人 AI Wiki 词条",
)
async def get_personal_aiwiki_entry_page(
    page: str,
    current_user: User = Depends(get_current_user),
):
    return service.get_entry_page(current_user, page)


@router.get(
    "/jobs/{job_id}",
    response_model=PersonalAiwikiJobOut,
    summary="获取个人 AI Wiki 任务状态",
)
async def get_personal_aiwiki_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_job(db, job_id, current_user)


@router.patch(
    "/jobs/{job_id}",
    response_model=PersonalAiwikiJobOut,
    summary="更新个人 AI Wiki 任务元数据",
)
async def update_personal_aiwiki_job(
    job_id: str,
    payload: PersonalAiwikiJobUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.update_job(db, job_id, payload, current_user)


@router.get(
    "/jobs/{job_id}/result",
    response_model=PersonalAiwikiResultOut,
    summary="获取个人 AI Wiki 任务结果",
)
async def get_personal_aiwiki_result(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_result(db, job_id, current_user)


@router.get(
    "/jobs/{job_id}/files/{file_index}",
    summary="获取个人 AI Wiki 上传原文件",
)
async def get_personal_aiwiki_file(
    job_id: str,
    file_index: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return service.get_file(db, job_id, file_index, current_user)


@router.delete(
    "/jobs/{job_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除个人 AI Wiki 任务",
)
async def delete_personal_aiwiki_job(
    job_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    service.delete_job(db, job_id, current_user)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
