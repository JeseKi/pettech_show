# -*- coding: utf-8 -*-
"""Social card video record synchronization and recovery."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from loguru import logger
from sqlalchemy.orm import Session

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import progress_marked_complete
from src.server.config import global_config

from ...dao import SocialCardVideoJobDAO
from ...models import SocialCardVideoJob
from ...parser import parse_social_card_video_result
from ...queue_state import get_queue
from ..persistence import (
    coerce_datetime,
    coerce_int,
    json_string,
    read_manifest,
    update_job,
    write_manifest,
)


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = SocialCardVideoJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_social_card_videos/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Social Card Videos manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = SocialCardVideoJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_social_card_job_id=str(manifest["source_social_card_job_id"]),
            title=_normalize_title(manifest.get("title")),
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


def reconcile_orphaned_finished_job(db: Session, job: SocialCardVideoJob) -> SocialCardVideoJob:
    if job.status not in {"queued", "running"}:
        return job
    if get_queue().queue_position(job.id) is not None:
        return job
    workdir = Path(job.workdir)
    if not progress_marked_complete(workdir):
        return job
    try:
        result = parse_social_card_video_result(
            job_id=job.id,
            source_social_card_job_id=job.source_social_card_job_id,
            workdir=workdir,
        )
    except Exception as exc:
        logger.warning("跳过 Social Card Videos 孤儿任务收尾 {}: {}", job.id, exc)
        return job
    summary = {
        **result.summary,
        "video_count": len(result.videos),
        "status": "completed",
    }
    append_log(workdir, "RECOVERY: progress.json 已完成，补写轮播视频任务状态。")
    update_job(
        db,
        job.id,
        status="completed",
        message="轮播视频生成完成",
        summary=summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    reconciled = SocialCardVideoJobDAO(db).get(job.id) or job
    write_manifest(workdir, reconciled)
    return reconciled


def _normalize_title(value: object) -> str | None:
    if value is None:
        return None
    stripped = str(value).strip()
    return stripped or None
