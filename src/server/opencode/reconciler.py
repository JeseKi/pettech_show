# -*- coding: utf-8 -*-
"""Background reconciliation for OpenCode-backed jobs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Event, Thread
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from src.server.opencode.hidden_errors import record_hidden_generation_error

RECONCILE_INTERVAL_SECONDS = 60
ACTIVE_STATUSES = ("queued", "running")
PROGRESS_COMPLETE_EVENT = {
    "event": "完成",
    "step": "全部",
    "summary": "任务完成",
}
LEGACY_PROGRESS_COMPLETE_EVENT = {
    "event": "completed",
    "step": "all",
    "summary": "任务完成",
}


class OpenCodeReconcilerService:
    def __init__(self, *, interval_seconds: int = RECONCILE_INTERVAL_SECONDS):
        self.interval_seconds = interval_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="opencode-reconciler",
            daemon=True,
        )
        self._thread.start()
        logger.info("OpenCode 任务协调器已启动：interval={}s", self.interval_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("OpenCode 任务协调器已停止")

    def _run(self) -> None:
        from src.server.database import SessionLocal

        while not self._stop_event.wait(self.interval_seconds):
            db = SessionLocal()
            try:
                reconciled_count = reconcile_active_opencode_jobs(db)
                if reconciled_count:
                    logger.info("OpenCode 任务协调器本轮补写完成任务 {} 个", reconciled_count)
            except Exception as exc:
                logger.warning("OpenCode 任务协调器扫描失败：{}", exc)
            finally:
                db.close()


def reconcile_active_opencode_jobs(db: Session) -> int:
    return sum(
        (
            _reconcile_aiwiki_jobs(db),
            _reconcile_seed_matrix_jobs(db),
            _reconcile_daily_writer_jobs(db),
            _reconcile_social_card_jobs(db),
            _reconcile_social_card_video_jobs(db),
            _reconcile_capability_jobs(db),
            _reconcile_personal_aiwiki_jobs(db),
        )
    )


def _reconcile_aiwiki_jobs(db: Session) -> int:
    from src.server.aiwiki.dao import AiwikiJobDAO
    from src.server.aiwiki.models import AiwikiJob
    from src.server.aiwiki.parser import parse_aiwiki_result
    from src.server.aiwiki.service.persistence import read_manifest, write_manifest

    count = 0
    jobs = _active_jobs(db, AiwikiJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        try:
            result = parse_aiwiki_result(job.id, workdir)
            if not result.materials and not result.wiki_entries:
                raise RuntimeError("OpenCode 未生成 material 或 wiki 结果")
        except Exception as exc:
            record_hidden_generation_error(workdir, f"AI Wiki 结果不可用：{exc}")
            continue
        updated = AiwikiJobDAO(db).update(
            job.id,
            status="completed",
            message="AI Wiki 生成完成",
            summary_json=result.summary,
            finished_at=_finished_at(job),
        )
        if updated is None:
            continue
        _update_manifest_file(
            workdir,
            read_manifest,
            write_manifest,
            status="completed",
            message="AI Wiki 生成完成",
            finished_at=_finished_at(updated),
            summary=result.summary,
        )
        count += 1
    return count


def _reconcile_seed_matrix_jobs(db: Session) -> int:
    from src.server.seed_matrix.dao import SeedMatrixJobDAO
    from src.server.seed_matrix.models import SeedMatrixJob
    from src.server.seed_matrix.parser import parse_seed_matrix_result
    from src.server.seed_matrix.service.constants import RESULT_CSV_PATH
    from src.server.seed_matrix.service.persistence import write_manifest

    count = 0
    jobs = _active_jobs(db, SeedMatrixJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        try:
            result_path = job.result_csv_path or RESULT_CSV_PATH
            result = parse_seed_matrix_result(
                job_id=job.id,
                source_aiwiki_job_id=job.source_aiwiki_job_id,
                workdir=workdir,
                csv_path=result_path,
            )
        except Exception as exc:
            record_hidden_generation_error(workdir, f"选题矩阵结果不可用：{exc}")
            continue
        updated = SeedMatrixJobDAO(db).update(
            job.id,
            status="completed",
            message="选题矩阵生成完成",
            result_csv_path=job.result_csv_path or RESULT_CSV_PATH,
            summary=result.summary,
            finished_at=_finished_at(job),
        )
        write_manifest(workdir, updated)
        count += 1
    return count


def _reconcile_daily_writer_jobs(db: Session) -> int:
    from src.server.daily_writer.dao import DailyWriterJobDAO, parse_json_dict
    from src.server.daily_writer.models import DailyWriterJob
    from src.server.daily_writer.parser import parse_daily_writer_result
    from src.server.daily_writer.service.persistence import write_manifest

    count = 0
    jobs = _active_jobs(db, DailyWriterJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        params = parse_json_dict(job.params_json)
        if _active_queue_position("daily_writer", job.id) is not None and (
            bool(params.get("generate_variants")) or bool(params.get("generate_artwork"))
        ):
            continue
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
            if not _daily_writer_followups_satisfied(result, params):
                raise RuntimeError("稿件后续产物尚未生成完整")
        except Exception as exc:
            record_hidden_generation_error(workdir, f"稿件结果不可用：{exc}")
            continue
        updated = DailyWriterJobDAO(db).update(
            job.id,
            status="completed",
            message="长文生成完成",
            article_path=result.article_path,
            metadata_path=result.metadata_path,
            summary=result.summary,
            finished_at=_finished_at(job),
        )
        write_manifest(workdir, updated)
        count += 1
    return count


def _reconcile_social_card_jobs(db: Session) -> int:
    from src.server.social_cards.dao import SocialCardJobDAO
    from src.server.social_cards.models import SocialCardJob
    from src.server.social_cards.parser import parse_social_card_result
    from src.server.social_cards.service.persistence import write_manifest

    count = 0
    jobs = _active_jobs(db, SocialCardJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        try:
            result = parse_social_card_result(
                job_id=job.id,
                source_daily_writer_job_id=job.source_daily_writer_job_id,
                workdir=workdir,
            )
        except Exception as exc:
            record_hidden_generation_error(workdir, f"图文结果不可用：{exc}")
            continue
        updated = SocialCardJobDAO(db).update(
            job.id,
            status="completed",
            message="小红书图文卡生成完成",
            summary={**result.summary, "status": "completed"},
            finished_at=_finished_at(job),
        )
        write_manifest(workdir, updated)
        count += 1
    return count


def _reconcile_social_card_video_jobs(db: Session) -> int:
    from src.server.social_card_videos.dao import SocialCardVideoJobDAO
    from src.server.social_card_videos.models import SocialCardVideoJob
    from src.server.social_card_videos.parser import parse_social_card_video_result
    from src.server.social_card_videos.service.persistence import write_manifest

    count = 0
    jobs = _active_jobs(db, SocialCardVideoJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        try:
            result = parse_social_card_video_result(
                job_id=job.id,
                source_social_card_job_id=job.source_social_card_job_id,
                workdir=workdir,
            )
        except Exception as exc:
            record_hidden_generation_error(workdir, f"轮播视频结果不可用：{exc}")
            continue
        updated = SocialCardVideoJobDAO(db).update(
            job.id,
            status="completed",
            message="轮播视频生成完成",
            summary={**result.summary, "status": "completed"},
            finished_at=_finished_at(job),
        )
        write_manifest(workdir, updated)
        count += 1
    return count


def _reconcile_capability_jobs(db: Session) -> int:
    from src.server.capability_jobs.dao import CapabilityJobDAO, parse_json_dict
    from src.server.capability_jobs.models import CapabilityJob
    from src.server.capability_jobs.parser import parse_capability_result
    from src.server.capability_jobs.config import get_capability
    from src.server.capability_jobs.service.persistence import write_manifest

    result_md_path = "output/result.md"
    result_json_path = "output/result.json"
    count = 0
    jobs = _active_jobs(db, CapabilityJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        config = get_capability(job.capability_key)
        summary = _capability_summary(workdir, config.title if config else job.capability_key)
        try:
            parse_capability_result(
                job_id=job.id,
                capability_key=job.capability_key,
                workdir=workdir,
                markdown_path=job.result_markdown_path or result_md_path,
                json_path=job.result_json_path or result_json_path,
                summary=summary,
            )
        except Exception as exc:
            record_hidden_generation_error(workdir, f"能力任务结果不可用：{exc}")
            continue
        updated = CapabilityJobDAO(db).update(
            job.id,
            status="completed",
            message="能力任务完成",
            result_markdown_path=job.result_markdown_path or result_md_path,
            result_json_path=job.result_json_path or result_json_path,
            summary=summary or parse_json_dict(job.summary_json),
            finished_at=_finished_at(job),
        )
        write_manifest(workdir, updated)
        count += 1
    return count


def _reconcile_personal_aiwiki_jobs(db: Session) -> int:
    from src.server.aiwiki.parser import parse_aiwiki_result
    from src.server.personal_aiwiki.dao import PersonalAiwikiJobDAO
    from src.server.personal_aiwiki.models import PersonalAiwikiJob
    from src.server.personal_aiwiki.service.persistence import (
        read_answer,
        read_manifest,
        write_manifest,
    )

    count = 0
    jobs = _active_jobs(db, PersonalAiwikiJob)
    for job in jobs:
        workdir = Path(job.workdir)
        if not _completed_progress_ready(workdir):
            continue
        try:
            workspace_dir = Path(job.workspace_dir)
            result = parse_aiwiki_result(job.id, workspace_dir)
            if not result.materials and not result.wiki_entries:
                raise RuntimeError("OpenCode 未生成个人 wiki 结果")
            answer = read_answer(workdir)
        except Exception as exc:
            record_hidden_generation_error(workdir, f"个人 AI Wiki 结果不可用：{exc}")
            continue
        updated = PersonalAiwikiJobDAO(db).update(
            job.id,
            status="completed",
            message="个人知识库已更新",
            summary=result.summary,
            answer_markdown=answer,
            finished_at=_finished_at(job),
        )
        if updated is None:
            continue
        _update_manifest_file(
            workdir,
            read_manifest,
            write_manifest,
            status="completed",
            message="个人知识库已更新",
            finished_at=_finished_at(updated),
            summary=result.summary,
            answer_markdown=answer,
        )
        count += 1
    return count


def _active_jobs(db: Session, model: type[Any]) -> list[Any]:
    return list(db.query(model).filter(model.status.in_(ACTIVE_STATUSES)).all())


def _completed_progress_ready(workdir: Path) -> bool:
    progress = read_progress(workdir)
    if str(progress.get("status") or "") in {"failure", "failed"}:
        record_hidden_generation_error(
            workdir,
            str(progress.get("current_step") or "任务失败"),
        )
        return False
    return progress_marked_complete(workdir)


def read_progress(workdir: Path) -> dict[str, Any]:
    progress_path = workdir / "progress.json"
    if not progress_path.exists():
        return {}
    try:
        parsed = json.loads(progress_path.read_text(encoding="utf-8", errors="replace"))
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def progress_marked_complete(workdir: Path) -> bool:
    progress = read_progress(workdir)
    events = progress.get("events")
    if (
        progress.get("status") != "completed"
        or progress.get("current_step") != "任务完成"
        or not isinstance(events, list)
        or not events
        or not isinstance(events[-1], dict)
    ):
        return False
    return any(
        all(events[-1].get(key) == value for key, value in complete_event.items())
        for complete_event in (PROGRESS_COMPLETE_EVENT, LEGACY_PROGRESS_COMPLETE_EVENT)
    )


def _finished_at(job: Any) -> str:
    value = getattr(job, "finished_at", None)
    if value is not None:
        return value.isoformat()
    return datetime.now(timezone.utc).isoformat()


def _active_queue_position(queue_name: str, job_id: str) -> int | None:
    if queue_name == "daily_writer":
        from src.server.daily_writer.queue_state import get_queue

        return get_queue().queue_position(job_id)
    return None


def _daily_writer_followups_satisfied(result: Any, params: dict[str, object]) -> bool:
    if bool(params.get("generate_variants")):
        expected_variants = _coerce_variant_count(params.get("variant_count"))
        if len(result.variants) < expected_variants:
            return False
    if bool(params.get("generate_artwork")) and (
        not result.artwork.cover_images or not result.artwork.inline_images
    ):
        return False
    return True


def _coerce_variant_count(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        return 3
    try:
        return max(1, min(int(value), 20))
    except (TypeError, ValueError):
        return 3


def _capability_summary(workdir: Path, fallback_title: str) -> dict[str, Any]:
    data_path = workdir / "output" / "result.json"
    summary: dict[str, Any] = {"title": fallback_title}
    if not data_path.is_file():
        return summary
    try:
        parsed = json.loads(data_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return summary
    if not isinstance(parsed, dict):
        return summary
    summary["title"] = str(parsed.get("title") or fallback_title)
    raw_summary = parsed.get("summary")
    if isinstance(raw_summary, dict):
        summary.update(raw_summary)
    elif isinstance(raw_summary, str):
        summary["summary"] = raw_summary
    return summary


def _update_manifest_file(
    workdir: Path,
    reader: Any,
    writer: Any,
    **fields: Any,
) -> None:
    try:
        manifest = reader(workdir)
    except Exception as exc:
        logger.warning("跳过 manifest 补写 {}: {}", workdir, exc)
        return
    manifest.update(fields)
    writer(workdir, manifest)


opencode_reconciler_service = OpenCodeReconcilerService()
