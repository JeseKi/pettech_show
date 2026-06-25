# -*- coding: utf-8 -*-
"""Public social card job service functions."""

from __future__ import annotations

import json
import shutil
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session, sessionmaker

from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.opencode import prepare_opencode_config
from src.server.aiwiki.service.progress import (
    initial_progress,
    mark_progress_failure,
    progress_marked_complete,
    read_progress,
    write_progress,
)
from src.server.auth.models import User
from src.server.config import global_config
from src.server.daily_writer.service.persistence import get_accessible_job as get_daily_writer_job

from ..dao import SocialCardJobDAO, parse_json_dict
from ..models import SocialCardJob
from ..parser import parse_social_card_result, resolve_social_card_asset_path
from ..queue_state import get_queue
from ..schemas import (
    SocialCardCreate,
    SocialCardJobListOut,
    SocialCardJobOut,
    SocialCardResultOut,
)
from .artifacts import copy_source_article, prepare_skill
from .constants import MAX_SOCIAL_CARD_COUNT, MAX_SOCIAL_POST_COUNT, RESULT_ZIP_NAME
from .opencode import run_opencode
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
    get_queue().enqueue(job_id, lambda: _run_job(job_id, session_factory))
    return job_out_from_model(job, current_user.username)


def list_jobs(
    db: Session,
    *,
    limit: int,
    offset: int,
    current_user: User,
    source_daily_writer_job_id: str | None = None,
) -> SocialCardJobListOut:
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    owner_filter = None if is_admin(current_user) else current_user.id
    dao = SocialCardJobDAO(db)
    jobs = dao.list(
        limit=normalized_limit,
        offset=normalized_offset,
        owner_user_id=owner_filter,
        source_daily_writer_job_id=source_daily_writer_job_id,
    )
    jobs = [_reconcile_orphaned_finished_job(db, job) for job in jobs]
    return SocialCardJobListOut(
        items=[job_summary_from_model(job, dao.owner_username(job.owner_user_id)) for job in jobs],
        total=dao.count(
            owner_user_id=owner_filter,
            source_daily_writer_job_id=source_daily_writer_job_id,
        ),
        limit=normalized_limit,
        offset=normalized_offset,
    )


def get_job(db: Session, job_id: str, current_user: User) -> SocialCardJobOut:
    job = get_accessible_job(db, job_id, current_user)
    job = _reconcile_orphaned_finished_job(db, job)
    return job_out_from_model(job, SocialCardJobDAO(db).owner_username(job.owner_user_id))


def get_result(db: Session, job_id: str, current_user: User) -> SocialCardResultOut:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return parse_social_card_result(
            job_id=job.id,
            source_daily_writer_job_id=job.source_daily_writer_job_id,
            workdir=Path(job.workdir),
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
    SocialCardJobDAO(db).delete(job)
    shutil.rmtree(workdir, ignore_errors=True)


def delete_child_jobs_for_daily_writer(db: Session, source_daily_writer_job_id: str) -> None:
    dao = SocialCardJobDAO(db)
    children = dao.list(
        limit=1000,
        offset=0,
        source_daily_writer_job_id=source_daily_writer_job_id,
    )
    active = [job for job in children if job.status in {"queued", "running"}]
    if active:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="该稿件任务仍有关联的小红书图文卡任务正在执行",
        )
    for child in children:
        child_workdir = Path(child.workdir)
        dao.delete(child)
        shutil.rmtree(child_workdir, ignore_errors=True)


def result_zip_file(db: Session, job_id: str, current_user: User) -> Path:
    get_result(db, job_id, current_user)
    job = get_accessible_job(db, job_id, current_user)
    workdir = Path(job.workdir)
    zip_path = workdir / RESULT_ZIP_NAME
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive_roots = [workdir / "xhs_guizang", workdir / "xhs_guizang_variants"]
        archive_roots.extend(sorted(workdir.glob("xhs_guizang_variant_*")))
        for root in archive_roots:
            if not root.is_dir():
                continue
            for path in sorted(root.rglob("*")):
                if path.is_file():
                    archive.write(path, arcname=path.relative_to(workdir).as_posix())
    return zip_path


