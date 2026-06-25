# -*- coding: utf-8 -*-
"""Public daily writer job service functions."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.dao import AiwikiJobDAO
from src.server.aiwiki.service.checks import python_args, run_check_command
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.persistence import existing_job_workdir
from src.server.aiwiki.service.progress import (
    initial_progress,
    mark_progress_failure,
    mark_progress_running,
    progress_marked_complete,
    read_progress,
    write_progress,
)
from src.server.auth.models import User
from src.server.config import global_config
from src.server.seed_matrix.parser import parse_seed_matrix_result
from src.server.seed_matrix.service.permissions import can_access_job as can_access_source
from src.server.seed_matrix.service.persistence import get_accessible_job as get_seed_matrix_job

from ..dao import DailyWriterJobDAO, parse_json_dict, parse_json_str_dict
from ..models import DailyWriterJob
from ..parser import (
    parse_daily_writer_result,
    resolve_artwork_asset_path,
    resolve_result_paths,
)
from ..queue_state import get_queue
from ..schemas import (
    DailyWriterCreate,
    DailyWriterJobListOut,
    DailyWriterJobOut,
    DailyWriterResultOut,
)
from .artifacts import copy_source_artifacts, prepare_skill
from .constants import (
    MAX_VARIANT_COUNT,
    RESULT_ZIP_NAME,
    SELECTED_SEED_ROW_PATH,
)
from .opencode import (
    run_artwork_opencode,
    run_opencode,
    run_repair_opencode,
    run_variant_opencode,
)
from .permissions import is_admin
from .persistence import (
    build_session_factory,
    coerce_datetime,
    coerce_int,
    get_accessible_job,
    job_workdir,
    json_string,
    new_job_id,
    read_manifest,
    update_job,
    write_manifest,
)
from .serializers import job_out_from_model, job_summary_from_model


def create_job(
    db: Session, payload: DailyWriterCreate, current_user: User
) -> DailyWriterJobOut:
    source_matrix = get_seed_matrix_job(db, payload.source_seed_matrix_job_id, current_user)
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
    if not (source_workdir / "material").exists() or not (source_workdir / "wiki").exists():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="源 AI Wiki 缺少 material 或 wiki 结果",
        )

    now = datetime.now(timezone.utc)
    job_id = new_job_id(now)
    workdir = job_workdir(job_id)
    (workdir / "logs").mkdir(parents=True, exist_ok=False)
    (workdir / "input").mkdir(parents=True, exist_ok=True)
    write_progress(workdir, initial_progress())
    copy_source_artifacts(source_workdir, workdir)
    prepare_skill(workdir, include_artwork=payload.generate_artwork)

    (workdir / SELECTED_SEED_ROW_PATH).write_text(
        json.dumps(row, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    params = {
        "output_date": payload.output_date or "",
        "generate_variants": payload.generate_variants,
        "variant_count": payload.variant_count if payload.generate_variants else 0,
        "max_variant_count": MAX_VARIANT_COUNT,
        "generate_artwork": payload.generate_artwork,
    }
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
    get_queue().enqueue(job_id, lambda: _run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    source_seed_matrix_job_id: str | None = None,
) -> DailyWriterJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = DailyWriterJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
    )
    jobs = [_reconcile_orphaned_finished_job(db, job) for job in jobs]
    return DailyWriterJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(
            owner_user_id=owner_filter,
            source_seed_matrix_job_id=source_seed_matrix_job_id,
        ),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> DailyWriterJobOut:
    job = get_accessible_job(db, job_id, current_user)
    job = _reconcile_orphaned_finished_job(db, job)
    return job_out_from_model(job, DailyWriterJobDAO(db).owner_username(job.owner_user_id))


def get_result(
    db: Session, job_id: str, current_user: User
) -> DailyWriterResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=Path(job.workdir),
            article_path=job.article_path,
            metadata_path=job.metadata_path,
        )
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    result = get_result(db, job_id, current_user)
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    zip_path = workdir / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.write(workdir / result.article_path, arcname="main.md")
        archive.write(workdir / result.metadata_path, arcname="metadata.json")
        variants_root = Path(result.metadata_path).parent / "variants"
        if (workdir / variants_root).is_dir():
            for path in sorted((workdir / variants_root).rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(workdir / variants_root.parent).as_posix())
        artwork_root = Path(result.metadata_path).parent / "artwork"
        if (workdir / artwork_root).is_dir():
            for path in sorted((workdir / artwork_root).rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(workdir / artwork_root.parent).as_posix())
    return zip_path


def artwork_file(
    db: Session,
    job_id: str,
    asset_key: str,
    current_user: User,
) -> tuple[Path, str]:
    job = get_accessible_job(db, job_id, current_user)
    if job.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        _, metadata_path = resolve_result_paths(
            Path(job.workdir),
            article_path=job.article_path,
            metadata_path=job.metadata_path,
        )
        return resolve_artwork_asset_path(
            job_id=job.id,
            workdir=Path(job.workdir),
            article_dir=metadata_path.parent,
            asset_key=asset_key,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


def sync_job_records(db: Session) -> None:
    data_root = Path(global_config.project_root) / "data"
    if not data_root.exists():
        return
    dao = DailyWriterJobDAO(db)
    for manifest_path in sorted(data_root.glob("*_daily_writer/manifest.json")):
        workdir = manifest_path.parent
        try:
            manifest = read_manifest(workdir)
        except Exception as exc:
            logger.warning("跳过无法读取的 Daily Writer manifest {}: {}", manifest_path, exc)
            continue
        if dao.get(str(manifest.get("id"))) is not None:
            continue
        job = DailyWriterJob(
            id=str(manifest["id"]),
            owner_user_id=coerce_int(manifest.get("owner_user_id")),
            source_seed_matrix_job_id=str(manifest["source_seed_matrix_job_id"]),
            source_aiwiki_job_id=str(manifest["source_aiwiki_job_id"]),
            seed_id=str(manifest["seed_id"]),
            status=str(manifest.get("status") or "failed"),
            message=manifest.get("message"),
            workdir=workdir.as_posix(),
            row_json=json_string(manifest.get("row") or {}),
            params_json=json_string(manifest.get("params") or {}),
            article_path=manifest.get("article_path"),
            metadata_path=manifest.get("metadata_path"),
            summary_json=json_string(manifest.get("summary") or {}),
            created_at=coerce_datetime(manifest.get("created_at")) or datetime.now(timezone.utc),
            started_at=coerce_datetime(manifest.get("started_at")),
            finished_at=coerce_datetime(manifest.get("finished_at")),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(job)
        db.commit()


def _run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = DailyWriterJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成长文",
            started_at=started_at.isoformat(),
        )
        job = DailyWriterJobDAO(session).get(job_id)
        if job is None:
            return
        workdir = Path(job.workdir)
        write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        params = parse_json_dict(job.params_json)
        main_progress_events = _progress_events_snapshot(workdir)
        try:
            run_opencode(
                workdir,
                params,
                parse_json_str_dict(job.row_json),
            )
        finally:
            _ensure_progress_events_preserved(workdir, main_progress_events, "长文生成")
        if not progress_marked_complete(workdir):
            raise RuntimeError("progress.json 未写入任务完成标记")
        _run_daily_writer_json_check_with_repair(workdir)

        result = parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=workdir,
            article_path=None,
            metadata_path=None,
            write_artwork_assets=True,
        )

        generate_variants = bool(params.get("generate_variants"))
        variant_count = _coerce_variant_count(params.get("variant_count"))
        if generate_variants:
            try:
                update_job(
                    session,
                    job_id,
                    status="running",
                    message="OpenCode 正在生成长文变体",
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    summary={
                        **result.summary,
                        "variant_requested_count": variant_count,
                        "variant_failed_count": 0,
                        "variant_status": "running",
                    },
                )
                write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
                mark_progress_running(
                    workdir,
                    step="生成长文变体",
                    summary="长文已生成，正在生成长文变体",
                )
                variant_progress_events = _progress_events_snapshot(workdir)
                try:
                    run_variant_opencode(
                        workdir,
                        article_dir=Path(result.metadata_path).parent.as_posix(),
                        variant_count=variant_count,
                    )
                finally:
                    _ensure_progress_events_preserved(
                        workdir, variant_progress_events, "长文变体生成"
                    )
                if not progress_marked_complete(workdir):
                    raise RuntimeError("progress.json 未写入变体任务完成标记")
                _run_daily_writer_json_check_with_repair(
                    workdir,
                    article_dir=Path(result.metadata_path).parent.as_posix(),
                    include_variants=True,
                )
                result = parse_daily_writer_result(
                    job_id=job.id,
                    source_seed_matrix_job_id=job.source_seed_matrix_job_id,
                    source_aiwiki_job_id=job.source_aiwiki_job_id,
                    seed_id=job.seed_id,
                    workdir=workdir,
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    write_artwork_assets=True,
                )
                if len(result.variants) < variant_count:
                    raise RuntimeError(
                        f"变体生成数量不足：期望 {variant_count} 篇，实际 {len(result.variants)} 篇"
                    )
                result.summary.update(
                    {
                        "variant_requested_count": variant_count,
                        "variant_success_count": len(result.variants),
                        "variant_failed_count": 0,
                        "variant_status": "completed",
                    }
                )
            except Exception as variant_exc:
                logger.exception("Daily writer variant generation failed: {}", job_id)
                append_log(Path(job.workdir), f"VARIANT ERROR: {variant_exc}")
                mark_progress_failure(Path(job.workdir), f"长文变体生成失败：{variant_exc}")
                result.summary.update(
                    {
                        "variant_requested_count": variant_count,
                        "variant_success_count": len(result.variants),
                        "variant_failed_count": max(variant_count - len(result.variants), 1),
                        "variant_status": "failed",
                        "variant_error": str(variant_exc),
                    }
                )
                update_job(
                    session,
                    job_id,
                    status="partial_failed",
                    message=f"长文已生成，变体生成失败：{variant_exc}",
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    summary=result.summary,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
                return
        else:
            result.summary.update(
                {
                    "variant_requested_count": 0,
                    "variant_failed_count": 0,
                    "variant_status": "not_requested",
                }
            )

        generate_artwork = bool(params.get("generate_artwork"))
        if generate_artwork:
            try:
                update_job(
                    session,
                    job_id,
                    status="running",
                    message="OpenCode 正在生成封面和插图",
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    summary={
                        **result.summary,
                        "artwork_status": "running",
                        "artwork_cover_count": 0,
                        "artwork_inline_count": 0,
                    },
                )
                write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
                mark_progress_running(
                    workdir,
                    step="生成封面插图",
                    summary="长文已生成，正在生成封面和插图",
                )
                artwork_progress_events = _progress_events_snapshot(workdir)
                try:
                    run_artwork_opencode(
                        workdir,
                        article_dir=Path(result.metadata_path).parent.as_posix(),
                    )
                finally:
                    _ensure_progress_events_preserved(
                        workdir, artwork_progress_events, "封面插图生成"
                    )
                if not progress_marked_complete(workdir):
                    raise RuntimeError("progress.json 未写入封面插图任务完成标记")
                result = parse_daily_writer_result(
                    job_id=job.id,
                    source_seed_matrix_job_id=job.source_seed_matrix_job_id,
                    source_aiwiki_job_id=job.source_aiwiki_job_id,
                    seed_id=job.seed_id,
                    workdir=workdir,
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    write_artwork_assets=True,
                )
                if not result.artwork.cover_images or not result.artwork.inline_images:
                    raise RuntimeError("封面或正文插图生成数量不足")
                result.summary.update(
                    {
                        "artwork_status": "completed",
                        "artwork_cover_count": len(result.artwork.cover_images),
                        "artwork_inline_count": len(result.artwork.inline_images),
                    }
                )
            except Exception as artwork_exc:
                logger.exception("Daily writer artwork generation failed: {}", job_id)
                append_log(Path(job.workdir), f"ARTWORK ERROR: {artwork_exc}")
                mark_progress_failure(Path(job.workdir), f"封面插图生成失败：{artwork_exc}")
                result.summary.update(
                    {
                        "artwork_status": "failed",
                        "artwork_error": str(artwork_exc),
                        "artwork_cover_count": len(result.artwork.cover_images),
                        "artwork_inline_count": len(result.artwork.inline_images),
                    }
                )
                update_job(
                    session,
                    job_id,
                    status="partial_failed",
                    message=f"长文已生成，封面插图生成失败：{artwork_exc}",
                    article_path=result.article_path,
                    metadata_path=result.metadata_path,
                    summary=result.summary,
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
                return
        else:
            result.summary.update(
                {
                    "artwork_status": "not_requested",
                    "artwork_cover_count": 0,
                    "artwork_inline_count": 0,
                }
            )

        update_job(
            session,
            job_id,
            status="completed",
            message="长文生成完成",
            article_path=result.article_path,
            metadata_path=result.metadata_path,
            summary=result.summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_manifest(workdir, DailyWriterJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("Daily writer job failed: {}", job_id)
        try:
            job = DailyWriterJobDAO(session).get(job_id)
            if job is not None:
                append_log(Path(job.workdir), f"ERROR: {exc}")
                mark_progress_failure(Path(job.workdir), str(exc))
                update_job(
                    session,
                    job_id,
                    status="failed",
                    message=str(exc),
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(Path(job.workdir), DailyWriterJobDAO(session).get(job_id))
        finally:
            pass
    finally:
        session.close()


def _find_seed_row(rows: list[dict[str, str]], seed_id: str) -> dict[str, str]:
    normalized = seed_id.strip()
    for row in rows:
        if row.get("seed_id", "").strip() == normalized:
            return row
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"选题矩阵中不存在 seed_id：{seed_id}",
    )


def _coerce_variant_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_VARIANT_COUNT))


def _reconcile_orphaned_finished_job(
    db: Session, job: DailyWriterJob
) -> DailyWriterJob:
    if job.status not in {"queued", "running"}:
        return job
    workdir = Path(job.workdir)
    if not progress_marked_complete(workdir):
        return job

    params = parse_json_dict(job.params_json)
    queue_position = get_queue().queue_position(job.id)
    has_followup_steps = bool(params.get("generate_variants")) or bool(
        params.get("generate_artwork")
    )
    if queue_position is not None and has_followup_steps:
        return job
    try:
        result = parse_daily_writer_result(
            job_id=job.id,
            source_seed_matrix_job_id=job.source_seed_matrix_job_id,
            source_aiwiki_job_id=job.source_aiwiki_job_id,
            seed_id=job.seed_id,
            workdir=workdir,
            article_path=job.article_path,
            metadata_path=job.metadata_path,
            write_artwork_assets=True,
        )
        expected_variants = (
            _coerce_variant_count(params.get("variant_count"))
            if params.get("generate_variants")
            else 0
        )
        if expected_variants and len(result.variants) < expected_variants:
            return job
        if params.get("generate_artwork") and (
            not result.artwork.cover_images or not result.artwork.inline_images
        ):
            return job
    except Exception as exc:
        logger.warning("跳过 Daily Writer 孤儿任务收尾 {}: {}", job.id, exc)
        return job

    append_log(workdir, "RECOVERY: progress.json 已完成，补写 Daily Writer 任务状态。")
    update_job(
        db,
        job.id,
        status="completed",
        message="长文生成完成",
        article_path=result.article_path,
        metadata_path=result.metadata_path,
        summary=result.summary,
        finished_at=datetime.now(timezone.utc).isoformat(),
    )
    reconciled = DailyWriterJobDAO(db).get(job.id) or job
    write_manifest(workdir, reconciled)
    return reconciled


def _run_daily_writer_json_check_with_repair(
    workdir: Path, *, article_dir: str | None = None, include_variants: bool = False
) -> None:
    try:
        _run_daily_writer_json_check(
            workdir,
            article_dir=article_dir,
            include_variants=include_variants,
        )
        return
    except Exception as first_error:
        append_log(workdir, f"DAILY WRITER JSON CHECK ERROR: {first_error}")
        mark_progress_running(
            workdir,
            step="修复 metadata JSON",
            summary="metadata JSON 校验失败，正在下发 OpenCode 修复任务",
        )
        repair_progress_events = _progress_events_snapshot(workdir)
        try:
            run_repair_opencode(workdir, error=str(first_error), article_dir=article_dir)
        finally:
            _ensure_progress_events_preserved(
                workdir, repair_progress_events, "metadata JSON 修复"
            )
        if not progress_marked_complete(workdir):
            raise RuntimeError("修复后 progress.json 未写入任务完成标记")
        _run_daily_writer_json_check(
            workdir,
            article_dir=article_dir,
            include_variants=include_variants,
        )


def _run_daily_writer_json_check(
    workdir: Path, *, article_dir: str | None = None, include_variants: bool = False
) -> None:
    args = python_args(".agents/skills/wechat-daily-writer/scripts/check_article_json.py")
    if article_dir:
        args.extend(["--article-dir", article_dir])
    if include_variants:
        args.append("--include-variants")
    run_check_command(workdir, args, label="长文 metadata JSON 校验")


def _progress_events_snapshot(workdir: Path) -> list[object]:
    events = read_progress(workdir).get("events")
    return list(events) if isinstance(events, list) else []


def _ensure_progress_events_preserved(
    workdir: Path, baseline_events: list[object], stage: str
) -> None:
    events = read_progress(workdir).get("events")
    if not isinstance(events, list):
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：events 缺失或不是数组")
    if len(events) < len(baseline_events) or events[: len(baseline_events)] != baseline_events:
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：必须保留已有 events 并追加新事件")
