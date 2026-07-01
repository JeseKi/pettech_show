# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from src.server.config import global_config
from src.server.daily_writer.service.artifacts import prepare_skill


def test_prepare_skill_copies_agent_assets_for_artwork(
    tmp_path: Path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    skill_root = project_root / ".agents" / "skills"
    assets_root = project_root / ".agents" / "assets" / "fonts"
    assets_root.mkdir(parents=True)
    (assets_root / "README.md").write_text("fonts\n", encoding="utf-8")

    for skill_name in (
        "wechat-daily-writer",
        "wechat-main-variant-batch-rewriter",
        "wechat-main-variant-rewriter",
        "wechat-main-artwork-coordinator",
        "guizang-social-card-skill",
    ):
        skill_dir = skill_root / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")

    monkeypatch.setattr(global_config, "project_root", project_root)
    workdir = tmp_path / "workdir"

    prepare_skill(workdir, include_artwork=True)

    assert (workdir / ".agents" / "assets" / "fonts" / "README.md").is_file()
