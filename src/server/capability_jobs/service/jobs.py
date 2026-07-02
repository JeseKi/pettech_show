# -*- coding: utf-8 -*-
"""Public generic capability job service functions."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import (
    initial_progress,
    mark_progress_failure,
    mark_progress_running,
    progress_marked_complete,
    write_progress,
)
from src.server.auth.models import User
from src.server.config import global_config
from src.server.opencode.tmux import kill_tmux_sessions_for_workdir

from ..config import CAPABILITIES, CapabilityConfig, get_capability
from ..dao import CapabilityJobDAO, parse_json_dict
from ..models import CapabilityJob
from ..parser import parse_capability_result
from ..queue_state import get_queue
from ..schemas import (
    CapabilityConfigOut,
    CapabilityCreate,
    CapabilityInputOut,
    CapabilityJobListOut,
    CapabilityJobOut,
    CapabilityJobUpdate,
    CapabilityResultOut,
)
from .opencode import run_opencode, run_repair_opencode, run_validator
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

RESULT_MD_PATH = "output/result.md"
RESULT_JSON_PATH = "output/result.json"
RESULT_ZIP_NAME = "capability-result.zip"


def get_capabilities() -> list[CapabilityConfigOut]:
    return [_config_out(config) for config in CAPABILITIES.values()]


def create_job(db: Session, payload: CapabilityCreate, current_user: User) -> CapabilityJobOut:
    config = get_capability(payload.capability_key)
    if config is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="未知能力入口")
    inputs = _normalize_inputs(config, payload.inputs)

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    (workdir / "output").mkdir(parents=True, exist_ok=True)
    write_progress(workdir, initial_progress())
    (workdir / "input" / "inputs.json").write_text(
        json.dumps(inputs, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    job = CapabilityJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        capability_key=config.key,
        workdir=workdir.as_posix(),
        inputs=inputs,
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
    capability_key: str | None = None,
) -> CapabilityJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = CapabilityJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        capability_key=capability_key,
    )
    return CapabilityJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(owner_user_id=owner_filter, capability_key=capability_key),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> CapabilityJobOut:
    job = get_accessible_job(db, job_id, current_user)
    return job_out_from_model(job, CapabilityJobDAO(db).owner_username(job.owner_user_id))


def update_job_title(
    db: Session, job_id: str, payload: CapabilityJobUpdate, current_user: User
) -> CapabilityJobOut:
    job = get_accessible_job(db, job_id, current_user)
    updated = CapabilityJobDAO(db).update(job.id, title=normalize_title(payload.title))
    write_manifest(Path(updated.workdir), updated)
    return job_out_from_model(
        updated,
        CapabilityJobDAO(db).owner_username(updated.owner_user_id),
    )


def get_result(db: Session, job_id: str, current_user: User) -> CapabilityResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_capability_result(
            job_id=job.id,
            capability_key=job.capability_key,
            workdir=Path(job.workdir),
            markdown_path=job.result_markdown_path,
            json_path=job.result_json_path,
            summary=parse_json_dict(job.summary_json),
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    get_queue().cancel(job.id)
    kill_tmux_sessions_for_workdir(workdir)
    CapabilityJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    zip_path = Path(job.workdir) / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for relative in (job.result_markdown_path, job.result_json_path):
            if relative and (Path(job.workdir) / relative).is_file():
                archive.write(Path(job.workdir) / relative, arcname=relative)
    return zip_path


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = CapabilityJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_capability/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Capability manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = CapabilityJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            capability_key=str(manifest["capability_key"]),
            title=normalize_title(manifest.get("title")),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            input_json=json_string(manifest.get("inputs") or {}),
            result_markdown_path=manifest.get("result_markdown_path"),
            result_json_path=manifest.get("result_json_path"),
            summary_json=json_string(manifest.get("summary") or {}),
            created_at=coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=coerce_datetime(manifest.get("started_at")),
            finished_at=coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def normalize_title(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None


def _run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = CapabilityJobDAO(session).get(job_id)
        if job is None:
            return
        config = get_capability(job.capability_key)
        if config is None:
            raise RuntimeError("未知能力入口")
        started_at = datetime.now(timezone.utc)
        update_job(session, job_id, status="running", message="能力任务执行中", started_at=started_at)
        write_manifest(Path(job.workdir), CapabilityJobDAO(session).get(job_id))
        append_log(Path(job.workdir), "开始执行能力任务")
        inputs = parse_json_dict(job.input_json)
        prepare_opencode_config(Path(job.workdir))
        run_opencode(Path(job.workdir), config, inputs)
        if not progress_marked_complete(Path(job.workdir)):
            raise RuntimeError("progress.json 未写入任务完成标记")
        _run_validator_with_repair(Path(job.workdir), config, inputs)
        summary = _result_summary(Path(job.workdir), config)
        finished_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="completed",
            message="能力任务完成",
            result_markdown_path=RESULT_MD_PATH,
            result_json_path=RESULT_JSON_PATH,
            summary=summary,
            finished_at=finished_at,
        )
        write_manifest(Path(job.workdir), CapabilityJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("能力任务 {} 执行失败", job_id)
        try:
            failed_job = CapabilityJobDAO(session).get(job_id)
            if failed_job:
                workdir = Path(failed_job.workdir)
                mark_progress_failure(workdir, str(exc))
                append_log(workdir, f"任务失败：{exc}")
            update_job(
                session,
                job_id,
                status="failed",
                message=str(exc),
                finished_at=datetime.now(timezone.utc),
            )
            job = CapabilityJobDAO(session).get(job_id)
            if job:
                write_manifest(Path(job.workdir), job)
        except Exception:
            logger.exception("更新能力任务失败状态失败")
    finally:
        session.close()


def _normalize_inputs(config: CapabilityConfig, inputs: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for item in config.inputs:
        value = inputs.get(item.key)
        if item.required and (value is None or str(value).strip() == ""):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"请填写：{item.label}")
        if value is not None:
            normalized[item.key] = str(value).strip() if item.type in {"text", "textarea"} else value
    return normalized


def _run_validator_with_repair(
    workdir: Path, config: CapabilityConfig, inputs: dict[str, Any]
) -> None:
    try:
        run_validator(workdir, config, json_only=True)
        return
    except Exception as first_error:
        append_log(workdir, f"CAPABILITY JSON CHECK ERROR: {first_error}")
        mark_progress_running(
            workdir,
            step="修复 result JSON",
            summary="result JSON 校验失败，正在下发 OpenCode 修复任务",
        )
        try:
            run_repair_opencode(workdir, config, inputs, error=str(first_error))
        except Exception:
            raise first_error
        if not progress_marked_complete(workdir):
            raise RuntimeError("修复后 progress.json 未写入任务完成标记")
        run_validator(workdir, config, json_only=True)


def _result_summary(workdir: Path, config: CapabilityConfig) -> dict[str, Any]:
    data_path = workdir / RESULT_JSON_PATH
    summary: dict[str, Any] = {"title": config.title}
    if data_path.is_file():
        try:
            parsed = json.loads(data_path.read_text(encoding="utf-8"))
            if isinstance(parsed, dict):
                raw_summary = parsed.get("summary")
                summary["title"] = str(parsed.get("title") or config.title)
                if isinstance(raw_summary, dict):
                    summary.update(raw_summary)
                elif isinstance(raw_summary, str):
                    summary["summary"] = raw_summary
        except json.JSONDecodeError:
            pass
    if not (workdir / RESULT_MD_PATH).is_file():
        raise FileNotFoundError("OpenCode 未生成 output/result.md")
    if not data_path.is_file():
        raise FileNotFoundError("OpenCode 未生成 output/result.json")
    return summary


def _config_out(config: CapabilityConfig) -> CapabilityConfigOut:
    return CapabilityConfigOut(
        key=config.key,
        group=config.group,
        path=config.path,
        nav_label=config.nav_label,
        title=config.title,
        description=config.description,
        button_text=config.button_text,
        inputs=[
            CapabilityInputOut(
                key=item.key,
                label=item.label,
                type=item.type,
                required=item.required,
                placeholder=item.placeholder,
            )
            for item in config.inputs
        ],
        outputs=list(config.outputs),
        steps=list(config.steps),
    )
