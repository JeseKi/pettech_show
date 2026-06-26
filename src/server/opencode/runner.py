# -*- coding: utf-8 -*-
"""OpenCode lifecycle runner backed by tmux."""

from __future__ import annotations

import json
import shlex
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path

from src.server.aiwiki.service.constants import (
    LEGACY_PROGRESS_COMPLETE_EVENT,
    PROGRESS_COMPLETE_EVENT,
)
from src.server.aiwiki.service.logs import append_log
from src.server.aiwiki.service.progress import mark_progress_running, read_progress
from src.server.config import global_config

from .constants import POLL_INTERVAL_SECONDS
from .sessions import persist_session_id, read_session_id
from .tmux import (
    build_tmux_script,
    kill_tmux_session,
    session_name,
    start_tmux_session,
    tmux_session_exists,
)


def run_opencode_in_tmux(
    workdir: Path,
    *,
    title: str,
    prompt: str,
    resume_prompt: str | None = None,
    max_resume_attempts: int = 1,
) -> None:
    initial_prompt_path: Path | None = None
    attempt_title = title
    attempt_prompt = prompt
    for attempt in range(max_resume_attempts + 1):
        session_id = read_session_id(workdir) if attempt > 0 else None
        result, prompt_path = _run_opencode_attempt(
            workdir,
            title=attempt_title,
            prompt=attempt_prompt,
            session_id=session_id,
        )
        if initial_prompt_path is None:
            initial_prompt_path = prompt_path
        if result == "completed":
            return
        if attempt >= max_resume_attempts:
            return
        append_log(
            workdir,
            "RECOVERY: OpenCode 已退出但 progress.json 未完成，"
            "将在同一工作目录拉起新的 tmux session 继续执行。",
        )
        mark_progress_running(
            workdir,
            step="恢复 OpenCode",
            summary="OpenCode 已退出但任务未完成，正在同一工作目录继续执行",
        )
        attempt_title = f"{title} resume"
        if read_session_id(workdir):
            attempt_prompt = "继续"
        else:
            attempt_prompt = resume_prompt or _build_generic_resume_prompt(
                workdir,
                initial_prompt_path=initial_prompt_path,
            )


def _run_opencode_attempt(
    workdir: Path, *, title: str, prompt: str, session_id: str | None = None
) -> tuple[str, Path]:
    args = _opencode_args(workdir, title=title, session_id=session_id)
    logs_dir = workdir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    run_id = _new_run_id()
    prompt_path = logs_dir / f"opencode-prompt-{run_id}.md"
    script_path = logs_dir / f"opencode-tmux-{run_id}.sh"
    status_path = logs_dir / f"opencode-status-{run_id}.json"
    log_path = logs_dir / "opencode.log"
    tmux_name = session_name(workdir, title, run_id)

    prompt_path.write_text(prompt, encoding="utf-8")
    script_path.write_text(
        build_tmux_script(
            args=args,
            prompt_path=prompt_path,
            status_path=status_path,
            log_path=log_path,
            workdir=workdir,
        ),
        encoding="utf-8",
    )
    script_path.chmod(0o700)

    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args) + " <prompt>")
    append_log(workdir, _tmux_command_log(tmux_name, script_path))
    baseline_event_count = _progress_event_count(workdir)
    started_after_ms = int(datetime.now(timezone.utc).timestamp() * 1000)
    next_session_probe = 0.0
    start_tmux_session(tmux_name, script_path)
    deadline = datetime.now(timezone.utc).timestamp() + global_config.aiwiki_task_timeout_seconds

    while True:
        now = datetime.now(timezone.utc).timestamp()
        if not read_session_id(workdir) and now >= next_session_probe:
            persist_session_id(workdir, title=title, started_after_ms=started_after_ms)
            next_session_probe = now + 1

        if _progress_marked_complete_after(workdir, baseline_event_count):
            append_log(workdir, "progress.json 已标记任务完成，后端结束 tmux OpenCode session 并解析结果。")
            persist_session_id(workdir, title=title, started_after_ms=started_after_ms)
            kill_tmux_session(tmux_name)
            return "completed", prompt_path

        status_payload = _read_status(status_path)
        if status_payload is not None:
            return _handle_finished_status(
                workdir,
                status_payload=status_payload,
                title=title,
                started_after_ms=started_after_ms,
                prompt_path=prompt_path,
            )

        if datetime.now(timezone.utc).timestamp() > deadline:
            kill_tmux_session(tmux_name)
            raise RuntimeError("OpenCode 执行超时")

        if not tmux_session_exists(tmux_name):
            status_payload = _wait_for_status(status_path)
            if status_payload is not None:
                return _handle_finished_status(
                    workdir,
                    status_payload=status_payload,
                    title=title,
                    started_after_ms=started_after_ms,
                    prompt_path=prompt_path,
                )
            persist_session_id(workdir, title=title, started_after_ms=started_after_ms)
            append_log(
                workdir,
                "RECOVERY: OpenCode tmux session 已结束但未写入退出状态，"
                "将按未完成任务处理并尝试恢复。",
            )
            return "exited", prompt_path

        time.sleep(POLL_INTERVAL_SECONDS)


