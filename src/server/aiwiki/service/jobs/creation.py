# -*- coding: utf-8 -*-
"""AI Wiki job creation."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.config import global_config

from ...dao import AiwikiJobDAO
from ...schemas import JobOut
from ..constants import ALLOWED_EXTENSIONS
from ..files import (
    build_file_preview,
    category_for_extension,
    convert_to_markdown,
    default_mime_type,
    safe_filename,
)
from ..persistence import (
    build_session_factory,
    job_workdir,
    new_job_id,
    upsert_job_from_manifest,
    write_manifest,
)
from ..progress import initial_progress, write_progress
from ..queue_state import get_queue
from ..serializers import job_out_from_manifest
from .runner import run_job


async def create_job(
    db: Session,
    files: list[UploadFile],
    current_user: User,
    *,
    generate_search_assets: bool = True,
) -> JobOut:
    if not files:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请至少上传一个文件",
        )
    validated_files = await _validate_uploads(files)
    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    raw_date = now.strftime("%y%m%d")
    saved_files = _write_uploads(workdir, raw_date=raw_date, files=validated_files)
    manifest = _build_manifest(
        job_id=job_id,
        owner_user_id=current_user.id,
        workdir=workdir,
        raw_date=raw_date,
        files=saved_files,
        created_at=now,
        generate_search_assets=generate_search_assets,
    )
    write_progress(workdir, initial_progress())
    write_manifest(workdir, manifest)
    _write_audit_logs(db, current_user=current_user, job_id=job_id, files=saved_files)
    upsert_job_from_manifest(db, workdir, manifest)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: run_job(job_id, workdir, session_factory))
    return job_out_from_manifest(workdir, manifest, current_user.username)


async def _validate_uploads(files: list[UploadFile]) -> list[dict[str, Any]]:
    total_size = 0
    validated_files: list[dict[str, Any]] = []
    max_bytes = global_config.aiwiki_max_upload_mb * 1024 * 1024
    for index, file in enumerate(files, start=1):
        original_name = safe_filename(file.filename or f"upload-{index}.txt")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"不支持的文件类型：{extension or original_name}",
            )
        content = await file.read()
        total_size += len(content)
        if total_size > max_bytes:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"上传总大小不能超过 {global_config.aiwiki_max_upload_mb}MB",
            )
        validated_files.append(
            {
                "filename": original_name,
                "extension": extension,
                "content": content,
                "content_type": file.content_type,
            }
        )
    return validated_files


def _write_uploads(
    workdir: Path, *, raw_date: str, files: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    uploads_dir = workdir / "uploads"
    raw_dir = workdir / "raw" / raw_date
    (workdir / "logs").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[dict[str, Any]] = []
    for index, item in enumerate(files, start=1):
        file_record = _write_one_upload(
            workdir,
            uploads_dir=uploads_dir,
            raw_dir=raw_dir,
            raw_date=raw_date,
            index=index,
            item=item,
        )
        saved_files.append(file_record)
    return saved_files


def _write_one_upload(
    workdir: Path,
    *,
    uploads_dir: Path,
    raw_dir: Path,
    raw_date: str,
    index: int,
    item: dict[str, Any],
) -> dict[str, Any]:
    original_name = str(item["filename"])
    extension = str(item["extension"])
    content = item["content"]
    upload_path = uploads_dir / original_name
    upload_path.write_bytes(content)
    raw_text = convert_to_markdown(upload_path, content, extension)
    raw_base = safe_filename(f"{raw_date}_{index}_{Path(original_name).stem}")
    raw_path = raw_dir / f"{raw_base}.md"
    raw_path.write_text(raw_text, encoding="utf-8")
    preview = build_file_preview(original_name, content, extension)
    file_record = {
        "filename": original_name,
        "size_bytes": len(content),
        "upload_path": upload_path.relative_to(workdir).as_posix(),
        "raw_path": raw_path.relative_to(workdir).as_posix(),
        "extension": extension,
        "mime_type": item["content_type"] or default_mime_type(extension),
        "category": category_for_extension(extension),
        "preview_status": "ready",
        "preview": preview,
    }
    if extension == ".pdf":
        raw_source_path = raw_dir / f"{raw_base}.pdf"
        raw_source_path.write_bytes(content)
        file_record["raw_source_path"] = raw_source_path.relative_to(workdir).as_posix()
    return file_record


def _build_manifest(
    *,
    job_id: str,
    owner_user_id: int | None,
    workdir: Path,
    raw_date: str,
    files: list[dict[str, Any]],
    created_at: datetime,
    generate_search_assets: bool,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "owner_user_id": owner_user_id,
        "title": _default_job_title(files, job_id),
        "description": None,
        "status": "queued",
        "message": "任务已进入队列",
        "created_at": created_at.isoformat(),
        "started_at": None,
        "finished_at": None,
        "workdir": workdir.as_posix(),
        "files": files,
        "raw_date": raw_date,
        "options": {"generate_search_assets": generate_search_assets},
    }


def _write_audit_logs(
    db: Session, *, current_user: User, job_id: str, files: list[dict[str, Any]]
) -> None:
    dao = AiwikiJobDAO(db)
    for item in files:
        dao.append_audit_log(
            actor_user_id=current_user.id,
            actor_username=current_user.username,
            action="upload",
            job_id=job_id,
            target_filename=str(item["filename"]),
            message=f"{current_user.username} 上传了 {item['filename']}",
            metadata={
                "size_bytes": item["size_bytes"],
                "extension": item["extension"],
                "category": item["category"],
            },
        )
    dao.append_audit_log(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="execute",
        job_id=job_id,
        target_filename=", ".join(str(item["filename"]) for item in files),
        message=f"{current_user.username} 执行了知识库生成任务",
        metadata={"job_id": job_id, "filenames": [item["filename"] for item in files]},
    )


def _default_job_title(files: list[dict[str, Any]], fallback_id: str) -> str:
    first = files[0].get("filename") if files else None
    if isinstance(first, str) and first.strip():
        return f"{first.strip()} 等 {len(files)} 个文件" if len(files) > 1 else first.strip()
    return fallback_id
