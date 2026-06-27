# -*- coding: utf-8 -*-
"""Upload preparation for Personal AI Wiki jobs."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status

from src.server.aiwiki.service.constants import ALLOWED_EXTENSIONS
from src.server.aiwiki.service.files import (
    build_file_preview,
    category_for_extension,
    convert_to_markdown,
    default_mime_type,
    safe_filename,
)
from src.server.config import global_config

from ..schemas import PersonalAiwikiOperation


async def validate_uploads(files: list[UploadFile]) -> list[dict[str, Any]]:
    total_size = 0
    validated_files: list[dict[str, Any]] = []
    max_bytes = global_config.aiwiki_max_upload_mb * 1024 * 1024
    for index, file in enumerate(files, start=1):
        original_name = safe_filename(file.filename or f"upload-{index}.txt")
        extension = Path(original_name).suffix.lower()
        if extension not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"不支持的文件类型：{extension or original_name}")
        content = await file.read()
        total_size += len(content)
        if total_size > max_bytes:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=f"上传总大小不能超过 {global_config.aiwiki_max_upload_mb}MB")
        validated_files.append(
            {
                "filename": original_name,
                "extension": extension,
                "content": content,
                "content_type": file.content_type,
            }
        )
    return validated_files


def write_uploads(
    workdir: Path,
    *,
    workspace_root: Path,
    raw_date: str,
    job_id: str,
    files: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    if not files:
        (workdir / "logs").mkdir(parents=True, exist_ok=True)
        return []
    uploads_dir = workdir / "uploads"
    raw_dir = workdir / "raw" / raw_date
    workspace_raw_dir = workspace_root / "raw" / raw_date
    (workdir / "logs").mkdir(parents=True, exist_ok=True)
    uploads_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    workspace_raw_dir.mkdir(parents=True, exist_ok=True)
    saved_files: list[dict[str, Any]] = []
    for index, item in enumerate(files, start=1):
        saved_files.append(
            write_one_upload(
                workdir,
                workspace_root=workspace_root,
                uploads_dir=uploads_dir,
                raw_dir=raw_dir,
                workspace_raw_dir=workspace_raw_dir,
                raw_date=raw_date,
                job_id=job_id,
                index=index,
                item=item,
            )
        )
    return saved_files


def write_one_upload(
    workdir: Path,
    *,
    workspace_root: Path,
    uploads_dir: Path,
    raw_dir: Path,
    workspace_raw_dir: Path,
    raw_date: str,
    job_id: str,
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
    workspace_raw_path = workspace_raw_dir / f"{job_id}_{index}_{Path(original_name).stem}.md"
    workspace_raw_path.write_text(raw_text, encoding="utf-8")
    preview = build_file_preview(original_name, content, extension)
    file_record = {
        "filename": original_name,
        "size_bytes": len(content),
        "upload_path": upload_path.relative_to(workdir).as_posix(),
        "raw_path": raw_path.relative_to(workdir).as_posix(),
        "workspace_raw_path": workspace_raw_path.relative_to(workspace_root).as_posix(),
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


def write_text_source(
    workdir: Path,
    *,
    workspace_root: Path,
    raw_date: str,
    job_id: str,
    text: str,
    title: str | None,
) -> dict[str, Any]:
    input_dir = workdir / "inputs"
    raw_dir = workdir / "raw" / raw_date
    workspace_raw_dir = workspace_root / "raw" / raw_date
    input_dir.mkdir(parents=True, exist_ok=True)
    raw_dir.mkdir(parents=True, exist_ok=True)
    workspace_raw_dir.mkdir(parents=True, exist_ok=True)
    filename = safe_filename(f"{title or '输入文本'}.md")
    content = text.strip() + "\n"
    upload_path = input_dir / filename
    upload_path.write_text(content, encoding="utf-8")
    raw_base = safe_filename(f"{raw_date}_text_{Path(filename).stem}")
    raw_path = raw_dir / f"{raw_base}.md"
    raw_path.write_text(content, encoding="utf-8")
    workspace_raw_path = workspace_raw_dir / f"{job_id}_text_{Path(filename).stem}.md"
    workspace_raw_path.write_text(content, encoding="utf-8")
    return {
        "filename": filename,
        "size_bytes": len(content.encode("utf-8")),
        "upload_path": upload_path.relative_to(workdir).as_posix(),
        "raw_path": raw_path.relative_to(workdir).as_posix(),
        "workspace_raw_path": workspace_raw_path.relative_to(workspace_root).as_posix(),
        "extension": ".md",
        "mime_type": "text/markdown",
        "category": "graphic_text",
        "preview_status": "ready",
        "preview": {
            "kind": "text",
            "format": "markdown",
            "text": content[:200_000],
            "truncated": len(content) > 200_000,
            "character_count": len(content),
        },
    }


def build_manifest(
    *,
    job_id: str,
    owner_user_id: int,
    operation: PersonalAiwikiOperation,
    workdir: Path,
    workspace_root: Path,
    input_text: str | None,
    title: str | None,
    description: str | None,
    files: list[dict[str, Any]],
    created_at: datetime,
    raw_date: str,
) -> dict[str, Any]:
    return {
        "id": job_id,
        "owner_user_id": owner_user_id,
        "operation": operation,
        "title": title or default_job_title(operation, files, input_text, job_id),
        "description": description,
        "status": "queued",
        "message": "任务已进入队列",
        "created_at": created_at.isoformat(),
        "started_at": None,
        "finished_at": None,
        "workdir": workdir.as_posix(),
        "workspace_dir": workspace_root.as_posix(),
        "input_text": input_text,
        "files": files,
        "raw_date": raw_date,
        "summary": None,
        "answer_markdown": None,
    }


def default_job_title(
    operation: PersonalAiwikiOperation,
    files: list[dict[str, Any]],
    input_text: str | None,
    fallback_id: str,
) -> str:
    first_file = files[0].get("filename") if files else None
    if isinstance(first_file, str) and first_file.strip():
        return f"{first_file.strip()} 等 {len(files)} 个来源" if len(files) > 1 else first_file.strip()
    first_line = (input_text or "").strip().splitlines()[0:1]
    return (first_line[0][:80] if first_line else "") or fallback_id
