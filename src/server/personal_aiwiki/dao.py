# -*- coding: utf-8 -*-
"""Personal AI Wiki DAO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.dao.dao_base import BaseDAO

from .models import PersonalAiwikiJob


class PersonalAiwikiJobDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def get(self, job_id: str) -> PersonalAiwikiJob | None:
        return (
            self.db_session.query(PersonalAiwikiJob)
            .filter(PersonalAiwikiJob.id == job_id)
            .first()
        )

    def list(
        self,
        *,
        limit: int,
        offset: int,
        owner_user_id: int | None = None,
        status: str | None = None,
        operation: str | None = None,
    ) -> list[PersonalAiwikiJob]:
        query = self.db_session.query(PersonalAiwikiJob)
        if owner_user_id is not None:
            query = query.filter(PersonalAiwikiJob.owner_user_id == owner_user_id)
        if status is not None:
            query = query.filter(PersonalAiwikiJob.status == status)
        if operation is not None:
            query = query.filter(PersonalAiwikiJob.operation == operation)
        return (
            query.order_by(PersonalAiwikiJob.created_at.desc(), PersonalAiwikiJob.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(
        self,
        *,
        owner_user_id: int | None = None,
        status: str | None = None,
        operation: str | None = None,
    ) -> int:
        query = self.db_session.query(PersonalAiwikiJob)
        if owner_user_id is not None:
            query = query.filter(PersonalAiwikiJob.owner_user_id == owner_user_id)
        if status is not None:
            query = query.filter(PersonalAiwikiJob.status == status)
        if operation is not None:
            query = query.filter(PersonalAiwikiJob.operation == operation)
        return query.count()

    def upsert_from_payload(self, payload: dict[str, Any]) -> PersonalAiwikiJob:
        job = self.get(str(payload["id"]))
        if job is None:
            job = PersonalAiwikiJob(
                id=str(payload["id"]),
                workdir=str(payload["workdir"]),
                workspace_dir=str(payload["workspace_dir"]),
            )
            self.db_session.add(job)
        self.apply_payload(job, payload)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def update(self, job_id: str, **fields: Any) -> PersonalAiwikiJob | None:
        job = self.get(job_id)
        if job is None:
            return None
        payload = {
            "id": job.id,
            "owner_user_id": fields.get("owner_user_id", job.owner_user_id),
            "status": fields.get("status", job.status),
            "operation": fields.get("operation", job.operation),
            "title": fields.get("title", job.title),
            "description": fields.get("description", job.description),
            "message": fields.get("message", job.message),
            "workdir": fields.get("workdir", job.workdir),
            "workspace_dir": fields.get("workspace_dir", job.workspace_dir),
            "input_text": fields.get("input_text", job.input_text),
            "files": fields.get("files", job.files_json),
            "summary": fields.get("summary", job.summary_json),
            "answer_markdown": fields.get("answer_markdown", job.answer_markdown),
            "created_at": fields.get("created_at", job.created_at),
            "started_at": fields.get("started_at", job.started_at),
            "finished_at": fields.get("finished_at", job.finished_at),
        }
        self.apply_payload(job, payload)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def delete(self, job: PersonalAiwikiJob) -> None:
        self.db_session.delete(job)
        self.db_session.commit()

    def apply_payload(self, job: PersonalAiwikiJob, payload: dict[str, Any]) -> None:
        if "owner_user_id" in payload:
            job.owner_user_id = _coerce_int(payload.get("owner_user_id"))
        job.status = str(payload.get("status") or job.status or "queued")
        job.operation = str(payload.get("operation") or job.operation or "ingest")
        job.title = payload.get("title")
        job.description = payload.get("description")
        job.message = payload.get("message")
        job.workdir = str(payload.get("workdir") or job.workdir)
        job.workspace_dir = str(payload.get("workspace_dir") or job.workspace_dir)
        job.input_text = payload.get("input_text")
        job.files_json = _json_string(payload.get("files_json") or payload.get("files") or [])
        summary = payload.get("summary_json")
        if summary is None:
            summary = payload.get("summary")
        job.summary_json = None if summary is None else _json_string(summary)
        job.answer_markdown = payload.get("answer_markdown")
        job.created_at = _coerce_datetime(payload.get("created_at")) or job.created_at
        job.started_at = _coerce_datetime(payload.get("started_at"))
        job.finished_at = _coerce_datetime(payload.get("finished_at"))
        job.updated_at = datetime.now(timezone.utc)

    def owner_username(self, owner_user_id: int | None) -> str | None:
        if owner_user_id is None:
            return None
        user = self.db_session.query(User).filter(User.id == owner_user_id).first()
        return user.username if user else None


def _coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)
