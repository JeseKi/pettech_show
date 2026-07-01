# -*- coding: utf-8 -*-
from __future__ import annotations

from pathlib import Path

from src.server.config import global_config
from src.server.daily_writer.service.artifacts import ensure_artwork_artifacts, prepare_skill


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
    artwork_scripts = skill_root / "wechat-main-artwork-coordinator" / "scripts"
    artwork_scripts.mkdir()
    (artwork_scripts / "init_artwork.py").write_text("# init\n", encoding="utf-8")
    (artwork_scripts / "prepare_upload_images.py").write_text(
        "# prepare\n", encoding="utf-8"
    )

    monkeypatch.setattr(global_config, "project_root", project_root)
    workdir = tmp_path / "workdir"

    prepare_skill(workdir, include_artwork=True)

    assert (workdir / ".agents" / "skills" / "wechat-daily-writer").is_dir()
    assert not (workdir / ".agents" / "skills" / "wechat-daily-writer").is_symlink()
    assert (
        workdir / ".agents" / "skills" / "wechat-main-artwork-coordinator"
    ).is_dir()
    assert not (
        workdir / ".agents" / "skills" / "wechat-main-artwork-coordinator"
    ).is_symlink()
    assert (workdir / ".agents" / "assets").is_dir()
    assert not (workdir / ".agents" / "assets").is_symlink()
    assert (workdir / ".agents" / "assets" / "fonts" / "README.md").is_file()


def test_ensure_artwork_artifacts_repairs_existing_workdir(
    tmp_path: Path,
    monkeypatch,
):
    project_root = tmp_path / "project"
    skill_root = project_root / ".agents" / "skills"
    assets_root = project_root / ".agents" / "assets" / "fonts"
    assets_root.mkdir(parents=True)
    (assets_root / "README.md").write_text("fonts\n", encoding="utf-8")

    for skill_name in (
        "wechat-main-artwork-coordinator",
        "guizang-social-card-skill",
    ):
        skill_dir = skill_root / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# {skill_name}\n", encoding="utf-8")
    artwork_scripts = skill_root / "wechat-main-artwork-coordinator" / "scripts"
    artwork_scripts.mkdir()
    (artwork_scripts / "init_artwork.py").write_text("# init\n", encoding="utf-8")
    (artwork_scripts / "prepare_upload_images.py").write_text(
        "# prepare\n", encoding="utf-8"
    )

    monkeypatch.setattr(global_config, "project_root", project_root)
    workdir = tmp_path / "workdir"
    existing_skill = workdir / ".agents" / "skills" / "wechat-daily-writer"
    existing_skill.mkdir(parents=True)
    (existing_skill / "SKILL.md").write_text("# daily\n", encoding="utf-8")

    ensure_artwork_artifacts(workdir)

    assert (existing_skill / "SKILL.md").is_file()
    assert (
        workdir / ".agents" / "skills" / "wechat-main-artwork-coordinator"
    ).is_dir()
    assert not (
        workdir / ".agents" / "skills" / "wechat-main-artwork-coordinator"
    ).is_symlink()
    assert (
        workdir / ".agents" / "skills" / "guizang-social-card-skill"
    ).is_dir()
    assert not (
        workdir / ".agents" / "skills" / "guizang-social-card-skill"
    ).is_symlink()
    assert (workdir / ".agents" / "assets").is_dir()
    assert not (workdir / ".agents" / "assets").is_symlink()
    assert (
        workdir
        / ".agents"
        / "skills"
        / "wechat-main-artwork-coordinator"
        / "SKILL.md"
    ).is_file()
    assert (
        workdir / ".agents" / "skills" / "guizang-social-card-skill" / "SKILL.md"
    ).is_file()
    assert (workdir / ".agents" / "assets" / "fonts" / "README.md").is_file()
