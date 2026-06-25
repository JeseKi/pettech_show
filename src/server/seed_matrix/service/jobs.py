# -*- coding: utf-8 -*-
"""Public seed matrix job service functions."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.dao import AiwikiJobDAO
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.checks import python_args, run_check_command
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.persistence import existing_job_workdir
from src.server.aiwiki.service.progress import (
    initial_progress,
    mark_progress_failure,
    mark_progress_running,
    progress_marked_complete,
    read_progress,
    write_progress,
)
from src.server.auth.models import User
from src.server.config import global_config

from ..dao import SeedMatrixJobDAO, parse_json_dict
from ..models import SeedMatrixJob
from ..parser import parse_seed_matrix_result
from ..queue_state import get_queue
from ..schemas import (
    SeedMatrixCreate,
    SeedMatrixJobListOut,
    SeedMatrixJobOut,
    SeedMatrixJobUpdate,
    SeedMatrixResultOut,
)
from .artifacts import copy_source_artifacts, material_count, prepare_skill
from .constants import FAILURE_REPORT_PATH, RESULT_CSV_PATH
from .opencode import build_generation_params, run_opencode, run_repair_opencode
from .permissions import can_access_job, is_admin
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
    db: Session, payload: SeedMatrixCreate, current_user: User
) -> SeedMatrixJobOut:
    source = AiwikiJobDAO(db).get(payload.source_aiwiki_job_id)
    if source is None or not can_access_job(current_user, source.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Wiki 任务不存在")
    if source.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能选择已完成的 AI Wiki 任务",
        )

    source_workdir = existing_job_workdir(source.id, db)
    if not (source_workdir / "material").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务没有 material 结果",
        )
    count = material_count(source_workdir)
    if count < 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务没有可用 material JSON",
        )

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    write_progress(workdir, initial_progress())
    copy_source_artifacts(source_workdir, workdir)
    prepare_skill(workdir)

    params = build_generation_params(payload, count)
    job = SeedMatrixJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_aiwiki_job_id=source.id,
        workdir=workdir.as_posix(),
        params=params,
        created_at=now,
    )
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: _run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    source_aiwiki_job_id: str | None = None,
) -> SeedMatrixJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = SeedMatrixJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_aiwiki_job_id=source_aiwiki_job_id,
    )
    return SeedMatrixJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(owner_user_id=owner_filter, source_aiwiki_job_id=source_aiwiki_job_id),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> SeedMatrixJobOut:
    job = get_accessible_job(db, job_id, current_user)
    return job_out_from_model(job, SeedMatrixJobDAO(db).owner_username(job.owner_user_id))


def update_job_title(
    db: Session, job_id: str, payload: SeedMatrixJobUpdate, current_user: User
) -> SeedMatrixJobOut:
    job = get_accessible_job(db, job_id, current_user)
    updated = SeedMatrixJobDAO(db).update(job.id, title=normalize_title(payload.title))
    write_manifest(Path(updated.workdir), updated)
    return job_out_from_model(
        updated,
        SeedMatrixJobDAO(db).owner_username(updated.owner_user_id),
    )


def get_result(
    db: Session, job_id: str, current_user: User
) -> SeedMatrixResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_seed_matrix_result(
            job_id=job.id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            workdir=Path(job.workdir),
            csv_path=job.result_csv_path,
        )
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务正在执行，完成或失败后才能删除",
        )
    from src.server.daily_writer.service import delete_child_jobs_for_seed_matrix

    delete_child_jobs_for_seed_matrix(db, job.id)
    workdir = Path(job.workdir)
    SeedMatrixJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def result_csv_file(db: Session, job_id: str, current_user: User) -> Path:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    if not job.result_csv_path:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="矩阵 CSV 不存在")
    path = Path(job.workdir) / job.result_csv_path
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="矩阵 CSV 不存在")
    return path


def normalize_title(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = SeedMatrixJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_seed_matrix/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Seed Matrix manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = SeedMatrixJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_aiwiki_job_id=str(manifest["source_aiwiki_job_id"]),
            title=normalize_title(manifest.get("title")),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            params_json=json_string(manifest.get("params") or {}),
            result_csv_path=manifest.get("result_csv_path"),
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
        job = SeedMatrixJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成选题矩阵",
            started_at=started_at.isoformat(),
        )
        workdir = Path(job.workdir)
        write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        params = parse_json_dict(job.params_json)
        _run_opencode_with_check(workdir, params)

        result = parse_seed_matrix_result(
            job_id=job.id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            workdir=workdir,
            csv_path=RESULT_CSV_PATH,
        )
        update_job(
            session,
            job_id,
            status="completed",
            message="选题矩阵生成完成",
            result_csv_path=RESULT_CSV_PATH,
            summary=result.summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_manifest(workdir, SeedMatrixJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("Seed matrix job failed: {}", job_id)
        try:
            job = SeedMatrixJobDAO(session).get(job_id)
            if job is not None:
                workdir = Path(job.workdir)
                failure_message = _agent_failure_message(workdir, str(exc))
                append_log(workdir, f"ERROR: {failure_message}")
                if not _agent_failure_recorded(workdir):
                    mark_progress_failure(workdir, failure_message)
                update_job(
                    session,
                    job_id,
                    status="failed",
                    message=failure_message,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(workdir, SeedMatrixJobDAO(session).get(job_id))
        finally:
            pass
    finally:
        session.close()


def _run_opencode_with_check(workdir: Path, params: dict[str, object]) -> None:
    run_opencode(workdir, params)
    if not progress_marked_complete(workdir):
        raise RuntimeError(_agent_failure_message(workdir, "progress.json 未写入任务完成标记"))
    try:
        _run_seed_matrix_check(workdir)
        return
    except Exception as first_error:
        append_log(workdir, f"SEED MATRIX CHECK ERROR: {first_error}")
        mark_progress_running(
            workdir,
            step="修复选题矩阵",
            summary="选题矩阵校验失败，正在下发 OpenCode 修复任务",
        )
        run_repair_opencode(workdir, params, error=str(first_error))
        if not progress_marked_complete(workdir):
            raise RuntimeError(_agent_failure_message(workdir, "修复后 progress.json 未写入任务完成标记"))
        _run_seed_matrix_check(workdir)


def _run_seed_matrix_check(workdir: Path) -> None:
    run_check_command(
        workdir,
        python_args(
            ".agents/skills/wechat-seed-matrix-builder/scripts/validate_seed_matrix.py",
            "--source-table",
            RESULT_CSV_PATH,
        ),
        label="选题矩阵校验",
    )


def _agent_failure_recorded(workdir: Path) -> bool:
    return _explicit_agent_failure_message(workdir) is not None and (
        workdir / FAILURE_REPORT_PATH
    ).is_file()


def _agent_failure_message(workdir: Path, fallback: str) -> str:
    explicit_message = _explicit_agent_failure_message(workdir)
    report_exists = (workdir / FAILURE_REPORT_PATH).is_file()
    if explicit_message and report_exists:
        return explicit_message
    if explicit_message:
        return f"{explicit_message}（Agent 未写入失败报告：{FAILURE_REPORT_PATH}）"
    if report_exists:
        return f"OpenCode Agent 写入了失败报告但未在 progress.json 写明失败原因：{FAILURE_REPORT_PATH}"
    return (
        f"OpenCode Agent 未按失败协议写入失败原因和 {FAILURE_REPORT_PATH}"
        f"（原始错误：{fallback}）"
    )


def _explicit_agent_failure_message(workdir: Path) -> str | None:
    events = read_progress(workdir).get("events")
    if not isinstance(events, list):
        return None
    for event in reversed(events):
        if not isinstance(event, dict):
            continue
        if str(event.get("event") or "").strip() != "失败":
            continue
        summary = str(event.get("summary") or "").strip()
        if not summary:
            continue
        step = str(event.get("step") or "").strip()
        if step and step != "任务失败" and step not in summary:
            return f"{step}：{summary}"
        return summary
    return None
