# -*- coding: utf-8 -*-
"""Persistence helpers for seed matrix jobs."""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.config import global_config

from ..dao import SeedMatrixJobDAO, parse_json_dict
from ..models import SeedMatrixJob
from .permissions import can_access_job


def new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_seed_matrix"


def job_workdir(job_id: str) -> Path:
    return Path(global_config.project_root) / "data" / job_id


def get_accessible_job(
    db: Session, job_id: str, current_user: Any
) -> SeedMatrixJob:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_seed_matrix", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    job = SeedMatrixJobDAO(db).get(job_id)
    if job is None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def update_job(session: Session, job_id: str, **fields: Any) -> None:
    SeedMatrixJobDAO(session).update(job_id, **fields)


def build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建选题矩阵任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def read_manifest(workdir: Path) -> dict[str, Any]:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(workdir: Path, job: SeedMatrixJob | None) -> None:
    if job is None:
        return

    payload = {
        "id": job.id,
        "owner_user_id": job.owner_user_id,
        "source_aiwiki_job_id": job.source_aiwiki_job_id,
        "status": job.status,
        "message": job.message,
        "workdir": job.workdir,
        "params": parse_json_dict(job.params_json),
        "result_csv_path": job.result_csv_path,
        "summary": parse_json_dict(job.summary_json),
        "created_at": job.created_at.isoformat(),
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
    }
    tmp_path = workdir / "manifest.json.tmp"
    tmp_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, workdir / "manifest.json")


def coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
