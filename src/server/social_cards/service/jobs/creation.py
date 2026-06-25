# -*- coding: utf-8 -*-
"""Social card job creation."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.daily_writer.service.persistence import get_accessible_job as get_daily_writer_job

from ...dao import SocialCardJobDAO
from ...queue_state import get_queue
from ...schemas import SocialCardCreate, SocialCardJobOut
from ..artifacts import copy_source_article, prepare_skill
from ..constants import MAX_SOCIAL_CARD_COUNT, MAX_SOCIAL_POST_COUNT
from ..persistence import build_session_factory, job_workdir, new_job_id, write_manifest
from ..serializers import job_out_from_model
from .runner import run_job


def create_job(
    db: Session, payload: SocialCardCreate, current_user: User
) -> SocialCardJobOut:
    source_job = get_daily_writer_job(db, payload.source_daily_writer_job_id, current_user)
    if source_job.status not in {"completed", "partial_failed"}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能基于已完成的稿件任务生成图文卡",
        )

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    from src.server.aiwiki.service.progress import initial_progress, write_progress

    write_progress(workdir, initial_progress())
    copy_source_article(source_job, workdir)
    prepare_skill(workdir)
    params = {
        "post_count": payload.post_count,
        "cards_per_post": payload.cards_per_post,
        "card_count": payload.cards_per_post,
        "max_social_card_count": MAX_SOCIAL_CARD_COUNT,
        "max_social_post_count": MAX_SOCIAL_POST_COUNT,
    }
    job = SocialCardJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_daily_writer_job_id=source_job.id,
        workdir=workdir.as_posix(),
        params=params,
        created_at=now,
    )
    write_manifest(workdir, job)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)
