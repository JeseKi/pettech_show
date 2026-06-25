# -*- coding: utf-8 -*-
"""Social card video background job runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import mark_progress_failure, progress_marked_complete

from ...dao import SocialCardVideoJobDAO
from ...parser import parse_social_card_video_result
from ..opencode import run_opencode
from ..persistence import update_job, write_manifest
from .validation import (
    ensure_progress_events_preserved,
    incomplete_progress_message,
    progress_events_snapshot,
)


def run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = SocialCardVideoJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成轮播视频",
            started_at=started_at.isoformat(),
        )
        job = SocialCardVideoJobDAO(session).get(job_id)
        if job is None:
            return
        _run_loaded_job(session, job_id=job_id, job=job)
    except Exception as exc:
        _mark_failed(session, job_id=job_id, exc=exc)
    finally:
        session.close()


def _run_loaded_job(session: Session, *, job_id: str, job) -> None:
    workdir = Path(job.workdir)
    write_manifest(workdir, job)
    prepare_opencode_config(workdir)
    progress_events = progress_events_snapshot(workdir)
    try:
        run_opencode(workdir)
    finally:
        ensure_progress_events_preserved(workdir, progress_events, "轮播视频生成")
    if not progress_marked_complete(workdir):
        raise RuntimeError(incomplete_progress_message(workdir))
    result = parse_social_card_video_result(
        job_id=job.id,
        source_social_card_job_id=job.source_social_card_job_id,
        workdir=workdir,
    )
    if not result.videos:
        raise RuntimeError("轮播视频生成数量为 0")
    summary = {
        **result.summary,
        "video_count": len(result.videos),
        "status": "completed",
    }
    update_job(
        session,
        job_id,
        status="completed",
        message="轮播视频生成完成",
        summary=summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(workdir, SocialCardVideoJobDAO(session).get(job_id))


def _mark_failed(session: Session, *, job_id: str, exc: Exception) -> None:
    logger.exception("Social card video job failed: {}", job_id)
    job = SocialCardVideoJobDAO(session).get(job_id)
    if job is None:
        return
    workdir = Path(job.workdir)
    append_log(workdir, f"ERROR: {exc}")
    mark_progress_failure(workdir, str(exc))
    update_job(
        session,
        job_id,
        status="failed",
        message=str(exc),
        summary={"status": "failed", "error": str(exc)},
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(workdir, SocialCardVideoJobDAO(session).get(job_id))

