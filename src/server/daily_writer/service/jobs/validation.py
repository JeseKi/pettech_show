# -*- coding: utf-8 -*-
"""Daily writer validation and progress guards."""

from __future__ import annotations

from pathlib import Path

from src.server.aiwiki.service.checks import python_args, run_check_command
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import (
    mark_progress_running,
    progress_marked_complete,
    read_progress,
)

from ..constants import MAX_VARIANT_COUNT
from ..opencode import run_repair_opencode


def coerce_variant_count(value: object) -> int:
    try:
        count = int(str(value or 0))
    except (TypeError, ValueError):
        return 0
    return max(0, min(count, MAX_VARIANT_COUNT))


def run_daily_writer_json_check_with_repair(
    workdir: Path, *, article_dir: str | None = None, include_variants: bool = False
) -> None:
    try:
        run_daily_writer_json_check(
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
        repair_progress_events = progress_events_snapshot(workdir)
        try:
            run_repair_opencode(workdir, error=str(first_error), article_dir=article_dir)
        finally:
            ensure_progress_events_preserved(
                workdir, repair_progress_events, "metadata JSON 修复"
            )
        if not progress_marked_complete(workdir):
            raise RuntimeError("修复后 progress.json 未写入任务完成标记")
        run_daily_writer_json_check(
            workdir,
            article_dir=article_dir,
            include_variants=include_variants,
        )


def run_daily_writer_json_check(
    workdir: Path, *, article_dir: str | None = None, include_variants: bool = False
) -> None:
    args = python_args(".agents/skills/wechat-daily-writer/scripts/check_article_json.py")
    if article_dir:
        args.extend(["--article-dir", article_dir])
    if include_variants:
        args.append("--include-variants")
    run_check_command(workdir, args, label="长文 metadata JSON 校验")


def progress_events_snapshot(workdir: Path) -> list[object]:
    events = read_progress(workdir).get("events")
    return list(events) if isinstance(events, list) else []


def ensure_progress_events_preserved(
    workdir: Path, baseline_events: list[object], stage: str
) -> None:
    events = read_progress(workdir).get("events")
    if not isinstance(events, list):
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：events 缺失或不是数组")
    if len(events) < len(baseline_events) or events[: len(baseline_events)] != baseline_events:
        raise RuntimeError(f"{stage} 阶段重置了 progress.json：必须保留已有 events 并追加新事件")
