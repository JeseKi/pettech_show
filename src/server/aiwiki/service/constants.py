# -*- coding: utf-8 -*-
"""AI Wiki service constants."""

from __future__ import annotations

ALLOWED_EXTENSIONS = {".md", ".markdown", ".txt", ".xlsx", ".csv", ".pdf"}
LOG_TAIL_LINES = 80
PROGRESS_FILE_NAME = "progress.json"
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
SKILL_NAMES = [
    "wechat-raw-materializer",
    "wechat-topic-wiki",
]
