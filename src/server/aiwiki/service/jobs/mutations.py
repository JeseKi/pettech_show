# -*- coding: utf-8 -*-
"""AI Wiki job mutations."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.opencode.tmux import kill_tmux_sessions_for_workdir

from ...dao import AiwikiJobDAO
from ...schemas import JobOut, JobUpdate
from ..persistence import (
    existing_job_workdir,
    manifest_db_payload,
    read_manifest,
    write_manifest,
)
from ..queue_state import get_queue
from ..serializers import job_out_from_manifest
from .access import can_access_job, normalize_optional_text
from .queries import parse_manifest_files


def update_job(
    db: Session, job_id: str, payload: JobUpdate, current_user: User
) -> JobOut:
    workdir = existing_job_workdir(job_id, db)
    dao = AiwikiJobDAO(db)
    job = dao.get(job_id)
    if job is None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    normalized = _normalized_update_fields(payload)
    manifest = read_manifest(workdir)
    manifest.update(normalized)
    write_manifest(workdir, manifest)
    dao.append_audit_log(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="update",
        job_id=job.id,
        target_filename=_target_filenames(workdir, fallback=job.id),
        message=f"{current_user.username} 更新了知识库任务 {job.id}",
        metadata={"job_id": job.id, "fields": sorted(normalized.keys())},
    )
    updated = dao.upsert_from_payload(manifest_db_payload(workdir, manifest))
    manifest["owner_user_id"] = updated.owner_user_id
    manifest["title"] = updated.title or manifest.get("title")
    manifest["description"] = updated.description
    return job_out_from_manifest(workdir, manifest, dao.owner_username(updated.owner_user_id))


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    workdir = existing_job_workdir(job_id, db)
    dao = AiwikiJobDAO(db)
    job = dao.get(job_id)
    if job is None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    get_queue().cancel(job.id)
    kill_tmux_sessions_for_workdir(workdir)
    dao.append_audit_log(
        actor_user_id=current_user.id,
        actor_username=current_user.username,
        action="delete",
        job_id=job.id,
        target_filename=_target_filenames(workdir, fallback=job.id),
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
    for child in children:
        from src.server.daily_writer.service import delete_child_jobs_for_seed_matrix
        from src.server.seed_matrix.queue_state import get_queue

        delete_child_jobs_for_seed_matrix(db, child.id)
        child_workdir = Path(child.workdir)
        get_queue().cancel(child.id)
        kill_tmux_sessions_for_workdir(child_workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)


def _normalized_update_fields(payload: JobUpdate) -> dict[str, Any]:
    fields = payload.model_dump(exclude_unset=True)
    normalized: dict[str, Any] = {}
    if "title" in fields:
        normalized["title"] = normalize_optional_text(fields.get("title"))
    if "description" in fields:
        normalized["description"] = normalize_optional_text(fields.get("description"))
    return normalized


def _target_filenames(workdir: Path, *, fallback: str) -> str:
    return ", ".join(
        item.get("filename", "")
        for item in parse_manifest_files(workdir)
        if isinstance(item, dict)
    ) or fallback