def _opencode_args(workdir: Path, *, title: str, session_id: str | None) -> list[str]:
    command = shlex.split(global_config.aiwiki_opencode_command)
    if not command:
        raise RuntimeError("AIWIKI_OPENCODE_COMMAND 不能为空")
    args = [*command, "run", "--dir", workdir.as_posix(), "--title", title]
    if session_id:
        args.extend(["--session", session_id])
    if global_config.aiwiki_opencode_model:
        args.extend(["--model", global_config.aiwiki_opencode_model])
    if global_config.aiwiki_opencode_agent:
        args.extend(["--agent", global_config.aiwiki_opencode_agent])
    if global_config.aiwiki_opencode_extra_args:
        args.extend(shlex.split(global_config.aiwiki_opencode_extra_args))
    return args


def _handle_finished_status(
    workdir: Path,
    *,
    status_payload: dict[str, object],
    title: str,
    started_after_ms: int,
    prompt_path: Path,
) -> tuple[str, Path]:
    exit_code = _coerce_exit_code(status_payload.get("exit_code"))
    persist_session_id(workdir, title=title, started_after_ms=started_after_ms)
    if exit_code != 0:
        raise RuntimeError(f"OpenCode 执行失败，退出码 {exit_code}")
    if _progress_marked_complete_after(workdir, 0):
        append_log(workdir, "progress.json 已在 OpenCode 退出时标记任务完成，后端直接解析结果。")
        return "completed", prompt_path
    return "exited", prompt_path


def _tmux_command_log(tmux_name: str, script_path: Path) -> str:
    command = [
        "tmux",
        "new-session",
        "-d",
        "-s",
        tmux_name,
        "bash",
        "-lc",
        f"exec bash {shlex.quote(script_path.as_posix())}",
    ]
    return "$ " + " ".join(shlex.quote(arg) for arg in command)


def _new_run_id() -> str:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S%f")
    return f"{timestamp}-{uuid.uuid4().hex[:8]}"


def _progress_event_count(workdir: Path) -> int:
    events = read_progress(workdir).get("events")
    return len(events) if isinstance(events, list) else 0


def _progress_marked_complete_after(workdir: Path, baseline_event_count: int) -> bool:
    progress = read_progress(workdir)
    events = progress.get("events")
    if (
        progress.get("status") != "completed"
        or progress.get("current_step") != "任务完成"
        or not isinstance(events, list)
        or len(events) <= baseline_event_count
        or not isinstance(events[-1], dict)
    ):
        return False
    return any(
        all(events[-1].get(key) == value for key, value in complete_event.items())
        for complete_event in (PROGRESS_COMPLETE_EVENT, LEGACY_PROGRESS_COMPLETE_EVENT)
    )


def _read_status(status_path: Path) -> dict[str, object] | None:
    if not status_path.exists():
        return None
    try:
        payload = json.loads(status_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _wait_for_status(
    status_path: Path, *, timeout_seconds: float = 2.0
) -> dict[str, object] | None:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        status_payload = _read_status(status_path)
        if status_payload is not None:
            return status_payload
        time.sleep(0.05)
    return _read_status(status_path)


def _coerce_exit_code(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        try:
            return int(value)
        except ValueError:
            return 1
    return 1


def _build_generic_resume_prompt(workdir: Path, *, initial_prompt_path: Path) -> str:
    return f"""
你在一个 OpenCode 任务的续跑 tmux session 中工作：{workdir.as_posix()}

上一轮 OpenCode 已退出，但当前目录的 `progress.json` 尚未写入 completed。

请严格只读写当前目录内的文件，不要访问或修改其他项目目录。

必须先读取：
1. `progress.json`
2. 原始任务 prompt：`{initial_prompt_path.relative_to(workdir).as_posix()}`
3. 当前目录中已经生成的文件和日志

续跑要求：
- 不要从零重做；基于当前目录已有文件继续完成原始任务。
- 必须保留 `progress.json` 中已有 `events`，只能在末尾追加新事件。
- 禁止清空、重置、重建或删除已有 `events`。
- 如果发现某一步已经产出文件，优先校验并补齐缺失部分，不要无意义覆盖。
- 修复完成后，必须按原始任务 prompt 的输出契约校验产物。
- 全部完成后，必须把 `progress.json` 的 `status` 设为 `completed`，`current_step` 设为 `任务完成`，且最后一个事件必须精确为 `{{"event":"完成","step":"全部","summary":"任务完成"}}`。
- 如果仍然失败，必须把失败原因写入当前目录的 `progress.json` 和日志。
- 完成后直接结束，不要等待用户继续输入。
""".strip()
