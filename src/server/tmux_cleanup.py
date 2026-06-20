# -*- coding: utf-8 -*-
"""Background cleanup for stale tmux sessions."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Event, Thread

from loguru import logger

TMUX_CLEANUP_INTERVAL_SECONDS = 300
TMUX_SESSION_TTL_SECONDS = 3 * 60 * 60
TMUX_COMMAND_TIMEOUT_SECONDS = 10


@dataclass(frozen=True)
class TmuxSession:
    name: str
    created_at_epoch: int


class TmuxCleanupService:
    def __init__(
        self,
        *,
        interval_seconds: int = TMUX_CLEANUP_INTERVAL_SECONDS,
        ttl_seconds: int = TMUX_SESSION_TTL_SECONDS,
    ):
        self.interval_seconds = interval_seconds
        self.ttl_seconds = ttl_seconds
        self._stop_event = Event()
        self._thread: Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = Thread(
            target=self._run,
            name="tmux-cleanup",
            daemon=True,
        )
        self._thread.start()
        logger.info("tmux 清理服务已启动：interval={}s ttl={}s", self.interval_seconds, self.ttl_seconds)

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        self._thread = None
        logger.info("tmux 清理服务已停止")

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                cleanup_old_tmux_sessions(ttl_seconds=self.ttl_seconds)
            except Exception as exc:
                logger.warning("tmux 清理扫描失败：{}", exc)
            self._stop_event.wait(self.interval_seconds)


def cleanup_old_tmux_sessions(
    *,
    ttl_seconds: int = TMUX_SESSION_TTL_SECONDS,
    now_epoch: int | None = None,
) -> int:
    now = now_epoch if now_epoch is not None else int(datetime.now(timezone.utc).timestamp())
    sessions = list_tmux_sessions()
    killed_count = 0
    for session in sessions:
        age_seconds = now - session.created_at_epoch
        if age_seconds < ttl_seconds:
            continue
        if kill_tmux_session(session.name):
            killed_count += 1
            logger.info(
                "已清理过期 tmux session：{} age={}s ttl={}s",
                session.name,
                age_seconds,
                ttl_seconds,
            )
    return killed_count


def list_tmux_sessions() -> list[TmuxSession]:
    try:
        result = subprocess.run(
            ["tmux", "list-sessions", "-F", "#{session_name}\t#{session_created}"],
            capture_output=True,
            check=False,
            text=True,
            timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError:
        logger.warning("未找到 tmux 命令，跳过 tmux 清理")
        return []

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        if stderr and "no server running" not in stderr.lower():
            logger.debug("tmux list-sessions 返回非零退出码：{}", stderr)
        return []

    sessions: list[TmuxSession] = []
    for line in result.stdout.splitlines():
        parsed = parse_tmux_session_line(line)
        if parsed is not None:
            sessions.append(parsed)
    return sessions


def parse_tmux_session_line(line: str) -> TmuxSession | None:
    raw_name, separator, raw_created = line.partition("\t")
    if not separator:
        return None
    name = raw_name.strip()
    if not name:
        return None
    try:
        created_at_epoch = int(raw_created.strip())
    except ValueError:
        return None
    return TmuxSession(name=name, created_at_epoch=created_at_epoch)


def kill_tmux_session(session_name: str) -> bool:
    result = subprocess.run(
        ["tmux", "kill-session", "-t", session_name],
        capture_output=True,
        check=False,
        text=True,
        timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
    )
    if result.returncode == 0:
        return True
    logger.debug(
        "清理 tmux session 失败：{} {}",
        session_name,
        (result.stderr or "").strip(),
    )
    return False


tmux_cleanup_service = TmuxCleanupService()

