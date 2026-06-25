# -*- coding: utf-8 -*-
"""tmux process management for OpenCode runs."""

from __future__ import annotations

import os
import re
import shlex
import subprocess
from pathlib import Path

from .constants import TMUX_COMMAND_TIMEOUT_SECONDS


def session_name(workdir: Path, title: str, run_id: str) -> str:
    raw = f"aiwiki-{workdir.name}-{title}-{run_id[-8:]}"
    slug = re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip("-")
    return slug[:100] or f"aiwiki-{run_id[-8:]}"


def build_tmux_script(
    *,
    args: list[str],
    prompt_path: Path,
    status_path: Path,
    log_path: Path,
    workdir: Path,
) -> str:
    command = " ".join(shlex.quote(arg) for arg in args)
    config_path = workdir / "config.json"
    opencode_config_line = (
        f"export OPENCODE_CONFIG={shlex.quote(config_path.as_posix())}"
        if config_path.exists()
        else ""
    )
    return "\n".join(
        line
        for line in [
            "#!/usr/bin/env bash",
            "set +e",
            f"cd {shlex.quote(workdir.as_posix())} || exit 1",
            opencode_config_line,
            f"prompt_file={shlex.quote(prompt_path.as_posix())}",
            f"status_file={shlex.quote(status_path.as_posix())}",
            f"log_file={shlex.quote(log_path.as_posix())}",
            'prompt="$(cat "$prompt_file")"',
            f"{command} \"$prompt\" >> \"$log_file\" 2>&1",
            "status=$?",
            "finished_at=\"$(date -u +%Y-%m-%dT%H:%M:%SZ)\"",
            "printf '{\"exit_code\":%s,\"finished_at\":\"%s\"}\\n' "
            '"$status" "$finished_at" > "$status_file"',
            'exit "$status"',
        ]
        if line
    )


def start_tmux_session(name: str, script_path: Path) -> None:
    tmux_cmd = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        name,
        "bash",
        "-lc",
        f"exec bash {shlex.quote(script_path.as_posix())}",
    ]
    try:
        result = subprocess.run(
            tmux_cmd,
            capture_output=True,
            check=False,
            env=os.environ.copy(),
            text=True,
            timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("未找到 tmux 命令，无法通过 tmux 运行 OpenCode") from exc
    if result.returncode != 0:
        stderr = (result.stderr or result.stdout or "").strip()
        raise RuntimeError(f"tmux 启动 OpenCode 失败：{stderr or result.returncode}")


def tmux_session_exists(name: str) -> bool:
    result = subprocess.run(
        ["tmux", "has-session", "-t", name],
        capture_output=True,
        check=False,
        text=True,
        timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
    )
    return result.returncode == 0


def kill_tmux_session(name: str) -> None:
    subprocess.run(
        ["tmux", "kill-session", "-t", name],
        capture_output=True,
        check=False,
        text=True,
        timeout=TMUX_COMMAND_TIMEOUT_SECONDS,
    )
