# -*- coding: utf-8 -*-
"""Daily writer job deletion helpers."""

from __future__ import annotations

import shutil
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ...dao import DailyWriterJobDAO
from ..persistence import get_accessible_job


def delete_job(db: Session, job_id: str, current_user: User) -> None:
    job = get_accessible_job(db, job_id, current_user)
    if job.status in {"queued", "running"}:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="任务正在执行，完成或失败后才能删除",
        )
    workdir = Path(job.workdir)
    from src.server.social_cards.service import delete_child_jobs_for_daily_writer

    delete_child_jobs_for_daily_writer(db, job.id)
    DailyWriterJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def delete_child_jobs_for_seed_matrix(db: Session, source_seed_matrix_job_id: str) -> None:
    dao = DailyWriterJobDAO(db)
    children = dao.list(
        limit=1000,
        offset=0,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
    )
    active = [job for job in children if job.status in {"queued", "running"}]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该选题矩阵仍有关联的长文生成任务正在执行",
        )
    for child in children:
        child_workdir = Path(child.workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)
