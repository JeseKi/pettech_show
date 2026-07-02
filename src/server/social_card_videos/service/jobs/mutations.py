# -*- coding: utf-8 -*-
"""Social card video job deletion helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.opencode.tmux import kill_tmux_sessions_for_workdir

from ...dao import SocialCardVideoJobDAO
from ...queue_state import get_queue
from ...schemas import SocialCardVideoJobOut, SocialCardVideoJobUpdate
from ..persistence import get_accessible_job, write_manifest
from ..serializers import job_out_from_model


def update_job_title(
    db: Session, job_id: str, payload: SocialCardVideoJobUpdate, current_user: User
) -> SocialCardVideoJobOut:
    job = get_accessible_job(db, job_id, current_user)
    updated = SocialCardVideoJobDAO(db).update(job.id, title=_normalize_title(payload.title))
    write_manifest(Path(updated.workdir), updated)
    return job_out_from_model(
        updated,
        SocialCardVideoJobDAO(db).owner_username(updated.owner_user_id),
    )


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    get_queue().cancel(job.id)
    kill_tmux_sessions_for_workdir(workdir)
    SocialCardVideoJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def delete_child_jobs_for_social_card(db: Session, source_social_card_job_id: str) -> None:
    dao = SocialCardVideoJobDAO(db)
    children = dao.list(
        limit=1000,
        offset=0,
        source_social_card_job_id=source_social_card_job_id,
    )
    for child in children:
        child_workdir = Path(child.workdir)
        get_queue().cancel(child.id)
        kill_tmux_sessions_for_workdir(child_workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)


def _normalize_title(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped or None
