# -*- coding: utf-8 -*-
"""Public AI Wiki job service functions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any, Literal

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.config import global_config
from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ..dao import AiwikiJobDAO
from ..parser import parse_aiwiki_result
from ..models import AiwikiAuditLog
from ..schemas import (
    AiwikiAuditLogListOut,
    AiwikiAuditLogOut,
    AiwikiResultOut,
    AiwikiStatsOut,
    JobListOut,
    JobOut,
    JobUpdate,
)
from .constants import ALLOWED_EXTENSIONS
from .files import (
    build_file_preview,
    category_for_extension,
    convert_to_markdown,
    default_mime_type,
    safe_filename,
)
from .logs import append_log
from .checks import python_args, run_check_command
from .opencode import (
    prepare_opencode_config,
    prepare_skills,
    run_opencode,
    run_repair_opencode,
)
from .persistence import (
    build_session_factory,
    existing_job_workdir,
    job_workdir,
    new_job_id,
    manifest_db_payload,
    read_manifest,
    update_manifest,
    upsert_job_from_manifest,
    write_manifest,
)
from .progress import (
    initial_progress,
    mark_progress_failure,
    mark_progress_running,
    progress_marked_complete,
    write_progress,
)
from .queue_state import get_queue
from .serializers import job_out_from_manifest, job_summary_from_model, parse_uploaded_files


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

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    uploads_dir = workdir / "uploads"
    raw_date = now.strftime("%y%m%d")
    raw_dir = workdir / "raw" / raw_date
    logs_dir = workdir / "logs"
    uploads_dir.mkdir(parents=True, exist_ok=False)
    raw_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

    saved_files: list[dict[str, Any]] = []
    for index, item in enumerate(validated_files, start=1):
        original_name = str(item["filename"])
        extension = str(item["extension"])
        content = item["content"]
        upload_path = uploads_dir / original_name
        upload_path.write_bytes(content)
        raw_text = convert_to_markdown(upload_path, content, extension)
        raw_base = safe_filename(f"{raw_date}_{index}_{Path(original_name).stem}")
        raw_path = raw_dir / f"{raw_base}.md"
        raw_path.write_text(raw_text, encoding="utf-8")
        raw_source_path: Path | None = None
        if extension == ".pdf":
            raw_source_path = raw_dir / f"{raw_base}.pdf"
            raw_source_path.write_bytes(content)
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
        if raw_source_path is not None:
            file_record["raw_source_path"] = raw_source_path.relative_to(workdir).as_posix()
        saved_files.append(file_record)

    manifest = {
        "id": job_id,
        "owner_user_id": current_user.id,
        "title": _default_job_title(saved_files, job_id),
        "description": None,
        "status": "queued",
        "message": "任务已进入队列",
        "created_at": now.isoformat(),
        "started_at": None,
        "finished_at": None,
        "workdir": workdir.as_posix(),
        "files": saved_files,
        "raw_date": raw_date,
        "options": {
            "generate_search_assets": generate_search_assets,
        },
    }
    write_progress(workdir, initial_progress())
    write_manifest(workdir, manifest)
    dao = AiwikiJobDAO(db)
    for item in saved_files:
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
        target_filename=", ".join(str(item["filename"]) for item in saved_files),
        message=f"{current_user.username} 执行了知识库生成任务",
        metadata={
            "job_id": job_id,
            "filenames": [item["filename"] for item in saved_files],
        },
    )
    upsert_job_from_manifest(db, workdir, manifest)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: _run_job(job_id, workdir, session_factory))
    return job_out_from_manifest(workdir, manifest, current_user.username)


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
        if not _is_admin(current_user):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
        manifest.setdefault("owner_user_id", _default_admin_user_id(db))
        upsert_job_from_manifest(db, workdir, manifest)
        job = dao.get(job_id)
    if job is None or not _can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    manifest["owner_user_id"] = job.owner_user_id
    manifest["title"] = job.title or manifest.get("title")
    manifest["description"] = job.description
    return job_out_from_manifest(workdir, manifest, dao.owner_username(job.owner_user_id))


def update_job(
    db: Session, job_id: str, payload: JobUpdate, current_user: User
) -> JobOut:
    workdir = existing_job_workdir(job_id, db)
    dao = AiwikiJobDAO(db)
    job = dao.get(job_id)
    if job is None or not _can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")

    fields = payload.model_dump(exclude_unset=True)
    normalized: dict[str, Any] = {}
    if "title" in fields:
        normalized["title"] = _normalize_optional_text(fields.get("title"))
    if "description" in fields:
        normalized["description"] = _normalize_optional_text(fields.get("description"))

    manifest = read_manifest(workdir)
    manifest.update(normalized)
    write_manifest(workdir, manifest)
    dao.append_audit_log(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="update",
        job_id=job.id,
        target_filename=", ".join(
            item.get("filename", "")
            for item in parse_manifest_files(workdir)
            if isinstance(item, dict)
        ) or job.id,
        message=f"{current_user.username} 更新了知识库任务 {job.id}",
        metadata={
            "job_id": job.id,
            "fields": sorted(normalized.keys()),
        },
    )
    updated = dao.upsert_from_payload(manifest_db_payload(workdir, manifest))
    manifest["owner_user_id"] = updated.owner_user_id
    manifest["title"] = updated.title or manifest.get("title")
    manifest["description"] = updated.description
    return job_out_from_manifest(
        workdir, manifest, dao.owner_username(updated.owner_user_id)
    )


def get_result(db: Session, job_id: str, current_user: User) -> AiwikiResultOut:
    workdir = existing_job_workdir(job_id, db)
    job = AiwikiJobDAO(db).get(job_id)
    if job is None or not _can_access_job(current_user, job.owner_user_id):
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
    if job is None or not _can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    manifest = read_manifest(workdir)
    manifest_files = manifest.get("files")
    files: list[dict[str, Any]] = [
        item for item in manifest_files if isinstance(item, dict)
    ] if isinstance(manifest_files, list) else []
    if file_index < 0 or file_index >= len(files) or not isinstance(files[file_index], dict):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    file_info = files[file_index]
    upload_path = file_info.get("upload_path")
    if not isinstance(upload_path, str) or not upload_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    path = (workdir / upload_path).resolve()
    try:
        path.relative_to(workdir.resolve())
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="文件路径非法")
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="文件不存在")
    return FileResponse(
        path,
        media_type=str(file_info.get("mime_type") or "application/octet-stream"),
        filename=str(file_info.get("filename") or path.name),
    )


def list_audit_logs(
    db: Session,
    *,
    current_user: User,
    scope: str,
    limit: int,
    offset: int,
) -> AiwikiAuditLogListOut:
    normalized_scope: Literal["mine", "all"] = "all" if scope == "all" else "mine"
    if normalized_scope == "all" and not _is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以查看全部操作日志")
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    actor_filter = None if normalized_scope == "all" else current_user.id
    dao = AiwikiJobDAO(db)
    return AiwikiAuditLogListOut(
        items=[audit_log_out(log) for log in dao.list_audit_logs(
            limit=normalized_limit,
            offset=normalized_offset,
            actor_user_id=actor_filter,
        )],
        total=dao.count_audit_logs(actor_user_id=actor_filter),
        limit=normalized_limit,
        offset=normalized_offset,
        scope=normalized_scope,
    )


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    workdir = existing_job_workdir(job_id, db)
    dao = AiwikiJobDAO(db)
    job = dao.get(job_id)
    if job is None or not _can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务正在执行，完成或失败后才能删除",
        )
    dao.append_audit_log(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="delete",
        job_id=job.id,
        target_filename=", ".join(
            item.get("filename", "")
            for item in parse_manifest_files(workdir)
            if isinstance(item, dict)
        ) or job.id,
        message=f"{current_user.username} 删除了知识库任务 {job.id}",
        metadata={"job_id": job.id},
    )
    _delete_child_seed_matrices(db, job_id)
    dao.delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def _delete_child_seed_matrices(db: Session, source_aiwiki_job_id: str) -> None:
    from src.server.seed_matrix.dao import SeedMatrixJobDAO

    dao = SeedMatrixJobDAO(db)
    children = dao.list(
        limit=1000,
        offset=0,
        source_aiwiki_job_id=source_aiwiki_job_id,
    )
    active = [job for job in children if job.status in {"queued", "running"}]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该 AI Wiki 仍有关联的选题矩阵任务正在执行",
        )
    for child in children:
        from src.server.daily_writer.service import delete_child_jobs_for_seed_matrix

        delete_child_jobs_for_seed_matrix(db, child.id)
        child_workdir = Path(child.workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)


def parse_manifest_files(workdir: Path) -> list[dict[str, Any]]:
    try:
        manifest = read_manifest(workdir)
    except Exception:
        return []
    files = manifest.get("files")
    return [item for item in files if isinstance(item, dict)] if isinstance(files, list) else []


def audit_log_out(log: AiwikiAuditLog) -> AiwikiAuditLogOut:
    from .serializers import parse_json_dict

    return AiwikiAuditLogOut(
        id=log.id,
        actor_user_id=log.actor_user_id,
        actor_username=log.actor_username,
        action=log.action,
        job_id=log.job_id,
        target_filename=log.target_filename,
        message=log.message,
        metadata=parse_json_dict(log.metadata_json),
        created_at=log.created_at,
    )


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


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return

    dao = AiwikiJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_aiwiki/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 AI Wiki manifest {}: {}", manifest_path, exc)
            continue

        status_value = str(manifest.get("status") or "")
        if status_value in {"queued", "running"}:
            manifest = _recover_interrupted_manifest(workdir, manifest)
            write_manifest(workdir, manifest)

        if dao.get(str(manifest.get("id"))) is None:
            manifest.setdefault("owner_user_id", _default_admin_user_id(db))
            dao.upsert_from_payload(manifest_db_payload(workdir, manifest))
        elif status_value in {"queued", "running"}:
            dao.upsert_from_payload(manifest_db_payload(workdir, manifest))


def _run_job(
    job_id: str, workdir: Path, session_factory: sessionmaker[Session]
) -> None:
    started_at = datetime.now(timezone.utc)
    update_manifest(
        workdir,
        status="running",
        message="OpenCode 正在生成生文材料和 AI Wiki",
        started_at=started_at.isoformat(),
        session_factory=session_factory,
    )
    try:
        prepare_skills(workdir)
        prepare_opencode_config(workdir)
        _run_opencode_with_json_check(
            workdir,
            generate_search_assets=_generate_search_assets(read_manifest(workdir)),
        )
        result = parse_aiwiki_result(job_id, workdir)
        if not result.materials and not result.wiki_entries:
            raise RuntimeError("OpenCode 未生成 material 或 wiki 结果")
        update_manifest(
            workdir,
            status="completed",
            message="AI Wiki 生成完成",
            finished_at=datetime.now(timezone.utc).isoformat(),
            summary=result.summary,
            session_factory=session_factory,
        )
    except Exception as exc:
        logger.exception("AI Wiki job failed: {}", job_id)
        append_log(workdir, f"ERROR: {exc}")
        mark_progress_failure(workdir, str(exc))
        update_manifest(
            workdir,
            status="failed",
            message=str(exc),
            finished_at=datetime.now(timezone.utc).isoformat(),
            session_factory=session_factory,
        )


def _recover_interrupted_manifest(
    workdir: Path, manifest: dict[str, Any]
) -> dict[str, Any]:
    recovered = dict(manifest)
    if progress_marked_complete(workdir):
        try:
            result = parse_aiwiki_result(str(recovered.get("id") or workdir.name), workdir)
            if result.materials or result.wiki_entries:
                recovered.update(
                    {
                        "status": "completed",
                        "message": "AI Wiki 生成完成（服务启动时恢复）",
                        "finished_at": recovered.get("finished_at")
                        or datetime.now(timezone.utc).isoformat(),
                        "summary": result.summary,
                    }
                )
                return recovered
        except Exception as exc:
            logger.warning("恢复 AI Wiki 完成任务失败 {}: {}", workdir, exc)

    recovered.update(
        {
            "status": "failed",
            "message": "任务因服务重启中断，请重新提交",
            "finished_at": recovered.get("finished_at")
            or datetime.now(timezone.utc).isoformat(),
        }
    )
    return recovered


def _run_opencode_with_json_check(workdir: Path, *, generate_search_assets: bool) -> None:
    run_opencode(workdir, generate_search_assets=generate_search_assets)
    if not progress_marked_complete(workdir):
        raise RuntimeError("progress.json 未写入任务完成标记")
    try:
        _run_aiwiki_json_check(workdir)
        return
    except Exception as first_error:
        append_log(workdir, f"JSON CHECK ERROR: {first_error}")
        mark_progress_running(
            workdir,
            step="修复 JSON",
            summary="JSON 校验失败，正在下发 OpenCode 修复任务",
        )
        run_repair_opencode(workdir, error=str(first_error))
        if not progress_marked_complete(workdir):
            raise RuntimeError("修复后 progress.json 未写入任务完成标记")
        _run_aiwiki_json_check(workdir)


def _run_aiwiki_json_check(workdir: Path) -> None:
    run_check_command(
        workdir,
        python_args(
            ".agents/skills/wechat-raw-materializer/scripts/materialize_raw.py",
            "validate",
            "--json-only",
        ),
        label="AI Wiki JSON 校验",
    )


def _generate_search_assets(manifest: dict[str, Any]) -> bool:
    options = manifest.get("options")
    if not isinstance(options, dict):
        return True
    return bool(options.get("generate_search_assets", True))


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def _can_access_job(user: User, owner_user_id: int | None) -> bool:
    return owner_user_id == user.id or _is_admin(user)


def _default_admin_user_id(db: Session) -> int | None:
    return AiwikiJobDAO(db).default_admin_user_id()


def _default_job_title(files: list[dict[str, Any]], fallback_id: str) -> str:
    first = files[0].get("filename") if files else None
    if isinstance(first, str) and first.strip():
        return f"{first.strip()} 等 {len(files)} 个文件" if len(files) > 1 else first.strip()
    return fallback_id


def _normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
