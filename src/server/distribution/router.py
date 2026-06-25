# -*- coding: utf-8 -*-
"""Routes for uploading generated content to Info Distribution."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Security, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_admin
from src.server.auth.models import User
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from . import service
from .schemas import (
    DistributionDirectoryOut,
    DistributionUploadJobListOut,
    DistributionUploadPlanOut,
    DistributionUploadRequest,
    DistributionUploadResultOut,
)

router = APIRouter(prefix="/api/distribution", tags=["分发平台"])


@router.get(
    "/remote-directory",
    response_model=DistributionDirectoryOut,
    summary="读取分发平台项目、主题和账号目录",
)
async def get_remote_directory(
    _: User = Security(get_current_admin),
):
    accounts, project_themes = await service.fetch_remote_directory()
    return DistributionDirectoryOut(accounts=accounts, project_themes=project_themes)


@router.post(
    "/uploads/plan",
    response_model=DistributionUploadPlanOut,
    summary="预览分发上传计划",
)
async def preview_distribution_upload_plan(
    payload: DistributionUploadRequest,
    db: Session = Depends(get_db),
    _: User = Security(get_current_admin),
):
    accounts, project_themes = await service.fetch_remote_directory()

    def _build():
        return service.build_upload_plan(
            db,
            payload=payload,
            account_directory=accounts,
            project_theme_directory=project_themes,
        )

    return await run_in_thread(_build)


@router.post(
    "/uploads",
    response_model=DistributionUploadResultOut,
    status_code=status.HTTP_201_CREATED,
    summary="执行分发上传",
)
async def create_distribution_upload(
    payload: DistributionUploadRequest,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_admin),
):
    accounts, project_themes = await service.fetch_remote_directory()

    def _prepare():
        plan = service.build_upload_plan(
            db,
            payload=payload,
            account_directory=accounts,
            project_theme_directory=project_themes,
        )
        if plan["item_count"] < 1:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="没有可上传项")
        job = service.create_upload_job(
            db, payload=payload, plan=plan, current_user=current_user
        )
        return plan, job

    plan, job = await run_in_thread(_prepare)
    job, result = await service.upload_plan_to_remote(db, job=job, plan=plan)
    return DistributionUploadResultOut(
        job=service.job_summary(job),
        plan=plan,
        results=result.get("results") or [],
    )


@router.get(
    "/uploads",
    response_model=DistributionUploadJobListOut,
    summary="列出分发上传历史",
)
async def list_distribution_uploads(
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    offset: Annotated[int, Query(ge=0)] = 0,
    db: Session = Depends(get_db),
    _: User = Security(get_current_admin),
):
    return await run_in_thread(lambda: service.list_upload_jobs(db, limit=limit, offset=offset))


@router.get(
    "/assets/{asset_type}/{job_id}/{asset_key}",
    summary="读取签名生成图片",
)
async def get_distribution_asset(
    asset_type: str,
    job_id: str,
    asset_key: str,
    sig: Annotated[str, Query(min_length=1)],
    db: Session = Depends(get_db),
):
    path, media_type = await run_in_thread(
        lambda: service.resolve_signed_asset(
            db,
            asset_type=asset_type,
            job_id=job_id,
            asset_key=asset_key,
            signature=sig,
        )
    )
    return FileResponse(
        path,
        media_type=media_type,
        filename=path.name,
        headers={
            "Cache-Control": "public, max-age=86400",
            "Access-Control-Allow-Origin": "*",
        },
    )
