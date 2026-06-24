# -*- coding: utf-8 -*-
"""Post-generation check helpers for AI task workspaces."""

from __future__ import annotations

import shlex
import subprocess
import sys
from pathlib import Path

from .logs import append_log


def run_check_command(workdir: Path, args: list[str], *, label: str) -> None:
    append_log(workdir, "$ " + " ".join(shlex.quote(arg) for arg in args))
    process = subprocess.run(
        args,
        cwd=workdir,
        check=False,
        capture_output=True,
        text=True,
    )
    output = "\n".join(
        part for part in (process.stdout.strip(), process.stderr.strip()) if part
    )
    if output:
        append_log(workdir, output)
    if process.returncode != 0:
        raise RuntimeError(f"{label} 失败：{output or process.returncode}")


def python_args(script: Path | str, *args: str) -> list[str]:
    return [sys.executable, Path(script).as_posix(), *args]
