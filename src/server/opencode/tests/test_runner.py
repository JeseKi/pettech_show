# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from pathlib import Path

from src.server.aiwiki.service.progress import initial_progress, write_progress
from src.server.config import global_config
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
