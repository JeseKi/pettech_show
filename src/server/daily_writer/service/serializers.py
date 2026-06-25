# -*- coding: utf-8 -*-
"""API serializers for daily writer jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.server.aiwiki.service.logs import read_log_tail
from src.server.aiwiki.service.progress import read_progress

from ..dao import parse_json_dict, parse_json_str_dict
from ..models import DailyWriterJob
from ..queue_state import get_queue
from ..schemas import DailyWriterJobOut, DailyWriterJobSummaryOut


def job_out_from_model(
    job: DailyWriterJob, owner_username: str | None = None
) -> DailyWriterJobOut:
    return DailyWriterJobOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        source_seed_matrix_job_id=job.source_seed_matrix_job_id,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        seed_id=job.seed_id,
        title=job.title,
        status=coerce_status(job.status),
        queue_position=get_queue().queue_position(job.id),
        message=job.message,
        row=parse_json_str_dict(job.row_json),
        params=parse_json_dict(job.params_json),
        summary=parse_json_dict(job.summary_json),
        article_path=job.article_path,
        metadata_path=job.metadata_path,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=read_progress(Path(job.workdir)),
        log_tail=read_log_tail(Path(job.workdir)),
    )


def job_summary_from_model(
    job: DailyWriterJob, owner_username: str | None = None
) -> DailyWriterJobSummaryOut:
    return DailyWriterJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        source_seed_matrix_job_id=job.source_seed_matrix_job_id,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        seed_id=job.seed_id,
        title=job.title,
        status=coerce_status(job.status),
        message=job.message,
        row=parse_json_str_dict(job.row_json),
        params=parse_json_dict(job.params_json),
        summary=parse_json_dict(job.summary_json),
        article_path=job.article_path,
        metadata_path=job.metadata_path,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def coerce_status(value: str) -> Any:
    if value not in {"queued", "running", "completed", "failed", "partial_failed"}:
        return "failed"
    return value
