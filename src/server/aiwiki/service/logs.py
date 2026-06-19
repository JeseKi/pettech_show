# -*- coding: utf-8 -*-
"""AI Wiki job log helpers."""

from __future__ import annotations

from pathlib import Path

from .constants import LOG_TAIL_LINES


def append_log(workdir: Path, line: str) -> None:
    log_path = workdir / "logs" / "opencode.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as file:
        file.write(line.rstrip() + "\n")


def read_log_tail(workdir: Path) -> list[str]:
    log_path = workdir / "logs" / "opencode.log"
    if not log_path.exists():
        return []
    lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    return lines[-LOG_TAIL_LINES:]
