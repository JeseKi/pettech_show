# -*- coding: utf-8 -*-
"""Daily writer job DAO."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.dao.dao_base import BaseDAO

from .models import DailyWriterJob


class DailyWriterJobDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create(
        self,
        *,
        job_id: str,
        owner_user_id: int | None,
        source_seed_matrix_job_id: str,
        source_aiwiki_job_id: str,
        seed_id: str,
        workdir: str,
        row: dict[str, str],
        params: dict[str, Any],
        created_at: datetime,
    ) -> DailyWriterJob:
        job = DailyWriterJob(
            id=job_id,
            owner_user_id=owner_user_id,
            source_seed_matrix_job_id=source_seed_matrix_job_id,
            source_aiwiki_job_id=source_aiwiki_job_id,
            seed_id=seed_id,
            status="queued",
            message="任务已进入队列",
            workdir=workdir,
            row_json=json_string(row),
            params_json=json_string(params),
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self.db_session.add(job)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def get(self, job_id: str) -> DailyWriterJob | None:
        return (
            self.db_session.query(DailyWriterJob)
            .populate_existing()
            .filter(DailyWriterJob.id == job_id)
            .first()
        )

    def list(
        self,
        *,
        limit: int,
        offset: int,
        owner_user_id: int | None = None,
        source_seed_matrix_job_id: str | None = None,
    ) -> list[DailyWriterJob]:
        query = self.db_session.query(DailyWriterJob)
        if owner_user_id is not None:
            query = query.filter(DailyWriterJob.owner_user_id == owner_user_id)
        if source_seed_matrix_job_id:
            query = query.filter(
                DailyWriterJob.source_seed_matrix_job_id == source_seed_matrix_job_id
            )
        return (
            query.order_by(DailyWriterJob.created_at.desc(), DailyWriterJob.id.desc())
            .offset(offset)
            .limit(limit)
            .all()
        )

    def count(
        self,
        *,
        owner_user_id: int | None = None,
        source_seed_matrix_job_id: str | None = None,
    ) -> int:
        query = self.db_session.query(DailyWriterJob)
        if owner_user_id is not None:
            query = query.filter(DailyWriterJob.owner_user_id == owner_user_id)
        if source_seed_matrix_job_id:
            query = query.filter(
                DailyWriterJob.source_seed_matrix_job_id == source_seed_matrix_job_id
            )
        return query.count()

    def update(self, job_id: str, **fields: Any) -> DailyWriterJob:
        job = self.get(job_id)
        if job is None:
            raise ValueError("任务不存在")
        if "status" in fields:
            job.status = str(fields["status"])
        if "message" in fields:
            job.message = fields["message"]
        if "article_path" in fields:
            job.article_path = fields["article_path"]
        if "metadata_path" in fields:
            job.metadata_path = fields["metadata_path"]
        if "summary" in fields:
            job.summary_json = json_string(fields["summary"])
        if "started_at" in fields:
            job.started_at = coerce_datetime(fields["started_at"])
        if "finished_at" in fields:
            job.finished_at = coerce_datetime(fields["finished_at"])
        job.updated_at = datetime.now(timezone.utc)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def delete(self, job: DailyWriterJob) -> None:
        self.db_session.delete(job)
        self.db_session.commit()

    def owner_username(self, owner_user_id: int | None) -> str | None:
        if owner_user_id is None:
            return None
        user = self.db_session.query(User).filter(User.id == owner_user_id).first()
        return user.username if user else None


def parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def parse_json_str_dict(value: str | None) -> dict[str, str]:
    parsed = parse_json_dict(value)
    return {str(key): str(item or "") for key, item in parsed.items()}


def json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def coerce_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None

