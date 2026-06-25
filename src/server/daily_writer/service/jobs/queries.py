# -*- coding: utf-8 -*-
"""Daily writer job queries and artifact access."""

from __future__ import annotations

import json
import zipfile
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ...dao import DailyWriterJobDAO
from ...parser import (
    parse_daily_writer_result,
    resolve_artwork_asset_path,
    resolve_result_paths,
)
from ...schemas import DailyWriterJobListOut, DailyWriterJobOut, DailyWriterResultOut
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
    source_seed_matrix_job_id: str | None = None,
) -> DailyWriterJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = DailyWriterJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
    )
    jobs = [reconcile_orphaned_finished_job(db, job) for job in jobs]
    return DailyWriterJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(
            owner_user_id=owner_filter,
            source_seed_matrix_job_id=source_seed_matrix_job_id,
        ),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> DailyWriterJobOut:
    job = get_accessible_job(db, job_id, current_user)
    job = reconcile_orphaned_finished_job(db, job)
    return job_out_from_model(job, DailyWriterJobDAO(db).owner_username(job.owner_user_id))


def get_result(
    db: Session, job_id: str, current_user: User
) -> DailyWriterResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=Path(job.workdir),
            article_path=job.article_path,
            metadata_path=job.metadata_path,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    result = get_result(db, job_id, current_user)
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    zip_path = workdir / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(workdir / result.article_path, arcname="main.md")
        archive.write(workdir / result.metadata_path, arcname="metadata.json")
        _write_optional_tree(archive, workdir, Path(result.metadata_path).parent / "variants")
        _write_optional_tree(archive, workdir, Path(result.metadata_path).parent / "artwork")
    return zip_path


def artwork_file(
    db: Session,
    job_id: str,
    asset_key: str,
    current_user: User,
) -> tuple[Path, str]:
    job = get_accessible_job(db, job_id, current_user)
    if job.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        _, metadata_path = resolve_result_paths(
            Path(job.workdir),
            article_path=job.article_path,
            metadata_path=job.metadata_path,
        )
        return resolve_artwork_asset_path(
            job_id=job.id,
            workdir=Path(job.workdir),
            article_dir=metadata_path.parent,
            asset_key=asset_key,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def _write_optional_tree(
    archive: zipfile.ZipFile, workdir: Path, relative_root: Path
) -> None:
    absolute_root = workdir / relative_root
    if not absolute_root.is_dir():
        return
    for path in sorted(absolute_root.rglob("*")):
        if path.is_file():
            archive.write(path, arcname=path.relative_to(workdir / relative_root.parent).as_posix())
