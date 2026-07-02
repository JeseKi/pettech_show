# -*- coding: utf-8 -*-
"""AI Wiki job queries and result access."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ...dao import AiwikiJobDAO
from ...parser import parse_aiwiki_result
from ...schemas import AiwikiResultOut, AiwikiStatsOut, JobListOut, JobOut
from ..files import category_for_extension
from ..persistence import existing_job_workdir, read_manifest, upsert_job_from_manifest
from ..serializers import (
    job_out_from_manifest,
    job_summary_from_model,
    parse_uploaded_files,
)
from .access import can_access_job, default_admin_user_id, is_admin


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    status: str | None = None,
) -> JobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    dao = AiwikiJobDAO(db)
    owner_filter = current_user.id
    items = [
        job_summary_from_model(job, dao.owner_username(job.owner_user_id))
        for job in dao.list(
            limit=normalized_limit,
            offset=normalized_offset,
            owner_user_id=owner_filter,
            status=status,
        )
    ]
    stats = build_stats(
        jobs=dao.list_for_stats(owner_user_id=owner_filter, status=status),
        display_count=sum(len(item.files) for item in items),
    )
    return JobListOut(
        items=items,
        total=dao.count(owner_user_id=owner_filter, status=status),
        limit=normalized_limit,
        offset=normalized_offset,
        stats=stats,
    )


def get_job(db: Session, job_id: str, current_user: User) -> JobOut:
    workdir = existing_job_workdir(job_id, db)
    manifest = read_manifest(workdir)
    dao = AiwikiJobDAO(db)
    job = dao.get(job_id)
    if job is None:
        if not is_admin(current_user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        manifest.setdefault("owner_user_id", default_admin_user_id(db))
        upsert_job_from_manifest(db, workdir, manifest)
        job = dao.get(job_id)
    if job is None or job.deleted_at is not None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    manifest["owner_user_id"] = job.owner_user_id
    manifest["title"] = job.title or manifest.get("title")
    manifest["description"] = job.description
    return job_out_from_manifest(workdir, manifest, dao.owner_username(job.owner_user_id))


def get_result(db: Session, job_id: str, current_user: User) -> AiwikiResultOut:
    workdir = existing_job_workdir(job_id, db)
    job = AiwikiJobDAO(db).get(job_id)
    if job is None or job.deleted_at is not None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    manifest = read_manifest(workdir)
    if manifest.get("status") != "completed":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务尚未完成",
        )
    result = parse_aiwiki_result(job_id, workdir)
    if not result.materials and not result.wiki_entries:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="任务未生成可展示结果",
        )
    return result


def get_file(db: Session, job_id: str, file_index: int, current_user: User) -> FileResponse:
    workdir = existing_job_workdir(job_id, db)
    job = AiwikiJobDAO(db).get(job_id)
    if job is None or job.deleted_at is not None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    files = parse_manifest_files(workdir)
    if file_index < 0 or file_index >= len(files) or not isinstance(files[file_index], dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    file_info = files[file_index]
    path = _resolve_upload_path(workdir, file_info)
    return FileResponse(
        path,
        media_type=str(file_info.get("mime_type") or "application/octet-stream"),
        filename=str(file_info.get("filename") or path.name),
    )


def parse_manifest_files(workdir: Path) -> list[dict[str, Any]]:
    try:
        manifest = read_manifest(workdir)
    except Exception:
        return []
    files = manifest.get("files")
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def build_stats(*, jobs: list[Any], display_count: int) -> AiwikiStatsOut:
    graphic_text_count = 0
    document_count = 0
    total_count = 0
    for job in jobs:
        for file in parse_uploaded_files(getattr(job, "files_json", "[]")):
            total_count += 1
            category = file.category or category_for_extension(
                file.extension or Path(file.filename).suffix.lower()
            )
            if category == "graphic_text":
                graphic_text_count += 1
            else:
                document_count += 1
    return AiwikiStatsOut(
        graphic_text_count=graphic_text_count,
        document_count=document_count,
        display_count=display_count,
        total_count=total_count,
    )


def _resolve_upload_path(workdir: Path, file_info: dict[str, Any]) -> Path:
    upload_path = file_info.get("upload_path")
    if not isinstance(upload_path, str) or not upload_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    path = (workdir / upload_path).resolve()
    try:
        path.relative_to(workdir.resolve())
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径非法") from exc
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return path
