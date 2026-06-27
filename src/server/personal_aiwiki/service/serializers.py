# -*- coding: utf-8 -*-
"""Serialization helpers for Personal AI Wiki jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from src.server.aiwiki.parser import parse_aiwiki_result
from src.server.aiwiki.schemas import JobStatus, UploadedFileOut
from src.server.aiwiki.service.logs import read_log_tail
from src.server.aiwiki.service.progress import read_progress

from ..models import PersonalAiwikiJob
from ..schemas import (
    PersonalAiwikiJobOut,
    PersonalAiwikiJobSummaryOut,
    PersonalAiwikiOperation,
    PersonalAiwikiResultOut,
    PersonalAiwikiStatsOut,
)


def job_out_from_model(
    job: PersonalAiwikiJob,
    owner_username: str | None = None,
    queue_position: int | None = None,
) -> PersonalAiwikiJobOut:
    return PersonalAiwikiJobOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        operation=coerce_operation(job.operation),
        title=job.title or job.id,
        description=job.description,
        status=coerce_job_status(job.status),
        queue_position=queue_position,
        message=job.message,
        workspace_dir=job.workspace_dir,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=parse_uploaded_files(job.files_json),
        progress=read_progress(Path(job.workdir)),
        log_tail=read_log_tail(Path(job.workdir)),
    )


def job_summary_from_model(
    job: PersonalAiwikiJob,
    owner_username: str | None = None,
) -> PersonalAiwikiJobSummaryOut:
    return PersonalAiwikiJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        operation=coerce_operation(job.operation),
        title=job.title or job.id,
        description=job.description,
        status=coerce_job_status(job.status),
        message=job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=parse_uploaded_files(job.files_json),
        summary=parse_json_dict(job.summary_json),
    )


def build_result_from_job(job: PersonalAiwikiJob) -> PersonalAiwikiResultOut:
    result = parse_aiwiki_result(job.id, Path(job.workspace_dir))
    return PersonalAiwikiResultOut.model_validate(
        {
            **result.model_dump(),
            "operation": coerce_operation(job.operation),
            "answer_markdown": job.answer_markdown,
            "workspace_dir": job.workspace_dir,
        }
    )


def build_stats(jobs: list[PersonalAiwikiJob]) -> PersonalAiwikiStatsOut:
    return PersonalAiwikiStatsOut(
        ingest_count=sum(1 for job in jobs if job.operation == "ingest"),
        query_count=sum(1 for job in jobs if job.operation == "query"),
        lint_count=sum(1 for job in jobs if job.operation == "lint"),
        active_count=sum(1 for job in jobs if job.status in {"queued", "running"}),
        completed_count=sum(1 for job in jobs if job.status == "completed"),
        total_count=len(jobs),
    )


def parse_json_list(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    if not value:
        return []
    try:
        parsed = json.loads(str(value))
    except json.JSONDecodeError:
        return []
    return [item for item in parsed if isinstance(item, dict)] if isinstance(parsed, list) else []


def parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_uploaded_files(value: str | None) -> list[UploadedFileOut]:
    return [UploadedFileOut.model_validate(item) for item in parse_json_list(value)]


def coerce_job_status(value: str) -> JobStatus:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return cast(JobStatus, value)


def coerce_operation(value: str) -> PersonalAiwikiOperation:
    if value in {"ingest", "query", "lint"}:
        return cast(PersonalAiwikiOperation, value)
    return "ingest"


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
