# -*- coding: utf-8 -*-
"""Filesystem artifact helpers for daily writer jobs."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.server.config import global_config

from .constants import DAILY_WRITER_SKILL_NAME


def copy_source_artifacts(source_workdir: Path, target_workdir: Path) -> None:
    for name in ("raw", "material", "wiki"):
        source = source_workdir / name
        if source.exists():
            shutil.copytree(
                source,
                target_workdir / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )


def prepare_skill(workdir: Path) -> None:
    source_root = Path(global_config.project_root) / ".agents" / "skills"
    source = source_root / DAILY_WRITER_SKILL_NAME
    if not source.exists():
        raise RuntimeError(f"Skill 不存在：{source}")
    target = workdir / ".agents" / "skills" / DAILY_WRITER_SKILL_NAME
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))

