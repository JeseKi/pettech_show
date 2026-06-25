# -*- coding: utf-8 -*-
"""Social card video job queries and artifact access."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ...dao import SocialCardVideoJobDAO
from ...parser import parse_social_card_video_result, resolve_social_card_video_asset_path
from ...schemas import SocialCardVideoJobListOut, SocialCardVideoJobOut, SocialCardVideoResultOut
from ..constants import RESULT_ZIP_NAME
from ..permissions import is_admin
from ..persistence import get_accessible_job
from ..serializers import job_out_from_model, job_summary_from_model
from .records import reconcile_orphaned_finished_job


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    source_social_card_job_id: str | None = None,
) -> SocialCardVideoJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = SocialCardVideoJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_social_card_job_id=source_social_card_job_id,
    )
    jobs = [reconcile_orphaned_finished_job(db, job) for job in jobs]
    return SocialCardVideoJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(
            owner_user_id=owner_filter,
            source_social_card_job_id=source_social_card_job_id,
        ),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> SocialCardVideoJobOut:
    job = get_accessible_job(db, job_id, current_user)
    job = reconcile_orphaned_finished_job(db, job)
    return job_out_from_model(job, SocialCardVideoJobDAO(db).owner_username(job.owner_user_id))


def get_result(db: Session, job_id: str, current_user: User) -> SocialCardVideoResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_social_card_video_result(
            job_id=job.id,
            source_social_card_job_id=job.source_social_card_job_id,
            workdir=Path(job.workdir),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    get_result(db, job_id, current_user)
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    zip_path = workdir / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in sorted((workdir / "source").rglob("*")):
            if path.is_file() and (
                path.name == "slideshow.mp4"
                or path.name == "video.md"
                or "verify_frames" in path.parts
            ):
                archive.write(path, arcname=path.relative_to(workdir).as_posix())
        config_path = workdir / "video-config.json"
        if config_path.is_file():
            archive.write(config_path, arcname="video-config.json")
    return zip_path


def video_file(
    db: Session,
    job_id: str,
    asset_key: str,
    current_user: User,
) -> tuple[Path, str]:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return resolve_social_card_video_asset_path(
            job_id=job.id,
            source_social_card_job_id=job.source_social_card_job_id,
            workdir=Path(job.workdir),
            asset_key=asset_key,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))