def image_file(
    db: Session,
    job_id: str,
    asset_key: str,
    current_user: User,
) -> tuple[Path, str]:
    job = get_accessible_job(db, job_id, current_user)
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="任务尚未完成")
    try:
        return resolve_social_card_asset_path(
            job_id=job.id,
            source_daily_writer_job_id=job.source_daily_writer_job_id,
            workdir=Path(job.workdir),
            asset_key=asset_key,
        )
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))


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


def _run_job(job_id: str, session_factory: sessionmaker[Session]) -> None:
    session = session_factory()
    try:
        job = SocialCardJobDAO(session).get(job_id)
        if job is None:
            return
        started_at = datetime.now(timezone.utc)
        update_job(
            session,
            job_id,
            status="running",
            message="OpenCode 正在生成小红书图文卡",
            started_at=started_at.isoformat(),
        )
        job = SocialCardJobDAO(session).get(job_id)
        if job is None:
            return
        workdir = Path(job.workdir)
        write_manifest(workdir, job)
        prepare_opencode_config(workdir)
        params = parse_json_dict(job.params_json)
        post_count = _coerce_post_count(params.get("post_count"))
        cards_per_post = _coerce_card_count(
            params.get("cards_per_post", params.get("card_count"))
        )
        progress_events = _progress_events_snapshot(workdir)
        try:
            run_opencode(
                workdir,
                post_count=post_count,
                cards_per_post=cards_per_post,
            )
        finally:
            _ensure_progress_events_preserved(workdir, progress_events, "小红书图文卡生成")
        if not progress_marked_complete(workdir):
            raise RuntimeError(
                _incomplete_progress_message(
                    workdir,
                    post_count=post_count,
                    cards_per_post=cards_per_post,
                )
            )
        result = parse_social_card_result(
            job_id=job.id,
            source_daily_writer_job_id=job.source_daily_writer_job_id,
            workdir=workdir,
        )
        _assert_result_counts(
            result=result,
            post_count=post_count,
            cards_per_post=cards_per_post,
        )
        total_card_count = post_count * cards_per_post
        if len(result.images) != total_card_count:
            raise RuntimeError(
                f"图文卡生成数量不符：期望 {total_card_count} 张，实际 {len(result.images)} 张"
            )
        summary = {
            **result.summary,
            "post_count": post_count,
            "cards_per_post": cards_per_post,
            "requested_count": total_card_count,
            "image_count": len(result.images),
            "status": "completed",
        }
        update_job(
            session,
            job_id,
            status="completed",
            message="小红书图文卡生成完成",
            summary=summary,
            finished_at=datetime.now(timezone.utc).isoformat(),
        )
        write_manifest(workdir, SocialCardJobDAO(session).get(job_id))
    except Exception as exc:
        logger.exception("Social card job failed: {}", job_id)
        try:
            job = SocialCardJobDAO(session).get(job_id)
            if job is not None:
                append_log(Path(job.workdir), f"ERROR: {exc}")
                mark_progress_failure(Path(job.workdir), str(exc))
                update_job(
                    session,
                    job_id,
                    status="failed",
                    message=str(exc),
                    summary={
                        "status": "failed",
                        "error": str(exc),
                    },
                    finished_at=datetime.now(timezone.utc).isoformat(),
                )
                write_manifest(Path(job.workdir), SocialCardJobDAO(session).get(job_id))
        finally:
            pass
    finally:
        session.close()


def _coerce_card_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SOCIAL_CARD_COUNT))


def _coerce_post_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_SOCIAL_POST_COUNT))


