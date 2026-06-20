# -*- coding: utf-8 -*-
"""AI Wiki job DAO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO
from src.server.auth.models import User
from src.server.auth.schemas import UserRole

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

    def list(
        self,
        *,
        limit: int,
        offset: int,
        owner_user_id: int | None = None,
        status: str | None = None,
    ) -> list[AiwikiJob]:
        query = self.db_session.query(AiwikiJob)
        if owner_user_id is not None:
            query = query.filter(AiwikiJob.owner_user_id == owner_user_id)
        if status is not None:
            query = query.filter(AiwikiJob.status == status)
        return (
            query.order_by(AiwikiJob.created_at.desc(), AiwikiJob.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(self, *, owner_user_id: int | None = None, status: str | None = None) -> int:
        query = self.db_session.query(AiwikiJob)
        if owner_user_id is not None:
            query = query.filter(AiwikiJob.owner_user_id == owner_user_id)
        if status is not None:
            query = query.filter(AiwikiJob.status == status)
        return query.count()

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
            "owner_user_id": fields.get("owner_user_id", job.owner_user_id),
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

    def delete(self, job: AiwikiJob) -> None:
        self.db_session.delete(job)
        self.db_session.commit()

    def apply_payload(self, job: AiwikiJob, payload: dict[str, Any]) -> None:
        if "owner_user_id" in payload:
            job.owner_user_id = _coerce_int(payload.get("owner_user_id"))
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

    def default_admin_user_id(self) -> int | None:
        user = (
            self.db_session.query(User)
            .filter(User.username == "admin")
            .filter(User.role == UserRole.ADMIN)
            .first()
        )
        if user is None:
            user = (
                self.db_session.query(User)
                .filter(User.role == UserRole.ADMIN)
                .order_by(User.id.asc())
                .first()
            )
        return user.id if user else None

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
    normalized = value.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def _json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None
