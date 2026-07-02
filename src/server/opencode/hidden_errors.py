# -*- coding: utf-8 -*-
"""Hidden generation error markers for demo-facing OpenCode jobs."""

from __future__ import annotations

from pathlib import Path

from loguru import logger

HIDDEN_GENERATION_ERROR_MARKER = "HERE IS A E"


def record_hidden_generation_error(workdir: Path, message: object) -> None:
    text = str(message).strip() or "生成任务后处理失败"
    logger.warning("OpenCode hidden generation error at {}: {}", workdir, text)
    log_path = workdir / "logs" / "opencode.log"
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except FileNotFoundError:
        lines = []
    if lines and lines[-1] == HIDDEN_GENERATION_ERROR_MARKER:
        return
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(HIDDEN_GENERATION_ERROR_MARKER + "\n")
