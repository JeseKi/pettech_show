# -*- coding: utf-8 -*-
"""Core planning and upload orchestration for Info Distribution."""

from __future__ import annotations

import secrets
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..dao import DistributionUploadDAO, history_key, parse_json_dict
from ..models import DistributionUploadJob
from ..schemas import DistributionUploadJobListOut, DistributionUploadJobSummaryOut, DistributionUploadRequest
from .accounts import account_summary, filter_accounts, public_project, public_theme, validate_project_theme
from .remote import remote_base_url, upload_batches
from .sources import UploadSource, collect_upload_sources, upload_type_for_source


def build_upload_plan(
    db: Session,
    *,
    payload: DistributionUploadRequest,
    account_directory: list[dict[str, Any]],
    project_theme_directory: dict[str, Any],
) -> dict[str, Any]:
    upload_type = upload_type_for_source(payload.source_type)
    project, theme = validate_project_theme(
        project_theme_directory, payload.project_id, payload.theme_id
    )
    accounts = filter_accounts(
        account_directory,
        upload_type=upload_type,
        project_id=payload.project_id,
        theme_id=payload.theme_id,
        platforms=payload.account_platforms,
        account_query=payload.account_query,
        user_query=payload.user_query,
        account_ids=payload.account_ids,
    )
    if not accounts:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有匹配项目、主题、类型、启用状态和账号筛选条件的账号",
        )

    sources = collect_upload_sources(
        db, source_type=payload.source_type, source_job_id=payload.source_job_id
    )
    if not sources:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="没有可上传的本地产物",
        )

    uploaded_keys = (
        set()
        if payload.ignore_history
        else DistributionUploadDAO(db).successful_history_keys(
            source_type=payload.source_type,
            source_job_id=payload.source_job_id,
            upload_type=upload_type,
            project_id=payload.project_id,
            theme_id=payload.theme_id,
            scheduled_date=payload.scheduled_date,
        )
    )

    requested = len(accounts) * payload.per_account_count
    warnings: list[str] = []
    if requested > len(sources):
        warnings.append(
            f"本次计划需要 {requested} 个上传项，但当前任务只有 {len(sources)} 个可用来源"
        )

    batches: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    source_index = 0
    for account in accounts:
        articles: list[dict[str, Any]] = []
        summary_items: list[dict[str, Any]] = []
        while len(articles) < payload.per_account_count and source_index < len(sources):
            source = sources[source_index]
            source_index += 1
            item_history_key = history_key(
                scheduled_date=payload.scheduled_date,
                account_id=account.id,
                project_id=payload.project_id,
                theme_id=payload.theme_id,
                source_key=source.source_key,
            )
            if item_history_key in uploaded_keys:
                skipped.append(
                    {
                        "account": account_summary(account),
                        "source_key": source.source_key,
                        "source_label": source.source_label,
                        "title": source.title,
                        "reason": "已上传过，默认跳过",
                    }
                )
                continue

            upload_item = _upload_item_for_source(
                source,
                upload_type=upload_type,
                origin_source_type=payload.source_type,
                origin_source_job_id=payload.source_job_id,
                account=account_summary(account),
                scheduled_date=payload.scheduled_date.isoformat(),
                project=project,
                theme=theme,
                project_id=payload.project_id,
                theme_id=payload.theme_id,
            )
            articles.append(upload_item)
            summary_items.append(
                {
                    **upload_item,
                    "source_key": source.source_key,
                    "source_label": source.source_label,
                    "source_path": source.source_path,
                    "content_sha256": source.content_sha256,
                }
            )

        if articles:
            batches.append(
                {
                    "account": account_summary(account),
                    "payload": {"account_id": account.id, "articles": articles},
                    "items": summary_items,
                    "article_count": len(summary_items),
                }
            )

    if source_index < len(sources):
        warnings.append(f"还有 {len(sources) - source_index} 个可用来源未分配")

    return {
        "source_type": payload.source_type,
        "source_job_id": payload.source_job_id,
        "upload_type": upload_type,
        "scheduled_date": payload.scheduled_date,
        "project": public_project(project),
        "theme": public_theme(theme),
        "account_count": len(accounts),
        "batch_count": len(batches),
        "item_count": sum(len(batch["items"]) for batch in batches),
        "skipped": skipped,
        "warnings": warnings,
        "batches": batches,
    }


def create_upload_job(
    db: Session,
    *,
    payload: DistributionUploadRequest,
    plan: dict[str, Any],
    current_user: User,
) -> DistributionUploadJob:
    now = datetime.now(timezone.utc)
    return DistributionUploadDAO(db).create_job(
        job_id=_new_upload_job_id(now),
        owner_user_id=current_user.id,
        source_type=payload.source_type,
        source_job_id=payload.source_job_id,
        upload_type=str(plan["upload_type"]),
        project_id=payload.project_id,
        theme_id=payload.theme_id,
        scheduled_date=payload.scheduled_date,
        remote_base_url=remote_base_url(),
        plan=_public_plan(plan),
        created_at=now,
    )


