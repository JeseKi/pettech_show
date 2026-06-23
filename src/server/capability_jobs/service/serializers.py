# -*- coding: utf-8 -*-
"""API serializers for generic capability jobs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.server.aiwiki.service.logs import read_log_tail
from src.server.aiwiki.service.progress import read_progress

from ..dao import parse_json_dict
from ..models import CapabilityJob
from ..queue_state import get_queue
from ..schemas import CapabilityJobOut, CapabilityJobSummaryOut


def job_out_from_model(job: CapabilityJob, owner_username: str | None = None) -> CapabilityJobOut:
    return CapabilityJobOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        capability_key=job.capability_key,
        status=coerce_status(job.status),
        queue_position=get_queue().queue_position(job.id),
        message=job.message,
        inputs=parse_json_dict(job.input_json),
        summary=parse_json_dict(job.summary_json),
        result_markdown_path=job.result_markdown_path,
        result_json_path=job.result_json_path,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        progress=read_progress(Path(job.workdir)),
        log_tail=read_log_tail(Path(job.workdir)),
    )


def job_summary_from_model(job: CapabilityJob, owner_username: str | None = None) -> CapabilityJobSummaryOut:
    return CapabilityJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        capability_key=job.capability_key,
        status=coerce_status(job.status),
        message=job.message,
        inputs=parse_json_dict(job.input_json),
        summary=parse_json_dict(job.summary_json),
        result_markdown_path=job.result_markdown_path,
        result_json_path=job.result_json_path,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
    )


def coerce_status(value: str) -> Any:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return value
