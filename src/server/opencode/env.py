# -*- coding: utf-8 -*-
"""Per-job OpenCode runtime environment helpers."""

from __future__ import annotations

import os
import shlex
from pathlib import Path
from typing import Mapping


XDG_HOME_DIRS: tuple[tuple[str, str], ...] = (
    ("XDG_DATA_HOME", "data"),
    ("XDG_CACHE_HOME", "cache"),
    ("XDG_STATE_HOME", "state"),
)


def runtime_root(workdir: Path) -> Path:
    return workdir / ".opencode-runtime"


def xdg_home_paths(workdir: Path) -> dict[str, Path]:
    root = runtime_root(workdir)
    return {env_name: root / dirname for env_name, dirname in XDG_HOME_DIRS}


def ensure_runtime_dirs(workdir: Path) -> None:
    for path in xdg_home_paths(workdir).values():
        path.mkdir(parents=True, exist_ok=True)


def isolated_env(
    workdir: Path, base: Mapping[str, str] | None = None
) -> dict[str, str]:
    env = dict(os.environ if base is None else base)
    ensure_runtime_dirs(workdir)
    for env_name, path in xdg_home_paths(workdir).items():
        env[env_name] = path.as_posix()
    return env


def shell_export_lines(workdir: Path) -> list[str]:
    ensure_runtime_dirs(workdir)
    paths = xdg_home_paths(workdir)
    mkdir_args = " ".join(shlex.quote(path.as_posix()) for path in paths.values())
    return [
        f"mkdir -p {mkdir_args} || exit 1",
        *[
            f"export {env_name}={shlex.quote(path.as_posix())}"
            for env_name, path in paths.items()
        ],
    ]
