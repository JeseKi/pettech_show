# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from src.server.config import global_config
from src.server.social_card_videos.service.artifacts import prepare_skill


def test_prepare_skill_copies_agent_assets(tmp_path: Path, monkeypatch):
    project_root = tmp_path / "project"
    skill_dir = project_root / ".agents" / "skills" / "xhs-slideshow-video-maker"
    font_dir = project_root / ".agents" / "assets" / "fonts"
    skill_dir.mkdir(parents=True)
    font_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# video\n", encoding="utf-8")
    (font_dir / "README.md").write_text("fonts\n", encoding="utf-8")

    monkeypatch.setattr(global_config, "project_root", project_root)
    workdir = tmp_path / "workdir"

    prepare_skill(workdir)

    assert (workdir / ".agents" / "assets" / "fonts" / "README.md").is_file()
