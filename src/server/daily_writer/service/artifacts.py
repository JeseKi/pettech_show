# -*- coding: utf-8 -*-
"""Filesystem artifact helpers for daily writer jobs."""

from __future__ import annotations

import shutil
from pathlib import Path

from src.server.config import global_config

from .constants import ARTWORK_SKILL_NAMES, DAILY_WRITER_SKILL_NAMES


def copy_source_artifacts(source_workdir: Path, target_workdir: Path) -> None:
    for name in ("raw", "material", "wiki"):
        source = source_workdir / name
        if source.exists():
            shutil.copytree(
                source,
                target_workdir / name,
                ignore=shutil.ignore_patterns("__pycache__"),
            )


def prepare_skill(workdir: Path, *, include_artwork: bool = False) -> None:
    skill_names = [
        *DAILY_WRITER_SKILL_NAMES,
        *(ARTWORK_SKILL_NAMES if include_artwork else []),
    ]
    _copy_skills(workdir, skill_names)
    if include_artwork:
        _copy_agent_assets(workdir)


def ensure_artwork_artifacts(workdir: Path) -> None:
    """Repair artwork-only agent assets for existing or resumed workdirs."""
    _copy_skills(workdir, ARTWORK_SKILL_NAMES)
    _copy_agent_assets(workdir)


def _copy_skills(workdir: Path, skill_names: list[str]) -> None:
    source_root = Path(global_config.project_root) / ".agents" / "skills"
    target_root = workdir / ".agents" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    for skill_name in _dedupe_skill_names(skill_names):
        source = source_root / skill_name
        if not source.exists():
            raise RuntimeError(f"Skill 不存在：{source}")
        target = target_root / skill_name
        _link_tree_or_copy(source, target)


def _copy_agent_assets(workdir: Path) -> None:
    source = Path(global_config.project_root) / ".agents" / "assets"
    if not source.exists():
        return
    target = workdir / ".agents" / "assets"
    _link_tree_or_copy(source, target)


def _link_tree_or_copy(source: Path, target: Path) -> None:
    _remove_existing(target)
    try:
        target.symlink_to(source, target_is_directory=True)
    except OSError:
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


def _remove_existing(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink()
    elif path.exists():
        shutil.rmtree(path)


def _dedupe_skill_names(skill_names: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for skill_name in skill_names:
        if skill_name in seen:
            continue
        seen.add(skill_name)
        deduped.append(skill_name)
    return deduped
