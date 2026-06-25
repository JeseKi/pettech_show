# -*- coding: utf-8 -*-
"""DAO helpers for Info Distribution upload history."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO

from .models import DistributionUploadItem, DistributionUploadJob


class DistributionUploadDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create_job(
        self,
        *,
        job_id: str,
        owner_user_id: int | None,
        source_type: str,
        source_job_id: str,
        upload_type: str,
        project_id: int,
        theme_id: int,
        scheduled_date: date,
        remote_base_url: str,
        plan: dict[str, Any],
        created_at: datetime,
    ) -> DistributionUploadJob:
        job = DistributionUploadJob(
            id=job_id,
            owner_user_id=owner_user_id,
            source_type=source_type,
            source_job_id=source_job_id,
            upload_type=upload_type,
            project_id=project_id,
            theme_id=theme_id,
            scheduled_date=scheduled_date,
            status="running",
            message="正在上传到分发平台",
            remote_base_url=remote_base_url,
            plan_json=json_string(plan),
            created_at=created_at,
            updated_at=datetime.now(timezone.utc),
        )
        self.db_session.add(job)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def mark_job_completed(
        self, job: DistributionUploadJob, *, result: dict[str, Any], message: str
    ) -> DistributionUploadJob:
        job.status = "completed"
        job.message = message
        job.result_json = json_string(result)
        job.finished_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def mark_job_failed(
        self, job: DistributionUploadJob, *, result: dict[str, Any], message: str
    ) -> DistributionUploadJob:
        job.status = "failed"
        job.message = message
        job.result_json = json_string(result)
        job.finished_at = datetime.now(timezone.utc)
        job.updated_at = datetime.now(timezone.utc)
        self.db_session.commit()
        self.db_session.refresh(job)
        return job

    def add_success_items(
        self,
        *,
        job: DistributionUploadJob,
        records: list[dict[str, Any]],
    ) -> list[DistributionUploadItem]:
        items: list[DistributionUploadItem] = []
        now = datetime.now(timezone.utc)
        for record in records:
            item = DistributionUploadItem(
                upload_job_id=job.id,
                owner_user_id=job.owner_user_id,
                source_type=job.source_type,
                source_job_id=job.source_job_id,
                source_key=str(record["source_key"]),
                source_label=str(record.get("source_label") or record["source_key"]),
                content_sha256=str(record["content_sha256"]),
                upload_type=job.upload_type,
                account_id=int(record["account_id"]),
                project_id=job.project_id,
                theme_id=job.theme_id,
                scheduled_date=job.scheduled_date,
                title=str(record["title"]),
                status="success",
                remote_article_id=coerce_int(record.get("remote_article_id")),
                response_json=json_string(record.get("response")),
                created_at=now,
                updated_at=now,
            )
            self.db_session.add(item)
            items.append(item)
        self.db_session.commit()
        for item in items:
            self.db_session.refresh(item)
        return items

    def successful_history_keys(
        self,
        *,
        source_type: str,
        source_job_id: str,
        upload_type: str,
        project_id: int,
        theme_id: int,
        scheduled_date: date,
    ) -> set[str]:
        rows = (
            self.db_session.query(DistributionUploadItem)
            .filter(
                DistributionUploadItem.source_type == source_type,
                DistributionUploadItem.source_job_id == source_job_id,
                DistributionUploadItem.upload_type == upload_type,
                DistributionUploadItem.project_id == project_id,
                DistributionUploadItem.theme_id == theme_id,
                DistributionUploadItem.scheduled_date == scheduled_date,
                DistributionUploadItem.status == "success",
            )
            .all()
        )
        return {
            history_key(
                scheduled_date=item.scheduled_date,
                account_id=item.account_id,
                project_id=item.project_id,
                theme_id=item.theme_id,
                source_key=item.source_key,
            )
            for item in rows
        }

    def list_jobs(self, *, limit: int, offset: int) -> tuple[list[DistributionUploadJob], int]:
        query = self.db_session.query(DistributionUploadJob)
        total = query.count()
        jobs = (
            query.order_by(
                DistributionUploadJob.created_at.desc(),
                DistributionUploadJob.id.desc(),
            )
            .offset(offset)
            .limit(limit)
            .all()
        )
        return jobs, total


def history_key(
    *,
    scheduled_date: date,
    account_id: int,
    project_id: int,
    theme_id: int,
    source_key: str,
) -> str:
    return "\t".join(
        [
            scheduled_date.isoformat(),
            str(account_id),
            str(project_id),
            str(theme_id),
            source_key,
        ]
    )


def parse_json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def json_string(value: Any) -> str:
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None

