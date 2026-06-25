# -*- coding: utf-8 -*-
"""Social card background job runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import mark_progress_failure, progress_marked_complete

from ...dao import SocialCardJobDAO, parse_json_dict
from ...parser import parse_social_card_result
from ..opencode import run_opencode
from ..persistence import update_job, write_manifest
from .validation import (
    assert_result_counts,
    coerce_card_count,
    coerce_post_count,
    ensure_progress_events_preserved,
    incomplete_progress_message,
    progress_events_snapshot,
)


def run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = SocialCardJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成小红书图文卡",
            started_at=started_at.isoformat(),
        )
        job = SocialCardJobDAO(session).get(job_id)
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
    params = parse_json_dict(job.params_json)
    post_count = coerce_post_count(params.get("post_count"))
    cards_per_post = coerce_card_count(params.get("cards_per_post", params.get("card_count")))
    progress_events = progress_events_snapshot(workdir)
    try:
        run_opencode(workdir, post_count=post_count, cards_per_post=cards_per_post)
    finally:
        ensure_progress_events_preserved(workdir, progress_events, "小红书图文卡生成")
    if not progress_marked_complete(workdir):
        raise RuntimeError(
            incomplete_progress_message(
                workdir,
                post_count=post_count,
                cards_per_post=cards_per_post,
            )
        )
    result = parse_social_card_result(
        job_id=job.id,
        source_daily_writer_job_id=job.source_daily_writer_job_id,
        workdir=workdir,
    )
    assert_result_counts(
        result=result,
        post_count=post_count,
        cards_per_post=cards_per_post,
    )
    total_card_count = post_count * cards_per_post
    if len(result.images) != total_card_count:
        raise RuntimeError(
            f"图文卡生成数量不符：期望 {total_card_count} 张，实际 {len(result.images)} 张"
        )
    summary = {
        **result.summary,
        "post_count": post_count,
        "cards_per_post": cards_per_post,
        "requested_count": total_card_count,
        "image_count": len(result.images),
        "status": "completed",
    }
    update_job(
        session,
        job_id,
        status="completed",
        message="小红书图文卡生成完成",
        summary=summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(workdir, SocialCardJobDAO(session).get(job_id))


def _mark_failed(session: Session, *, job_id: str, exc: Exception) -> None:
    logger.exception("Social card job failed: {}", job_id)
    job = SocialCardJobDAO(session).get(job_id)
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
    write_manifest(workdir, SocialCardJobDAO(session).get(job_id))
