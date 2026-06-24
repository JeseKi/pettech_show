# -*- coding: utf-8 -*-
"""Manifest and database persistence helpers for AI Wiki jobs."""

from __future__ import annotations

import json
import os
import re
import secrets
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.orm import Session, sessionmaker

from src.server.config import global_config
from src.server.database import SessionLocal

from ..dao import AiwikiJobDAO


def new_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_aiwiki"


def job_workdir(job_id: str) -> Path:
    return Path(global_config.project_root) / "data" / job_id


def existing_job_workdir(job_id: str, db: Session | None = None) -> Path:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_aiwiki", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    workdir = None
    if db is not None:
        job = AiwikiJobDAO(db).get(job_id)
        if job is not None:
            workdir = Path(job.workdir)
    workdir = workdir or job_workdir(job_id)
    if not (workdir / "manifest.json").exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return workdir


def read_manifest(workdir: Path) -> dict[str, Any]:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(workdir: Path, manifest: dict[str, Any]) -> None:
    path = workdir / "manifest.json"
    tmp_path = workdir / "manifest.json.tmp"
    tmp_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(tmp_path, path)


def update_manifest(
    workdir: Path,
    *,
    session_factory: sessionmaker[Session] | None = None,
    **fields: Any,
) -> None:
    manifest = read_manifest(workdir)
    manifest.update(fields)
    write_manifest(workdir, manifest)
    upsert_job_from_manifest(
        None, workdir, manifest, session_factory=session_factory
    )


def upsert_job_from_manifest(
    db: Session | None,
    workdir: Path,
    manifest: dict[str, Any],
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> None:
    payload = manifest_db_payload(workdir, manifest)
    if db is not None:
        AiwikiJobDAO(db).upsert_from_payload(payload)
        return

    factory = session_factory or SessionLocal
    session = factory()
    try:
        AiwikiJobDAO(session).upsert_from_payload(payload)
    except Exception as exc:
        logger.warning("同步 AI Wiki 任务到数据库失败 {}: {}", manifest.get("id"), exc)
    finally:
        session.close()


def build_session_factory(db: Session) -> sessionmaker[Session]:
    bind = db.get_bind()
    if isinstance(bind, Connection):
        bind = bind.engine
    if not isinstance(bind, Engine):
        raise RuntimeError("无法创建 AI Wiki 任务会话工厂")
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


def manifest_db_payload(workdir: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest.get("id") or workdir.name,
        "owner_user_id": manifest.get("owner_user_id"),
        "status": manifest.get("status") or "queued",
        "title": manifest.get("title"),
        "description": manifest.get("description"),
        "message": manifest.get("message"),
        "workdir": manifest.get("workdir") or workdir.as_posix(),
        "raw_date": manifest.get("raw_date"),
        "files": manifest.get("files") or [],
        "summary": manifest.get("summary"),
        "created_at": manifest.get("created_at"),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
    }