def _assert_result_counts(
    *,
    result: SocialCardResultOut,
    post_count: int,
    cards_per_post: int,
) -> None:
    if len(result.posts) != post_count:
        raise RuntimeError(
            f"图文篇数不符：期望 {post_count} 篇，实际 {len(result.posts)} 篇"
        )
    for index, post in enumerate(result.posts, start=1):
        if len(post.images) != cards_per_post:
            raise RuntimeError(
                f"第 {index} 篇图文卡数量不符：期望 {cards_per_post} 张，实际 {len(post.images)} 张"
            )


def _reconcile_orphaned_finished_job(
    db: Session, job: SocialCardJob
) -> SocialCardJob:
    if job.status not in {"queued", "running"}:
        return job
    if get_queue().queue_position(job.id) is not None:
        return job
    workdir = Path(job.workdir)
    if not progress_marked_complete(workdir):
        return job

    params = parse_json_dict(job.params_json)
    expected_post_count = _coerce_post_count(params.get("post_count"))
    expected_cards_per_post = _coerce_card_count(
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


def _incomplete_progress_message(
    workdir: Path, *, post_count: int, cards_per_post: int
) -> str:
    progress = read_progress(workdir)
    status_text = str(progress.get("status") or "未知")
    current_step = str(progress.get("current_step") or "未知步骤")
    last_event = _describe_last_progress_event(progress)
    issues = _inspect_social_card_outputs(
        workdir,
        post_count=post_count,
        cards_per_post=cards_per_post,
    )
    issue_text = "；".join(issues) if issues else "产物目录存在，但完成态协议未封口"
    return (
        "小红书图文卡生成未完成：OpenCode 已退出，但 progress.json 未写入 completed。"
        f" 当前状态：{status_text}，当前步骤：{current_step}，最后事件：{last_event}。"
        f" 发现问题：{issue_text}"
    )


def _describe_last_progress_event(progress: dict[str, object]) -> str:
    events = progress.get("events")
    if not isinstance(events, list):
        return "events 缺失或不是数组"
    if not events:
        return "无"
    last = events[-1]
    if not isinstance(last, dict):
        return "最后一条事件不是对象"
    event = str(last.get("event") or "未知事件")
    step = str(last.get("step") or "未知步骤")
    summary = str(last.get("summary") or "")
    if summary:
        return f"{event}/{step}：{summary}"
    return f"{event}/{step}"


def _inspect_social_card_outputs(
    workdir: Path, *, post_count: int, cards_per_post: int
) -> list[str]:
    issues: list[str] = []
    first_dir = workdir / "xhs_guizang"
    if not first_dir.is_dir():
        issues.append("未生成 xhs_guizang/")
    else:
        _append_post_output_issues(
            first_dir,
            label="xhs_guizang",
            cards_per_post=cards_per_post,
            issues=issues,
        )

    for post_index in range(2, post_count + 1):
        variant_name = f"variant-{post_index - 1:02d}"
        variant_dir = workdir / "xhs_guizang_variants" / variant_name
        label = f"xhs_guizang_variants/{variant_name}"
        if not variant_dir.is_dir():
            issues.append(f"未生成 {label}/")
            continue
        _append_post_output_issues(
            variant_dir,
            label=label,
            cards_per_post=cards_per_post,
            issues=issues,
        )
    return issues


def _append_post_output_issues(
    post_dir: Path, *, label: str, cards_per_post: int, issues: list[str]
) -> None:
    for filename in ("index.html", "manifest.json", "main.md"):
        if not (post_dir / filename).is_file():
            issues.append(f"缺少 {label}/{filename}")
    output_dir = post_dir / "output"
    if not output_dir.is_dir():
        issues.append(f"缺少 {label}/output/")
        return
    png_count = len([path for path in output_dir.glob("*.png") if path.is_file()])
    if png_count != cards_per_post:
        issues.append(
            f"{label}/output/ PNG 数量不符：期望 {cards_per_post} 张，实际 {png_count} 张"
        )
