# -*- coding: utf-8 -*-
"""AI Wiki service constants."""

from __future__ import annotations

from pathlib import Path

ALLOWED_EXTENSIONS = {".md", ".txt", ".docx"}
LOG_TAIL_LINES = 80
PROGRESS_FILE_NAME = "progress.json"
PROGRESS_COMPLETE_EVENT = {
    "event": "completed",
    "step": "all",
    "summary": "任务完成",
}
SKILL_SOURCES = [
    Path("/home/jese--ki/Projects/writing/.agents/skills/wechat-raw-materializer"),
    Path("/home/jese--ki/Projects/writing/.agents/skills/wechat-topic-wiki"),
]
