# -*- coding: utf-8 -*-
"""Manifest persistence for Personal AI Wiki jobs."""

from __future__ import annotations

import json
import os
import secrets
from pathlib import Path
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.database import SessionLocal

from ..dao import PersonalAiwikiJobDAO
from ..models import PersonalAiwikiJob


def read_manifest(workdir: Path) -> dict[str, Any]:
    return json.loads((workdir / "manifest.json").read_text(encoding="utf-8"))


def write_manifest(workdir: Path, manifest: dict[str, Any]) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "manifest.json"
    tmp_path = workdir / f"manifest.json.{secrets.token_hex(8)}.tmp"
    tmp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
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
    upsert_job_from_manifest(manifest, session_factory=session_factory)


def upsert_job_from_manifest(
    manifest: dict[str, Any],
    *,
    session_factory: sessionmaker[Session] | None = None,
) -> PersonalAiwikiJob | None:
    factory = session_factory or SessionLocal
    session = factory()
    try:
        return PersonalAiwikiJobDAO(session).upsert_from_payload(manifest_db_payload(manifest))
    except Exception as exc:
        logger.warning("同步个人 AI Wiki 任务到数据库失败 {}: {}", manifest.get("id"), exc)
        return None
    finally:
        session.close()


def manifest_db_payload(manifest: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": manifest.get("id"),
        "owner_user_id": manifest.get("owner_user_id"),
        "status": manifest.get("status") or "queued",
        "operation": manifest.get("operation") or "ingest",
        "title": manifest.get("title"),
        "description": manifest.get("description"),
        "message": manifest.get("message"),
        "workdir": manifest.get("workdir"),
        "workspace_dir": manifest.get("workspace_dir"),
        "input_text": manifest.get("input_text"),
        "files": manifest.get("files") or [],
        "summary": manifest.get("summary"),
        "answer_markdown": manifest.get("answer_markdown"),
        "created_at": manifest.get("created_at"),
        "started_at": manifest.get("started_at"),
        "finished_at": manifest.get("finished_at"),
    }


def read_answer(workdir: Path) -> str | None:
    answer_path = workdir / "answer.md"
    if not answer_path.exists():
        return None
    answer = answer_path.read_text(encoding="utf-8", errors="replace").strip()
    return answer or None
