# -*- coding: utf-8 -*-
"""Daily writer job creation."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.aiwiki.dao import AiwikiJobDAO
from src.server.aiwiki.service.persistence import existing_job_workdir
from src.server.auth.models import User
from src.server.seed_matrix.parser import parse_seed_matrix_result
from src.server.seed_matrix.service.permissions import can_access_job as can_access_source
from src.server.seed_matrix.service.persistence import get_accessible_job as get_seed_matrix_job

from ...dao import DailyWriterJobDAO
from ...queue_state import get_queue
from ...schemas import DailyWriterCreate, DailyWriterJobOut
from ..artifacts import copy_source_artifacts, prepare_skill
from ..constants import MAX_VARIANT_COUNT, SELECTED_SEED_ROW_PATH
from ..persistence import build_session_factory, job_workdir, new_job_id, write_manifest
from ..serializers import job_out_from_model
from .runner import run_job


def create_job(
    db: Session, payload: DailyWriterCreate, current_user: User
) -> DailyWriterJobOut:
    source_matrix = get_seed_matrix_job(db, payload.source_seed_matrix_job_id, current_user)
    _validate_source_matrix(source_matrix)
    source_aiwiki = AiwikiJobDAO(db).get(source_matrix.source_aiwiki_job_id)
    if source_aiwiki is None or not can_access_source(current_user, source_aiwiki.owner_user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="AI Wiki 任务不存在")
    if source_aiwiki.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 任务尚未完成",
        )
    matrix_result = parse_seed_matrix_result(
        job_id=source_matrix.id,
        source_aiwiki_job_id=source_matrix.source_aiwiki_job_id,
        workdir=Path(source_matrix.workdir),
        csv_path=source_matrix.result_csv_path,
    )
    row = _find_seed_row(matrix_result.rows, payload.seed_id)
    source_workdir = existing_job_workdir(source_aiwiki.id, db)
    _validate_source_assets(source_workdir)

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = _prepare_workdir(job_id, source_workdir, payload.generate_artwork)
    (workdir / SELECTED_SEED_ROW_PATH).write_text(
        json.dumps(row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    params = _job_params(payload)
    job = DailyWriterJobDAO(db).create(
        job_id=job_id,
        owner_user_id=current_user.id,
        source_seed_matrix_job_id=source_matrix.id,
        source_aiwiki_job_id=source_aiwiki.id,
        seed_id=row.get("seed_id") or payload.seed_id,
        workdir=workdir.as_posix(),
        row=row,
        params=params,
        created_at=now,
    )
    write_manifest(workdir, job)
    session_factory = build_session_factory(db)
    get_queue().enqueue(job_id, lambda: run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


def _validate_source_matrix(source_matrix) -> None:
    if source_matrix.status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只能选择已完成的选题矩阵任务",
        )
    if not source_matrix.result_csv_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源选题矩阵没有 CSV 结果",
        )


def _validate_source_assets(source_workdir: Path) -> None:
    if not (source_workdir / "material").exists() or not (source_workdir / "wiki").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 缺少 material 或 wiki 结果",
        )


def _prepare_workdir(job_id: str, source_workdir: Path, include_artwork: bool) -> Path:
    from src.server.aiwiki.service.progress import initial_progress, write_progress

    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    write_progress(workdir, initial_progress())
    copy_source_artifacts(source_workdir, workdir)
    prepare_skill(workdir, include_artwork=include_artwork)
    return workdir


def _job_params(payload: DailyWriterCreate) -> dict[str, object]:
    return {
        "output_date": payload.output_date or "",
        "generate_variants": payload.generate_variants,
        "variant_count": payload.variant_count if payload.generate_variants else 0,
        "max_variant_count": MAX_VARIANT_COUNT,
        "generate_artwork": payload.generate_artwork,
    }


def _find_seed_row(rows: list[dict[str, str]], seed_id: str) -> dict[str, str]:
    normalized = seed_id.strip()
    for row in rows:
        if row.get("seed_id", "").strip() == normalized:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"选题矩阵中不存在 seed_id：{seed_id}",
    )
