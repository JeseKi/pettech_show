# -*- coding: utf-8 -*-
"""Public AI Wiki job service functions."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import shutil
from typing import Any

from fastapi import HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.config import global_config
from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ..dao import AiwikiJobDAO
from ..parser import parse_aiwiki_result
from ..schemas import AiwikiResultOut, JobListOut, JobOut
from .constants import ALLOWED_EXTENSIONS
from .files import convert_to_markdown, safe_filename
from .logs import append_log
from .opencode import prepare_opencode_config, prepare_skills, run_opencode
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
from .progress import initial_progress, progress_marked_complete, write_progress
from .queue_state import get_queue
from .serializers import job_out_from_manifest, job_summary_from_model


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

    total_size = 0
    saved_files: list[dict[str, Any]] = []
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

        upload_path = uploads_dir / original_name
        upload_path.write_bytes(content)
        raw_text = convert_to_markdown(upload_path, content, extension)
        raw_name = f"{raw_date}_{index}_{Path(original_name).stem}.md"
        raw_path = raw_dir / safe_filename(raw_name)
        raw_path.write_text(raw_text, encoding="utf-8")
        saved_files.append(
            {
                "filename": original_name,
                "size_bytes": len(content),
                "raw_path": raw_path.relative_to(workdir).as_posix(),
            }
        )

    manifest = {
        "id": job_id,
        "owner_user_id": current_user.id,
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
    owner_filter = None if _is_admin(current_user) else current_user.id
    items = [
        job_summary_from_model(job, dao.owner_username(job.owner_user_id))
        for job in dao.list(
            limit=normalized_limit,
            offset=normalized_offset,
            owner_user_id=owner_filter,
            status=status,
        )
    ]
    return JobListOut(
        items=items,
        total=dao.count(owner_user_id=owner_filter, status=status),
        limit=normalized_limit,
        offset=normalized_offset,
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
    return job_out_from_manifest(workdir, manifest, dao.owner_username(job.owner_user_id))


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
        run_opencode(
            workdir,
            generate_search_assets=_generate_search_assets(read_manifest(workdir)),
        )
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入任务完成标记")
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


def _generate_search_assets(manifest: dict[str, Any]) -> bool:
    options = manifest.get("options")
    if not isinstance(options, dict):
        return True
    return bool(options.get("generate_search_assets", True))


def _is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def _can_access_job(user: User, owner_user_id: int | None) -> bool:
    return _is_admin(user) or owner_user_id == user.id


def _default_admin_user_id(db: Session) -> int | None:
    return AiwikiJobDAO(db).default_admin_user_id()
