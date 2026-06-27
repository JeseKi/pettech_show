# -*- coding: utf-8 -*-
"""Access helpers for Personal AI Wiki jobs."""

from __future__ import annotations

import re
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ..dao import PersonalAiwikiJobDAO
from ..models import PersonalAiwikiJob


def get_accessible_job(db: Session, job_id: str, current_user: User) -> PersonalAiwikiJob:
    if not re.fullmatch(r"\d{14}_[a-f0-9]{8}_personal_aiwiki", job_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    job = PersonalAiwikiJobDAO(db).get(job_id)
    if job is None or not can_access_job(current_user, job.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    if not (Path(job.workdir) / "manifest.json").exists():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="任务不存在")
    return job


def can_access_job(user: User, owner_user_id: int | None) -> bool:
    return owner_user_id == user.id or is_admin(user)


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN
