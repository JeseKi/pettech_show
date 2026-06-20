# -*- coding: utf-8 -*-
from __future__ import annotations

import subprocess
from typing import Any

from src.server.tmux_cleanup import cleanup_old_tmux_sessions, list_tmux_sessions


def test_cleanup_old_tmux_sessions_kills_only_expired(monkeypatch):
    calls: list[list[str]] = []

    def fake_run(args: list[str], **_: Any):
        calls.append(args)
        if args[:2] == ["tmux", "list-sessions"]:
            return subprocess.CompletedProcess(
                args,
                0,
                stdout=(
                    "old-session\t1000\n"
                    "fresh-session\t11000\n"
                    "malformed\n"
                    "bad-created\tnope\n"
                ),
                stderr="",
            )
        return subprocess.CompletedProcess(args, 0, stdout="", stderr="")

    monkeypatch.setattr(subprocess, "run", fake_run)

    killed = cleanup_old_tmux_sessions(ttl_seconds=10_800, now_epoch=12_000)

    assert killed == 1
    assert ["tmux", "kill-session", "-t", "old-session"] in calls
    assert ["tmux", "kill-session", "-t", "fresh-session"] not in calls


def test_list_tmux_sessions_skips_when_tmux_missing(monkeypatch):
    def fake_run(*_: Any, **__: Any):
        raise FileNotFoundError

    monkeypatch.setattr(subprocess, "run", fake_run)

    assert list_tmux_sessions() == []

