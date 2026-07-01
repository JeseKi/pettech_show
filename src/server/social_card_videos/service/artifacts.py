# -*- coding: utf-8 -*-
"""Filesystem artifact helpers for social card video jobs."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from fastapi import HTTPException, UploadFile, status

from src.server.config import global_config
from src.server.social_cards.models import SocialCardJob

from .constants import AUDIO_EXTENSIONS, MAX_BGM_UPLOAD_BYTES, VIDEO_SKILL_NAMES


def copy_source_cards(source_job: SocialCardJob, target_workdir: Path) -> list[dict[str, Any]]:
    source_workdir = Path(source_job.workdir)
    source_root = target_workdir / "source"
    source_root.mkdir(parents=True, exist_ok=True)
    deck_specs: list[dict[str, Any]] = []
    main_deck = source_workdir / "xhs_guizang"
    if main_deck.is_dir():
        _copy_deck(main_deck, source_root / "xhs_guizang")
        deck_specs.append({"label": "post_01", "deck_dir": "source/xhs_guizang"})
    variants_root = source_workdir / "xhs_guizang_variants"
    if variants_root.is_dir():
        for index, variant in enumerate(sorted(variants_root.glob("variant-*")), start=2):
            if not variant.is_dir():
                continue
            target = source_root / "xhs_guizang_variants" / variant.name
            _copy_deck(variant, target)
            deck_specs.append({"label": f"post_{index:02d}", "deck_dir": target.relative_to(target_workdir).as_posix()})
    if not deck_specs:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图文任务没有可用于视频的输出目录")
    (source_root / "source_job.json").write_text(
        json.dumps(
            {"source_social_card_job_id": source_job.id, "source_workdir": source_job.workdir},
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return deck_specs


def _copy_deck(source: Path, target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)
    ignore = shutil.ignore_patterns("__pycache__", "video", "*.zip")
    shutil.copytree(source, target, ignore=ignore)


def prepare_skill(workdir: Path) -> None:
    source_root = Path(global_config.project_root) / ".agents" / "skills"
    target_root = workdir / ".agents" / "skills"
    target_root.mkdir(parents=True, exist_ok=True)
    for skill_name in VIDEO_SKILL_NAMES:
        source = source_root / skill_name
        if not source.exists():
            raise RuntimeError(f"Skill 不存在：{source}")
        target = target_root / skill_name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))
    _copy_agent_assets(workdir)


def _copy_agent_assets(workdir: Path) -> None:
    source = Path(global_config.project_root) / ".agents" / "assets"
    if not source.exists():
        return
    target = workdir / ".agents" / "assets"
    if target.exists():
        shutil.rmtree(target)
    shutil.copytree(source, target, ignore=shutil.ignore_patterns("__pycache__"))


async def save_bgm_upload(workdir: Path, file: UploadFile | None) -> str | None:
    if file is None:
        return None
    filename = _safe_audio_filename(file.filename or "bgm.mp3")
    content_type = file.content_type or ""
    extension = Path(filename).suffix.lower()
    if not content_type.startswith("audio/") and extension not in AUDIO_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只支持上传音频文件作为 BGM")
    content = await file.read(MAX_BGM_UPLOAD_BYTES + 1)
    if len(content) > MAX_BGM_UPLOAD_BYTES:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="BGM 文件不能超过 80MB")
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="BGM 文件为空")
    upload_dir = workdir / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)
    target = upload_dir / filename
    target.write_bytes(content)
    return target.relative_to(workdir).as_posix()


def write_video_config(
    workdir: Path,
    *,
    deck_specs: list[dict[str, Any]],
    title: str,
    voice_text: str,
    bgm_path: str | None,
    bgm_start: float,
) -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "title": title.strip(),
        "voice_text": voice_text.strip(),
        "write_video_md": True,
    }
    if bgm_path:
        defaults["bgm_source"] = bgm_path
        defaults["bgm_start"] = max(0.0, float(bgm_start))
    jobs = [
        {
            "label": spec["label"],
            "image_dir": f"{spec['deck_dir']}/output",
            "output_dir": spec["deck_dir"],
        }
        for spec in deck_specs
    ]
    config: dict[str, Any]
    if len(jobs) == 1:
        config = {**defaults, **jobs[0]}
    else:
        config = {
            "defaults": defaults,
            "shared_asset_dir": "shared_video_assets",
            "jobs": jobs,
        }
    (workdir / "video-config.json").write_text(
        json.dumps(config, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def _safe_audio_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace("\\", "_").replace("/", "_")
    if not name:
        return "bgm.mp3"
    suffix = Path(name).suffix.lower()
    if suffix not in AUDIO_EXTENSIONS:
        return f"{name[:120]}.mp3"
    return name[:160]
