# -*- coding: utf-8 -*-
"""Progress file helpers for AI Wiki jobs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .constants import PROGRESS_COMPLETE_EVENT, PROGRESS_FILE_NAME


def initial_progress() -> dict[str, Any]:
    return {
        "status": "queued",
        "current_step": "任务排队中",
        "events": [
            {
                "event": "started",
                "step": "queued",
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
    return all(
        events[-1].get(key) == value
        for key, value in PROGRESS_COMPLETE_EVENT.items()
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
