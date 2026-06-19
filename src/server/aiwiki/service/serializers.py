# -*- coding: utf-8 -*-
"""API serializers for AI Wiki service objects."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

from ..models import AiwikiJob
from ..schemas import JobOut, JobStatus, JobSummaryOut, UploadedFileOut
from .logs import read_log_tail
from .progress import read_progress
from .queue_state import get_queue


def job_out_from_manifest(
    workdir: Path, manifest: dict[str, Any], owner_username: str | None = None
) -> JobOut:
    payload = dict(manifest)
    payload["owner_username"] = owner_username
    payload["queue_position"] = get_queue().queue_position(manifest["id"])
    payload["progress"] = read_progress(workdir)
    payload["log_tail"] = read_log_tail(workdir)
    return JobOut.model_validate(payload)


def job_summary_from_model(
    job: AiwikiJob, owner_username: str | None = None
) -> JobSummaryOut:
    return JobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        owner_username=owner_username,
        status=coerce_job_status(job.status),
        message=job.message,
        created_at=job.created_at,
        started_at=job.started_at,
        finished_at=job.finished_at,
        files=parse_uploaded_files(job.files_json),
        summary=parse_json_dict(job.summary_json),
    )


def parse_json_list(value: str | None) -> list[dict[str, Any]]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_uploaded_files(value: str | None) -> list[UploadedFileOut]:
    return [
        UploadedFileOut.model_validate(item)
        for item in parse_json_list(value)
        if isinstance(item, dict)
    ]


def coerce_job_status(value: str) -> JobStatus:
    if value not in {"queued", "running", "completed", "failed"}:
        return "failed"
    return cast(JobStatus, value)