async def upload_plan_to_remote(
    db: Session, *, job: DistributionUploadJob, plan: dict[str, Any]
) -> tuple[DistributionUploadJob, dict[str, Any]]:
    dao = DistributionUploadDAO(db)
    try:
        results = await upload_batches(plan)
    except HTTPException as exc:
        failed_result: dict[str, Any] = {"status": "failed", "error": exc.detail}
        dao.mark_job_failed(job, result=failed_result, message=str(exc.detail))
        raise

    result: dict[str, Any] = {"status": "completed", "results": results}
    records = _success_records(plan, results)
    dao.add_success_items(job=job, records=records)
    completed = dao.mark_job_completed(
        job,
        result=result,
        message=f"上传完成，共创建 {len(records)} 篇内容",
    )
    return completed, result


def list_upload_jobs(
    db: Session, *, limit: int, offset: int
) -> DistributionUploadJobListOut:
    jobs, total = DistributionUploadDAO(db).list_jobs(limit=limit, offset=offset)
    return DistributionUploadJobListOut(
        items=[job_summary(job) for job in jobs],
        total=total,
        limit=limit,
        offset=offset,
    )


def job_summary(job: DistributionUploadJob) -> DistributionUploadJobSummaryOut:
    return DistributionUploadJobSummaryOut(
        id=job.id,
        owner_user_id=job.owner_user_id,
        source_type=job.source_type,
        source_job_id=job.source_job_id,
        upload_type=job.upload_type,
        project_id=job.project_id,
        theme_id=job.theme_id,
        scheduled_date=job.scheduled_date,
        status=job.status,  # type: ignore[arg-type]
        message=job.message,
        remote_base_url=job.remote_base_url,
        plan=parse_json_dict(job.plan_json),
        result=parse_json_dict(job.result_json),
        created_at=job.created_at,
        finished_at=job.finished_at,
    )


def _upload_item_for_source(
    source: UploadSource,
    *,
    upload_type: str,
    origin_source_type: str,
    origin_source_job_id: str,
    account: dict[str, Any],
    scheduled_date: str,
    project: dict[str, Any],
    theme: dict[str, Any],
    project_id: int,
    theme_id: int,
) -> dict[str, Any]:
    metadata = dict(source.metadata)
    article_metadata = metadata.get("article")
    article = article_metadata if isinstance(article_metadata, dict) else {}
    metadata.update(
        {
            "article_role": article.get("role") or source.source_label,
            "summary": article.get("summary") or metadata.get("summary"),
            "tags": article.get("tags") or metadata.get("tags") or [],
            "upload_context": {
                "source_system": "pettech_show",
                "distribution_type": upload_type,
                "source_type": origin_source_type,
                "source_job_id": origin_source_job_id,
                "source_key": source.source_key,
                "source_label": source.source_label,
                "source_path": source.source_path,
                "content_sha256": source.content_sha256,
                "scheduled_date": scheduled_date,
                "project_id": project_id,
                "project_name": project.get("name"),
                "project_code": project.get("code"),
                "theme_id": theme_id,
                "theme_name": theme.get("name"),
                "account_id": account.get("id"),
                "account_name": account.get("account_name"),
                "platform": account.get("platform"),
            },
        }
    )
    return {
        "title": source.title,
        "keyword": source.keyword or "无",
        "markdown_content": source.markdown_content,
        "scheduled_date": scheduled_date,
        "project_id": project_id,
        "metadata": metadata,
    }


def _public_plan(plan: dict[str, Any]) -> dict[str, Any]:
    return {
        **plan,
        "scheduled_date": _string_date(plan["scheduled_date"]),
        "batches": [
            {
                "account": batch["account"],
                "items": [
                    {
                        "source_key": item["source_key"],
                        "source_label": item["source_label"],
                        "source_path": item.get("source_path"),
                        "title": item["title"],
                        "keyword": item.get("keyword") or "无",
                        "content_sha256": item["content_sha256"],
                    }
                    for item in batch["items"]
                ],
                "article_count": len(batch["items"]),
            }
            for batch in plan["batches"]
        ],
    }


def _success_records(
    plan: dict[str, Any], results: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for batch, result in zip(plan["batches"], results):
        response = result.get("response") if isinstance(result, dict) else None
        response_items = response if isinstance(response, list) else []
        for index, item in enumerate(batch["items"]):
            response_item = response_items[index] if index < len(response_items) else None
            records.append(
                {
                    "account_id": batch["account"]["id"],
                    "source_key": item["source_key"],
                    "source_label": item["source_label"],
                    "title": item["title"],
                    "content_sha256": item["content_sha256"],
                    "remote_article_id": response_item.get("id")
                    if isinstance(response_item, dict)
                    else None,
                    "response": response_item,
                }
            )
    return records


def _new_upload_job_id(now: datetime) -> str:
    return f"{now.strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(4)}_distribution"


def _string_date(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)
