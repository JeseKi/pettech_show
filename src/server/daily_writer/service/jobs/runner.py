# -*- coding: utf-8 -*-
"""Daily writer background job runner."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import (
    mark_progress_failure,
    progress_marked_complete,
)

from ...dao import DailyWriterJobDAO, parse_json_dict, parse_json_str_dict
from ...parser import parse_daily_writer_result
from ...schemas import DailyWriterResultOut
from ..artifacts import ensure_artwork_artifacts
from ..opencode import run_artwork_opencode, run_opencode, run_variant_opencode
from ..persistence import update_job, write_manifest
from .status_updates import (
    mark_artwork_running,
    mark_completed,
    mark_partial_failed,
    mark_variant_running,
)
from .validation import (
    coerce_variant_count,
    ensure_progress_events_preserved,
    progress_events_snapshot,
    run_daily_writer_json_check_with_repair,
)


def run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = _mark_started(session, job_id)
        if job is None:
            return
        workdir = Path(job.workdir)
        write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        params = parse_json_dict(job.params_json)
        result = _run_main_article(job, workdir=workdir, params=params)
        variant_result = _run_variants_if_requested(session, job, workdir, params, result)
        if variant_result is None:
            return
        artwork_result = _run_artwork_if_requested(
            session, job, workdir, params, variant_result
        )
        if artwork_result is None:
            return
        mark_completed(session, job_id=job_id, workdir=workdir, result=artwork_result)
    except Exception as exc:
        _mark_failed(session, job_id=job_id, exc=exc)
    finally:
        session.close()


def _mark_started(session: Session, job_id: str):
    job = DailyWriterJobDAO(session).get(job_id)
    if job is None:
        return None
    update_job(
        session,
        job_id,
        status="running",
        message="OpenCode 正在生成长文",
        started_at=datetime.now(timezone.utc).isoformat(),
    )
    return DailyWriterJobDAO(session).get(job_id)


def _run_main_article(job, *, workdir: Path, params: dict[str, object]) -> DailyWriterResultOut:
    main_progress_events = progress_events_snapshot(workdir)
    try:
        run_opencode(workdir, params, parse_json_str_dict(job.row_json))
    finally:
        ensure_progress_events_preserved(workdir, main_progress_events, "长文生成")
    if not progress_marked_complete(workdir):
        raise RuntimeError("progress.json 未写入任务完成标记")
    run_daily_writer_json_check_with_repair(workdir)
    return parse_daily_writer_result(
        job_id=job.id,
        source_seed_matrix_job_id=job.source_seed_matrix_job_id,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        seed_id=job.seed_id,
        workdir=workdir,
        article_path=None,
        metadata_path=None,
        write_artwork_assets=True,
    )


def _run_variants_if_requested(
    session: Session,
    job,
    workdir: Path,
    params: dict[str, object],
    result: DailyWriterResultOut,
) -> DailyWriterResultOut | None:
    if not bool(params.get("generate_variants")):
        result.summary.update(
            {"variant_requested_count": 0, "variant_failed_count": 0, "variant_status": "not_requested"}
        )
        return result
    variant_count = coerce_variant_count(params.get("variant_count"))
    try:
        mark_variant_running(session, job.id, workdir, result, variant_count)
        article_dir = Path(result.metadata_path).parent.as_posix()
        variant_progress_events = progress_events_snapshot(workdir)
        try:
            run_variant_opencode(workdir, article_dir=article_dir, variant_count=variant_count)
        finally:
            ensure_progress_events_preserved(
                workdir, variant_progress_events, "长文变体生成"
            )
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入变体任务完成标记")
        run_daily_writer_json_check_with_repair(
            workdir,
            article_dir=article_dir,
            include_variants=True,
        )
        result = _parse_current_result(job, workdir, result)
        if len(result.variants) < variant_count:
            raise RuntimeError(
                f"变体生成数量不足：期望 {variant_count} 篇，实际 {len(result.variants)} 篇"
            )
        result.summary.update(
            {
                "variant_requested_count": variant_count,
                "variant_success_count": len(result.variants),
                "variant_failed_count": 0,
                "variant_status": "completed",
            }
        )
        return result
    except Exception as variant_exc:
        logger.exception("Daily writer variant generation failed: {}", job.id)
        append_log(workdir, f"VARIANT ERROR: {variant_exc}")
        mark_progress_failure(workdir, f"长文变体生成失败：{variant_exc}")
        result.summary.update(
            {
                "variant_requested_count": variant_count,
                "variant_success_count": len(result.variants),
                "variant_failed_count": max(variant_count - len(result.variants), 1),
                "variant_status": "failed",
                "variant_error": str(variant_exc),
            }
        )
        mark_partial_failed(session, job.id, workdir, result, f"长文已生成，变体生成失败：{variant_exc}")
        return None


def _run_artwork_if_requested(
    session: Session,
    job,
    workdir: Path,
    params: dict[str, object],
    result: DailyWriterResultOut,
) -> DailyWriterResultOut | None:
    if not bool(params.get("generate_artwork")):
        result.summary.update(
            {"artwork_status": "not_requested", "artwork_cover_count": 0, "artwork_inline_count": 0}
        )
        return result
    try:
        ensure_artwork_artifacts(workdir)
        mark_artwork_running(session, job.id, workdir, result)
        article_dir = Path(result.metadata_path).parent.as_posix()
        artwork_progress_events = progress_events_snapshot(workdir)
        try:
            run_artwork_opencode(workdir, article_dir=article_dir)
        finally:
            ensure_progress_events_preserved(
                workdir, artwork_progress_events, "封面插图生成"
            )
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入封面插图任务完成标记")
        result = _parse_current_result(job, workdir, result)
        if not result.artwork.cover_images or not result.artwork.inline_images:
            raise RuntimeError("封面或正文插图生成数量不足")
        result.summary.update(
            {
                "artwork_status": "completed",
                "artwork_cover_count": len(result.artwork.cover_images),
                "artwork_inline_count": len(result.artwork.inline_images),
            }
        )
        return result
    except Exception as artwork_exc:
        logger.exception("Daily writer artwork generation failed: {}", job.id)
        append_log(workdir, f"ARTWORK ERROR: {artwork_exc}")
        mark_progress_failure(workdir, f"封面插图生成失败：{artwork_exc}")
        result.summary.update(
            {
                "artwork_status": "failed",
                "artwork_error": str(artwork_exc),
                "artwork_cover_count": len(result.artwork.cover_images),
                "artwork_inline_count": len(result.artwork.inline_images),
            }
        )
        mark_partial_failed(session, job.id, workdir, result, f"长文已生成，封面插图生成失败：{artwork_exc}")
        return None


def _parse_current_result(job, workdir: Path, result: DailyWriterResultOut) -> DailyWriterResultOut:
    return parse_daily_writer_result(
        job_id=job.id,
        source_seed_matrix_job_id=job.source_seed_matrix_job_id,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        seed_id=job.seed_id,
        workdir=workdir,
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        write_artwork_assets=True,
    )


def _mark_failed(session: Session, *, job_id: str, exc: Exception) -> None:
    logger.exception("Daily writer job failed: {}", job_id)
    job = DailyWriterJobDAO(session).get(job_id)
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
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
