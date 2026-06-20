# -*- coding: utf-8 -*-
"""Public daily writer job service functions."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.dao import AiwikiJobDAO
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.persistence import existing_job_workdir
from src.server.aiwiki.service.progress import (
    initial_progress,
    progress_marked_complete,
    write_progress,
)
from src.server.auth.models import User
from src.server.config import global_config
from src.server.seed_matrix.parser import parse_seed_matrix_result
from src.server.seed_matrix.service.permissions import can_access_job as can_access_source
from src.server.seed_matrix.service.persistence import get_accessible_job as get_seed_matrix_job

from ..dao import DailyWriterJobDAO, parse_json_str_dict
from ..models import DailyWriterJob
from ..parser import parse_daily_writer_result
from ..queue_state import get_queue
from ..schemas import (
    DailyWriterCreate,
    DailyWriterJobListOut,
    DailyWriterJobOut,
    DailyWriterResultOut,
)
from .artifacts import copy_source_artifacts, prepare_skill
from .constants import RESULT_ZIP_NAME, SELECTED_SEED_ROW_PATH
from .opencode import run_opencode
from .permissions import is_admin
from .persistence import (
    build_session_factory,
    coerce_datetime,
    coerce_int,
    get_accessible_job,
    job_workdir,
    json_string,
    new_job_id,
    read_manifest,
    update_job,
    write_manifest,
)
from .serializers import job_out_from_model, job_summary_from_model


def create_job(
    db: Session, payload: DailyWriterCreate, current_user: User
) -> DailyWriterJobOut:
    source_matrix = get_seed_matrix_job(db, payload.source_seed_matrix_job_id, current_user)
    if source_matrix.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能选择已完成的选题矩阵任务",
        )
    if not source_matrix.result_csv_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源选题矩阵没有 CSV 结果",
        )

    source_aiwiki = AiwikiJobDAO(db).get(source_matrix.source_aiwiki_job_id)
    if source_aiwiki is None or not can_access_source(current_user, source_aiwiki.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Wiki 任务不存在")
    if source_aiwiki.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务尚未完成",
        )

    matrix_result = parse_seed_matrix_result(
        job_id=source_matrix.id,
        source_aiwiki_job_id=source_matrix.source_aiwiki_job_id,
        workdir=Path(source_matrix.workdir),
        csv_path=source_matrix.result_csv_path,
    )
    row = _find_seed_row(matrix_result.rows, payload.seed_id)

    source_workdir = existing_job_workdir(source_aiwiki.id, db)
    if not (source_workdir / "material").exists() or not (source_workdir / "wiki").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 缺少 material 或 wiki 结果",
        )

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    write_progress(workdir, initial_progress())
    copy_source_artifacts(source_workdir, workdir)
    prepare_skill(workdir)

    (workdir / SELECTED_SEED_ROW_PATH).write_text(
        json.dumps(row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    params = {"output_date": payload.output_date or ""}
    job = DailyWriterJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_seed_matrix_job_id=source_matrix.id,
        source_aiwiki_job_id=source_aiwiki.id,
        seed_id=row.get("seed_id") or payload.seed_id,
        workdir=workdir.as_posix(),
        row=row,
        params=params,
        created_at=now,
    )
    write_manifest(workdir, job)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: _run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


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
    return job_out_from_model(job, DailyWriterJobDAO(db).owner_username(job.owner_user_id))


def get_result(
    db: Session, job_id: str, current_user: User
) -> DailyWriterResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
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


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务正在执行，完成或失败后才能删除",
        )
    workdir = Path(job.workdir)
    DailyWriterJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def delete_child_jobs_for_seed_matrix(db: Session, source_seed_matrix_job_id: str) -> None:
    dao = DailyWriterJobDAO(db)
    children = dao.list(
        limit=1000,
        offset=0,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
    )
    active = [job for job in children if job.status in {"queued", "running"}]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该选题矩阵仍有关联的长文生成任务正在执行",
        )
    for child in children:
        child_workdir = Path(child.workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    result = get_result(db, job_id, current_user)
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    zip_path = workdir / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(workdir / result.article_path, arcname="main.md")
        archive.write(workdir / result.metadata_path, arcname="metadata.json")
    return zip_path


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = DailyWriterJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_daily_writer/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Daily Writer manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = DailyWriterJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_seed_matrix_job_id=str(manifest["source_seed_matrix_job_id"]),
            source_aiwiki_job_id=str(manifest["source_aiwiki_job_id"]),
            seed_id=str(manifest["seed_id"]),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            row_json=json_string(manifest.get("row") or {}),
            params_json=json_string(manifest.get("params") or {}),
            article_path=manifest.get("article_path"),
            metadata_path=manifest.get("metadata_path"),
            summary_json=json_string(manifest.get("summary") or {}),
            created_at=coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=coerce_datetime(manifest.get("started_at")),
            finished_at=coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def _run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = DailyWriterJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成长文",
            started_at=started_at.isoformat(),
        )
        job = DailyWriterJobDAO(session).get(job_id)
        if job is None:
            return
        workdir = Path(job.workdir)
        write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        run_opencode(
            workdir,
            parse_json_str_dict(job.params_json),
            parse_json_str_dict(job.row_json),
        )
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入任务完成标记")

        result = parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=workdir,
            article_path=None,
            metadata_path=None,
        )
        update_job(
            session,
            job_id,
            status="completed",
            message="长文生成完成",
            article_path=result.article_path,
            metadata_path=result.metadata_path,
            summary=result.summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("Daily writer job failed: {}", job_id)
        try:
            job = DailyWriterJobDAO(session).get(job_id)
            if job is not None:
                append_log(Path(job.workdir), f"ERROR: {exc}")
                update_job(
                    session,
                    job_id,
                    status="failed",
                    message=str(exc),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(Path(job.workdir), DailyWriterJobDAO(session).get(job_id))
        finally:
            pass
    finally:
        session.close()


def _find_seed_row(rows: list[dict[str, str]], seed_id: str) -> dict[str, str]:
    normalized = seed_id.strip()
    for row in rows:
        if row.get("seed_id", "").strip() == normalized:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"选题矩阵中不存在 seed_id：{seed_id}",
    )
