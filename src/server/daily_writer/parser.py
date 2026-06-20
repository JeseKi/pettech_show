# -*- coding: utf-8 -*-
"""Parse and validate generated daily writer artifacts."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .schemas import DailyWriterResultOut, DailyWriterVariantOut

IMAGE_PATTERNS = [
    re.compile(r"!\[[^\]]*]\([^)]*\)"),
    re.compile(r"<img\b", re.IGNORECASE),
    re.compile(r"二维码|QR\s*code", re.IGNORECASE),
]


def parse_daily_writer_result(
    *,
    job_id: str,
    source_seed_matrix_job_id: str,
    source_aiwiki_job_id: str,
    seed_id: str,
    workdir: Path,
    article_path: str | None,
    metadata_path: str | None,
) -> DailyWriterResultOut:
    resolved_article, resolved_metadata = resolve_result_paths(
        workdir, article_path=article_path, metadata_path=metadata_path
    )
    markdown = resolved_article.read_text(encoding="utf-8")
    metadata = json.loads(resolved_metadata.read_text(encoding="utf-8"))
    validate_result(markdown, metadata, resolved_article, resolved_metadata)
    variants = parse_variants(resolved_metadata.parent, workdir)
    article_rel = resolved_article.relative_to(workdir).as_posix()
    metadata_rel = resolved_metadata.relative_to(workdir).as_posix()
    return DailyWriterResultOut(
        job_id=job_id,
        source_seed_matrix_job_id=source_seed_matrix_job_id,
        source_aiwiki_job_id=source_aiwiki_job_id,
        seed_id=seed_id,
        article_path=article_rel,
        metadata_path=metadata_rel,
        markdown=markdown,
        metadata=metadata,
        summary=build_summary(metadata, markdown, variants),
        variants=variants,
    )


def resolve_result_paths(
    workdir: Path, *, article_path: str | None, metadata_path: str | None
) -> tuple[Path, Path]:
    if article_path and metadata_path:
        article = workdir / article_path
        metadata = workdir / metadata_path
        if article.is_file() and metadata.is_file():
            return article, metadata

    candidates = sorted((workdir / "main").glob("*/*/metadata.json"))
    if not candidates:
        raise FileNotFoundError("长文 metadata.json 尚未生成")
    metadata = candidates[-1]
    article = metadata.parent / "main.md"
    if not article.is_file():
        raise FileNotFoundError("长文 main.md 尚未生成")
    return article, metadata


def validate_result(
    markdown: str, metadata: dict[str, Any], article_path: Path, metadata_path: Path
) -> None:
    for pattern in IMAGE_PATTERNS:
        if pattern.search(markdown):
            raise ValueError("main.md 包含图片语法、图片标签或二维码内容")

    output_id = str(metadata.get("output_id") or "")
    if not output_id:
        raise ValueError("metadata.json 缺少 output_id")
    if article_path.name != "main.md" or metadata_path.name != "metadata.json":
        raise ValueError("长文结果路径不符合 main.md / metadata.json 约定")
    if metadata_path.parent.name != output_id:
        raise ValueError("metadata.json output_id 与输出目录不一致")

    for required_key in ("topic", "pain_point", "solution", "hook", "article"):
        if required_key not in metadata:
            raise ValueError(f"metadata.json 缺少字段：{required_key}")
    article = metadata.get("article")
    if not isinstance(article, dict):
        raise ValueError("metadata.json article 必须是对象")
    if article.get("file") != "main.md":
        raise ValueError("metadata.json article.file 必须是 main.md")


def parse_variants(article_dir: Path, workdir: Path) -> list[DailyWriterVariantOut]:
    variants_dir = article_dir / "variants"
    if not variants_dir.is_dir():
        return []

    variants: list[DailyWriterVariantOut] = []
    for run_dir in sorted(path for path in variants_dir.iterdir() if path.is_dir()):
        markdown_path = run_dir / "output" / "others.md"
        metadata_path = run_dir / "output" / "metadata.json"
        if not markdown_path.is_file() or not metadata_path.is_file():
            continue
        try:
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        markdown = markdown_path.read_text(encoding="utf-8")
        angle = _variant_angle(metadata, run_dir)
        variants.append(
            DailyWriterVariantOut(
                angle=angle,
                directory=run_dir.relative_to(workdir).as_posix(),
                markdown_path=markdown_path.relative_to(workdir).as_posix(),
                metadata_path=metadata_path.relative_to(workdir).as_posix(),
                markdown=markdown,
                metadata=metadata,
            )
        )
    return variants


def build_summary(
    metadata: dict[str, Any],
    markdown: str,
    variants: list[DailyWriterVariantOut] | None = None,
) -> dict[str, Any]:
    article = metadata.get("article") if isinstance(metadata.get("article"), dict) else {}
    tags = article.get("tags") if isinstance(article, dict) else []
    search_intents = article.get("search_intents") if isinstance(article, dict) else []
    materials_used = article.get("materials_used") if isinstance(article, dict) else []
    variant_count = len(variants or [])
    return {
        "output_id": metadata.get("output_id") or "",
        "topic": metadata.get("topic") or "",
        "title": article.get("title") if isinstance(article, dict) else "",
        "summary": article.get("summary") if isinstance(article, dict) else "",
        "tag_count": len(tags) if isinstance(tags, list) else 0,
        "search_intent_count": len(search_intents) if isinstance(search_intents, list) else 0,
        "material_count": len(materials_used) if isinstance(materials_used, list) else 0,
        "character_count": len(markdown),
        "variant_success_count": variant_count,
        "variant_status": "completed" if variant_count else "not_requested",
    }


def _variant_angle(metadata: dict[str, Any], run_dir: Path) -> str:
    label = metadata.get("audience_label")
    if isinstance(label, str) and label.strip():
        return label.strip()
    article = metadata.get("article")
    if isinstance(article, dict):
        title = article.get("title")
        if isinstance(title, str) and title.strip():
            return title.strip()
    return run_dir.name
