# -*- coding: utf-8 -*-
"""Social card video job creation."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.social_cards.service.persistence import get_accessible_job as get_social_card_job

from ...dao import SocialCardVideoJobDAO
from ...queue_state import get_queue
from ...schemas import SocialCardVideoJobOut
from ..artifacts import copy_source_cards, prepare_skill, save_bgm_upload, write_video_config
from ..persistence import build_session_factory, job_workdir, new_job_id, write_manifest
from ..serializers import job_out_from_model
from .runner import run_job


async def create_job(
    db: Session,
    *,
    source_social_card_job_id: str,
    title: str,
    voice_text: str,
    bgm_start: float,
    bgm_file: UploadFile | None,
    current_user: User,
) -> SocialCardVideoJobOut:
    source_job = get_social_card_job(db, source_social_card_job_id, current_user)
    if source_job.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能基于已完成的图文卡任务生成轮播视频",
    )
    if not title.strip():
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="标题不能为空")

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    from src.server.aiwiki.service.progress import initial_progress, write_progress

    write_progress(workdir, initial_progress())
    deck_specs = copy_source_cards(source_job, workdir)
    prepare_skill(workdir)
    bgm_path = await save_bgm_upload(workdir, bgm_file)
    config = write_video_config(
        workdir,
        deck_specs=deck_specs,
        title=title,
        voice_text=voice_text,
        bgm_path=bgm_path,
        bgm_start=bgm_start,
    )
    params = {
        "title": title,
        "voice_text": voice_text,
        "bgm_start": max(0.0, float(bgm_start)),
        "has_bgm": bgm_path is not None,
        "bgm_path": bgm_path,
        "video_count": len(deck_specs),
        "config": config,
    }
    job = SocialCardVideoJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_social_card_job_id=source_job.id,
        workdir=workdir.as_posix(),
        params=params,
        created_at=now,
        title=title.strip(),
    )
    write_manifest(workdir, job)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)
