# -*- coding: utf-8 -*-
"""OpenCode session discovery and persistence."""

from __future__ import annotations

import json
import os
import shlex
import subprocess
from pathlib import Path

from src.server.aiwiki.service.logs import append_log
from src.server.config import global_config

from .constants import SESSION_FILE_NAME, TMUX_COMMAND_TIMEOUT_SECONDS
from .env import isolated_env


def read_session_id(workdir: Path) -> str | None:
    session_path = workdir / SESSION_FILE_NAME
    if not session_path.is_file():
        return None
    session_id = session_path.read_text(encoding="utf-8", errors="replace").strip()
    return session_id if session_id.startswith("ses_") else None


def persist_session_id(
    workdir: Path, *, title: str, started_after_ms: int, session_dir: Path | None = None
) -> str | None:
    existing = read_session_id(workdir)
    if existing:
        return existing
    session = _find_latest_opencode_session(
        session_dir or workdir,
        title=title,
        started_after_ms=started_after_ms,
        runtime_dir=workdir,
    )
    if session is None:
        return None
    session_id = str(session.get("id") or "")
    if not session_id.startswith("ses_"):
        return None
    (workdir / SESSION_FILE_NAME).write_text(session_id + "\n", encoding="utf-8")
    append_log(workdir, f"已记录 OpenCode session：{session_id}")
    return session_id


def _find_latest_opencode_session(
    workdir: Path, *, title: str, started_after_ms: int, runtime_dir: Path | None = None
) -> dict[str, object] | None:
    sessions = _list_opencode_sessions(workdir, runtime_dir=runtime_dir)
    if not sessions:
        return None
    workdir_text = workdir.as_posix()
    candidates: list[dict[str, object]] = []
    for session in sessions:
        if str(session.get("directory") or "") != workdir_text:
            continue
        if title and str(session.get("title") or "") != title:
            continue
        created = _coerce_epoch_ms(session.get("created"))
        updated = _coerce_epoch_ms(session.get("updated"))
        if max(created, updated) + 2000 < started_after_ms:
            continue
        candidates.append(session)
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda item: (
            _coerce_epoch_ms(item.get("updated")),
            _coerce_epoch_ms(item.get("created")),
        ),
    )


def _list_opencode_sessions(
    workdir: Path, *, runtime_dir: Path | None = None
) -> list[dict[str, object]]:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        return []
    args = [*command, "session", "list", "--format", "json", "--max-count", "50"]
    try:
        result = subprocess.run(
            args,
            cwd=workdir,
            capture_output=True,
            check=False,
            text=True,
            timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
            env=isolated_env(runtime_dir or workdir, os.environ.copy()),
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []
    if result.returncode != 0:
        return []
    try:
        payload = json.loads(result.stdout)
    except json.JSONDecodeError:
        return []
    if not isinstance(payload, list):
        return []
    return [item for item in payload if isinstance(item, dict)]


def _coerce_epoch_ms(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        return int(value)
    if isinstance(value, str):
        try:
            return int(float(value))
        except ValueError:
            return 0
    return 0
