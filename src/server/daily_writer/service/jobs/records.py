# -*- coding: utf-8 -*-
"""Daily writer record synchronization and orphan recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import progress_marked_complete
from src.server.config import global_config

from ...dao import DailyWriterJobDAO, parse_json_dict
from ...models import DailyWriterJob
from ...parser import parse_daily_writer_result
from ...queue_state import get_queue
from ..persistence import (
    coerce_datetime,
    coerce_int,
    json_string,
    read_manifest,
    update_job,
    write_manifest,
)
from .validation import coerce_variant_count


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = DailyWriterJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_daily_writer/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Daily Writer manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = DailyWriterJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_seed_matrix_job_id=str(manifest["source_seed_matrix_job_id"]),
            source_aiwiki_job_id=str(manifest["source_aiwiki_job_id"]),
            seed_id=str(manifest["seed_id"]),
            title=_normalize_title(manifest.get("title")),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            row_json=json_string(manifest.get("row") or {}),
            params_json=json_string(manifest.get("params") or {}),
            article_path=manifest.get("article_path"),
            metadata_path=manifest.get("metadata_path"),
            summary_json=json_string(manifest.get("summary") or {}),
            created_at=coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=coerce_datetime(manifest.get("started_at")),
            finished_at=coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def reconcile_orphaned_finished_job(db: Session, job: DailyWriterJob) -> DailyWriterJob:
    if job.status not in {"queued", "running"}:
        return job
    workdir = Path(job.workdir)
    if not progress_marked_complete(workdir):
        return job
    params = parse_json_dict(job.params_json)
    queue_position = get_queue().queue_position(job.id)
    has_followup_steps = bool(params.get("generate_variants")) or bool(
        params.get("generate_artwork")
    )
    if queue_position is not None and has_followup_steps:
        return job
    try:
        result = parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=workdir,
            article_path=job.article_path,
            metadata_path=job.metadata_path,
            write_artwork_assets=True,
        )
        if not _result_satisfies_followups(result, params):
            return job
    except Exception as exc:
        logger.warning("跳过 Daily Writer 孤儿任务收尾 {}: {}", job.id, exc)
        return job

    append_log(workdir, "RECOVERY: progress.json 已完成，补写 Daily Writer 任务状态。")
    update_job(
        db,
        job.id,
        status="completed",
        message="长文生成完成",
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        summary=result.summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    reconciled = DailyWriterJobDAO(db).get(job.id) or job
    write_manifest(workdir, reconciled)
    return reconciled


def _result_satisfies_followups(result, params: dict[str, object]) -> bool:
    expected_variants = (
        coerce_variant_count(params.get("variant_count"))
        if params.get("generate_variants")
        else 0
    )
    if expected_variants and len(result.variants) < expected_variants:
        return False
    if params.get("generate_artwork") and (
        not result.artwork.cover_images or not result.artwork.inline_images
    ):
        return False
    return True


def _normalize_title(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
