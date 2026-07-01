# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from src.server.aiwiki.service.progress import initial_progress, write_progress
from src.server.config import global_config
from src.server.opencode import sessions, tmux
from src.server.opencode import runner


def test_recovers_when_tmux_exits_without_status(
    tmp_path: Path,
    monkeypatch,
):
    workdir = tmp_path / "job"
    workdir.mkdir()
    write_progress(workdir, initial_progress())
    attempts = {"count": 0}

    def fake_start_tmux_session(name: str, script_path: Path) -> None:
        attempts["count"] += 1
        if attempts["count"] != 2:
            return
        progress = json.loads((workdir / "progress.json").read_text(encoding="utf-8"))
        events = progress.get("events")
        if not isinstance(events, list):
            events = []
        events.append({"event": "完成", "step": "全部", "summary": "任务完成"})
        write_progress(
            workdir,
            {
                "status": "completed",
                "current_step": "任务完成",
                "events": events,
            },
        )

    monkeypatch.setattr(global_config, "aiwiki_opencode_command", "opencode")
    monkeypatch.setattr(global_config, "aiwiki_task_timeout_seconds", 5)
    monkeypatch.setattr(runner, "start_tmux_session", fake_start_tmux_session)
    monkeypatch.setattr(runner, "tmux_session_exists", lambda name: False)
    monkeypatch.setattr(runner, "_wait_for_status", lambda status_path: None)
    monkeypatch.setattr(runner, "persist_session_id", lambda *args, **kwargs: None)

    runner.run_opencode_in_tmux(
        workdir,
        title="Capability generation",
        prompt="生成内容",
        max_resume_attempts=1,
    )

    assert attempts["count"] == 2
    progress = json.loads((workdir / "progress.json").read_text(encoding="utf-8"))
    assert progress["status"] == "completed"
    assert any(event["step"] == "恢复 OpenCode" for event in progress["events"])
    log_text = (workdir / "logs" / "opencode.log").read_text(encoding="utf-8")
    assert "未写入退出状态" in log_text
    assert "Capability generation resume" in log_text


def test_tmux_script_isolates_opencode_xdg_homes(tmp_path: Path):
    workdir = tmp_path / "job"
    workdir.mkdir()

    script = tmux.build_tmux_script(
        args=["opencode", "run"],
        prompt_path=workdir / "logs" / "prompt.md",
        status_path=workdir / "logs" / "status.json",
        log_path=workdir / "logs" / "opencode.log",
        workdir=workdir,
    )

    runtime_root = workdir / ".opencode-runtime"
    assert f"export XDG_DATA_HOME={runtime_root / 'data'}" in script
    assert f"export XDG_CACHE_HOME={runtime_root / 'cache'}" in script
    assert f"export XDG_STATE_HOME={runtime_root / 'state'}" in script
    assert "XDG_CONFIG_HOME" not in script


def test_session_list_uses_isolated_opencode_env(tmp_path: Path, monkeypatch):
    workdir = tmp_path / "job"
    workdir.mkdir()
    captured = {}

    class Result:
        returncode = 0
        stdout = "[]"

    def fake_run(*args, **kwargs):
        captured["env"] = kwargs["env"]
        return Result()

    monkeypatch.setattr(global_config, "aiwiki_opencode_command", "opencode")
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.setattr(sessions.subprocess, "run", fake_run)

    assert sessions._list_opencode_sessions(workdir) == []

    runtime_root = workdir / ".opencode-runtime"
    env = captured["env"]
    assert env["XDG_DATA_HOME"] == (runtime_root / "data").as_posix()
    assert env["XDG_CACHE_HOME"] == (runtime_root / "cache").as_posix()
    assert env["XDG_STATE_HOME"] == (runtime_root / "state").as_posix()
    assert "XDG_CONFIG_HOME" not in env


def test_session_ids_can_be_scoped_by_task_stage(tmp_path: Path):
    workdir = tmp_path / "job"
    workdir.mkdir()

    (workdir / ".session").write_text("ses_main\n", encoding="utf-8")
    (workdir / ".session-long-article-artwork-generation").write_text(
        "ses_artwork\n",
        encoding="utf-8",
    )

    assert sessions.read_session_id(workdir) == "ses_main"
    assert (
        sessions.read_session_id(workdir, key="Long article artwork generation")
        == "ses_artwork"
    )
    assert sessions.read_session_id(workdir, key="Long article variant generation") is None


def test_runner_resumes_with_scoped_session_id(tmp_path: Path, monkeypatch):
    workdir = tmp_path / "job"
    workdir.mkdir()
    write_progress(workdir, initial_progress())
    (workdir / ".session").write_text("ses_main\n", encoding="utf-8")
    (workdir / ".session-long-article-artwork-generation").write_text(
        "ses_artwork\n",
        encoding="utf-8",
    )
    calls = []

    def fake_run_opencode_attempt(workdir_arg: Path, **kwargs):
        calls.append(kwargs)
        return ("exited" if len(calls) == 1 else "completed", workdir_arg / "prompt.md")

    monkeypatch.setattr(runner, "_run_opencode_attempt", fake_run_opencode_attempt)

    runner.run_opencode_in_tmux(
        workdir,
        title="Long article artwork generation",
        prompt="生成插图",
        max_resume_attempts=1,
        session_key="Long article artwork generation",
    )

    assert calls[0]["session_id"] is None
    assert calls[1]["session_id"] == "ses_artwork"
    assert calls[1]["prompt"] == "继续"
    assert calls[1]["title"] == "Long article artwork generation resume"
