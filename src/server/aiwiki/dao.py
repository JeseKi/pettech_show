# -*- coding: utf-8 -*-
"""AI Wiki job DAO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO

from .models import AiwikiJob


class AiwikiJobDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get(self, job_id: str) -> AiwikiJob | None:
        return (
            self.db_session.query(AiwikiJob)
            .filter(AiwikiJob.id == job_id)
            .first()
        )

    def list(self, *, limit: int, offset: int) -> list[AiwikiJob]:
        return (
            self.db_session.query(AiwikiJob)
            .order_by(AiwikiJob.created_at.desc(), AiwikiJob.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(self) -> int:
        return self.db_session.query(AiwikiJob).count()

    def upsert_from_payload(self, payload: dict[str, Any]) -> AiwikiJob:
        job = self.get(str(payload["id"]))
        if job is None:
            job = AiwikiJob(id=str(payload["id"]), workdir=str(payload["workdir"]))
            self.db_session.add(job)
        self.apply_payload(job, payload)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def update(self, job_id: str, **fields: Any) -> AiwikiJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        payload = {
            "id": job.id,
            "workdir": job.workdir,
            "status": fields.get("status", job.status),
            "message": fields.get("message", job.message),
            "raw_date": fields.get("raw_date", job.raw_date),
            "files": fields.get("files_json", job.files_json),
            "summary": fields.get("summary_json", job.summary_json),
            "created_at": fields.get("created_at", job.created_at),
            "started_at": fields.get("started_at", job.started_at),
            "finished_at": fields.get("finished_at", job.finished_at),
        }
        self.apply_payload(job, payload)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def apply_payload(self, job: AiwikiJob, payload: dict[str, Any]) -> None:
        job.status = str(payload.get("status") or job.status or "queued")
        job.message = payload.get("message")
        job.workdir = str(payload.get("workdir") or job.workdir)
        job.raw_date = payload.get("raw_date")
        job.files_json = _json_string(payload.get("files_json") or payload.get("files") or [])
        summary = payload.get("summary_json")
        if summary is None:
            summary = payload.get("summary")
        job.summary_json = None if summary is None else _json_string(summary)
        job.created_at = _coerce_datetime(payload.get("created_at")) or job.created_at
        job.started_at = _coerce_datetime(payload.get("started_at"))
        job.finished_at = _coerce_datetime(payload.get("finished_at"))
        job.updated_at = datetime.now(timezone.utc)


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
