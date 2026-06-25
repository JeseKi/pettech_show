# -*- coding: utf-8 -*-
"""Social card record synchronization and recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import progress_marked_complete
from src.server.config import global_config

from ...dao import SocialCardJobDAO, parse_json_dict
from ...models import SocialCardJob
from ...parser import parse_social_card_result
from ...queue_state import get_queue
from ..persistence import (
    coerce_datetime,
    coerce_int,
    json_string,
    read_manifest,
    update_job,
    write_manifest,
)
from .validation import coerce_card_count, coerce_post_count


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = SocialCardJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_social_cards/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Social Cards manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = SocialCardJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_daily_writer_job_id=str(manifest["source_daily_writer_job_id"]),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            params_json=json_string(manifest.get("params") or {}),
            summary_json=json_string(manifest.get("summary") or {}),
            created_at=coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=coerce_datetime(manifest.get("started_at")),
            finished_at=coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def reconcile_orphaned_finished_job(db: Session, job: SocialCardJob) -> SocialCardJob:
    if job.status not in {"queued", "running"}:
        return job
    if get_queue().queue_position(job.id) is not None:
        return job
    workdir = Path(job.workdir)
    if not progress_marked_complete(workdir):
        return job
    params = parse_json_dict(job.params_json)
    expected_post_count = coerce_post_count(params.get("post_count"))
    expected_cards_per_post = coerce_card_count(
        params.get("cards_per_post", params.get("card_count"))
    )
    expected_count = expected_post_count * expected_cards_per_post
    try:
        result = parse_social_card_result(
            job_id=job.id,
            source_daily_writer_job_id=job.source_daily_writer_job_id,
            workdir=workdir,
        )
        if expected_post_count and len(result.posts) != expected_post_count:
            return job
        if expected_cards_per_post:
            if any(len(post.images) != expected_cards_per_post for post in result.posts):
                return job
        if expected_count and len(result.images) != expected_count:
            return job
    except Exception as exc:
        logger.warning("跳过 Social Cards 孤儿任务收尾 {}: {}", job.id, exc)
        return job
    summary = {
        **result.summary,
        "post_count": expected_post_count,
        "cards_per_post": expected_cards_per_post,
        "requested_count": expected_count,
        "image_count": len(result.images),
        "status": "completed",
    }
    append_log(workdir, "RECOVERY: progress.json 已完成，补写图文卡任务状态。")
    update_job(
        db,
        job.id,
        status="completed",
        message="小红书图文卡生成完成",
        summary=summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    reconciled = SocialCardJobDAO(db).get(job.id) or job
    write_manifest(workdir, reconciled)
    return reconciled
