# -*- coding: utf-8 -*-
"""Daily writer job status update helpers."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy.orm import Session

from src.server.aiwiki.service.progress import mark_progress_running

from ...dao import DailyWriterJobDAO
from ...schemas import DailyWriterResultOut
from ..persistence import update_job, write_manifest


def mark_variant_running(
    session: Session,
    job_id: str,
    workdir: Path,
    result: DailyWriterResultOut,
    variant_count: int,
) -> None:
    update_job(
        session,
        job_id,
        status="running",
        message="OpenCode 正在生成长文变体",
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        summary={
            **result.summary,
            "variant_requested_count": variant_count,
            "variant_failed_count": 0,
            "variant_status": "running",
        },
    )
    write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
    mark_progress_running(workdir, step="生成长文变体", summary="长文已生成，正在生成长文变体")


def mark_artwork_running(
    session: Session, job_id: str, workdir: Path, result: DailyWriterResultOut
) -> None:
    update_job(
        session,
        job_id,
        status="running",
        message="OpenCode 正在生成封面和插图",
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        summary={
            **result.summary,
            "artwork_status": "running",
            "artwork_cover_count": 0,
            "artwork_inline_count": 0,
        },
    )
    write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
    mark_progress_running(workdir, step="生成封面插图", summary="长文已生成，正在生成封面和插图")


def mark_partial_failed(
    session: Session, job_id: str, workdir: Path, result: DailyWriterResultOut, message: str
) -> None:
    update_job(
        session,
        job_id,
        status="partial_failed",
        message=message,
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        summary=result.summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))


def mark_completed(
    session: Session, *, job_id: str, workdir: Path, result: DailyWriterResultOut
) -> None:
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
