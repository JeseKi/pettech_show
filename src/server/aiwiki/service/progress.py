# -*- coding: utf-8 -*-
"""Progress file helpers for AI Wiki jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import (
    LEGACY_PROGRESS_COMPLETE_EVENT,
    PROGRESS_COMPLETE_EVENT,
    PROGRESS_FILE_NAME,
)


def initial_progress() -> dict[str, Any]:
    return {
        "status": "queued",
        "current_step": "任务排队中",
        "events": [
            {
                "event": "开始",
                "step": "排队",
                "summary": "任务已进入队列",
            }
        ],
    }


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


def mark_progress_running(workdir: Path, *, step: str, summary: str) -> None:
    progress = read_progress(workdir)
    events = progress.get("events")
    if not isinstance(events, list):
        events = []
    events.append({"event": "开始", "step": step, "summary": summary})
    write_progress(
        workdir,
        {
            "status": "running",
            "current_step": step,
            "events": events,
        },
    )


def mark_progress_failure(workdir: Path, summary: str) -> None:
    progress = read_progress(workdir)
    events = progress.get("events")
    if not isinstance(events, list):
        events = []
    events.append({"event": "失败", "step": "任务失败", "summary": summary})
    write_progress(
        workdir,
        {
            "status": "failure",
            "current_step": "任务失败",
            "events": events,
        },
    )


def read_progress(workdir: Path) -> dict[str, Any]:
    progress_path = workdir / PROGRESS_FILE_NAME
    if not progress_path.exists():
        return {}
    try:
        parsed = json.loads(
            progress_path.read_text(encoding="utf-8", errors="replace")
        )
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def write_progress(workdir: Path, progress: dict[str, Any]) -> None:
    progress_path = workdir / PROGRESS_FILE_NAME
    progress_path.write_text(
        json.dumps(progress, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
