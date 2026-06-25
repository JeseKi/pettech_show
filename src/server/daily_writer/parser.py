# -*- coding: utf-8 -*-
"""Parse and validate generated daily writer artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .schemas import (
    DailyWriterArtworkAssetOut,
    DailyWriterArtworkOut,
    DailyWriterResultOut,
    DailyWriterVariantOut,
)

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def parse_daily_writer_result(
    *,
    job_id: str,
    source_seed_matrix_job_id: str,
    source_aiwiki_job_id: str,
    seed_id: str,
    workdir: Path,
    article_path: str | None,
    metadata_path: str | None,
    write_artwork_assets: bool = False,
) -> DailyWriterResultOut:
    resolved_article, resolved_metadata = resolve_result_paths(
        workdir, article_path=article_path, metadata_path=metadata_path
    )
    markdown = resolved_article.read_text(encoding="utf-8")
    metadata = json.loads(resolved_metadata.read_text(encoding="utf-8"))
    validate_result(markdown, metadata, resolved_article, resolved_metadata)
    artwork = parse_artwork_assets(
        job_id=job_id,
        workdir=workdir,
        article_dir=resolved_metadata.parent,
        write_assets=write_artwork_assets,
    )
    variants = parse_variants(resolved_metadata.parent, workdir, artwork=artwork)
    illustrated_markdown = build_illustrated_markdown(markdown, artwork)
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
        illustrated_markdown=illustrated_markdown,
        metadata=metadata,
        summary=build_summary(metadata, markdown, variants, artwork),
        variants=variants,
        artwork=artwork,
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


def parse_variants(
    article_dir: Path, workdir: Path, *, artwork: DailyWriterArtworkOut | None = None
) -> list[DailyWriterVariantOut]:
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
                illustrated_markdown=build_illustrated_markdown(markdown, artwork),
                metadata=metadata,
            )
        )
    return variants


def build_illustrated_markdown(
    markdown: str, artwork: DailyWriterArtworkOut | None
) -> str:
    if artwork is None or not (artwork.cover_images or artwork.inline_images):
        return markdown

    blocks = _markdown_blocks(markdown)
    if not blocks:
        blocks = [markdown]

    output: list[str] = []
    cover = _preferred_cover_image(artwork.cover_images)
    if cover is not None:
        output.append(_artwork_markdown_image(cover))

    inline_images = list(artwork.inline_images)
    insert_after = _inline_insert_positions(len(blocks), inline_images)
    for index, block in enumerate(blocks, start=1):
        output.append(block)
        for image in insert_after.get(index, []):
            output.append(_artwork_markdown_image(image))

    return "\n\n".join(item.strip() for item in output if item.strip())


def parse_artwork_assets(
    *,
    job_id: str,
    workdir: Path,
    article_dir: Path,
    write_assets: bool = False,
) -> DailyWriterArtworkOut:
    candidates = list(_artwork_candidates(article_dir))
    seen: set[Path] = set()
    grouped: dict[str, list[Path]] = {"cover": [], "inline": []}
    for kind, path in candidates:
        resolved = _trusted_image_path(path, workdir)
        if resolved in seen:
            continue
        seen.add(resolved)
        grouped[kind].append(resolved)

    cover_images = _artwork_asset_outputs(job_id, "cover", grouped["cover"])
    inline_images = _artwork_asset_outputs(job_id, "inline", grouped["inline"])

    assets_path = article_dir / "artwork" / "output" / "assets.json"
    assets_rel: str | None = None
    if write_assets and (cover_images or inline_images):
        assets_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "input_mode": "filesystem",
            "output_id": article_dir.name,
            "cover_image_path": cover_images[0].path if cover_images else "",
            "inline_image_paths": [asset.path for asset in inline_images],
            "cover_images": [asset.model_dump() for asset in cover_images],
            "inline_images": [asset.model_dump() for asset in inline_images],
        }
        assets_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if assets_path.is_file():
        assets_rel = assets_path.relative_to(workdir).as_posix()

    return DailyWriterArtworkOut(
        cover_images=cover_images,
        inline_images=inline_images,
        assets_path=assets_rel,
    )


def resolve_artwork_asset_path(
    *,
    job_id: str,
    workdir: Path,
    article_dir: Path,
    asset_key: str,
) -> tuple[Path, str]:
    artwork = parse_artwork_assets(
        job_id=job_id,
        workdir=workdir,
        article_dir=article_dir,
        write_assets=False,
    )
    for asset in [*artwork.cover_images, *artwork.inline_images]:
        if asset.key == asset_key:
            return Path(asset.path), asset.content_type
    raise FileNotFoundError("Artwork 图片不存在")


def build_summary(
    metadata: dict[str, Any],
    markdown: str,
    variants: list[DailyWriterVariantOut] | None = None,
    artwork: DailyWriterArtworkOut | None = None,
) -> dict[str, Any]:
    article = metadata.get("article") if isinstance(metadata.get("article"), dict) else {}
    tags = article.get("tags") if isinstance(article, dict) else []
    search_intents = article.get("search_intents") if isinstance(article, dict) else []
    materials_used = article.get("materials_used") if isinstance(article, dict) else []
    variant_count = len(variants or [])
    cover_count = len(artwork.cover_images) if artwork else 0
    inline_count = len(artwork.inline_images) if artwork else 0
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
        "artwork_cover_count": cover_count,
        "artwork_inline_count": inline_count,
        "artwork_status": "completed" if cover_count or inline_count else "not_requested",
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


def _markdown_blocks(markdown: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in markdown.splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            blocks.append("\n".join(current))
            current = []
    if current:
        blocks.append("\n".join(current))
    return blocks


def _preferred_cover_image(
    cover_images: list[DailyWriterArtworkAssetOut],
) -> DailyWriterArtworkAssetOut | None:
    if not cover_images:
        return None
    for image in cover_images:
        filename = image.filename.lower()
        if "21x9" in filename or "cover-21" in filename:
            return image
    return cover_images[0]


def _inline_insert_positions(
    block_count: int, images: list[DailyWriterArtworkAssetOut]
) -> dict[int, list[DailyWriterArtworkAssetOut]]:
    image_count = len(images)
    if block_count < 1 or image_count < 1:
        return {}
    interval = max(1, block_count // (image_count + 1))
    positions: dict[int, list[DailyWriterArtworkAssetOut]] = {}
    for index, image in enumerate(images):
        position = min(block_count, max(1, (index + 1) * interval))
        positions.setdefault(position, []).append(image)
    return positions


def _artwork_markdown_image(asset: DailyWriterArtworkAssetOut) -> str:
    return f"![{asset.filename}](daily-writer-artwork:{asset.key})"


def _artwork_candidates(article_dir: Path) -> list[tuple[str, Path]]:
    manifest_candidates = _artwork_upload_manifest_candidates(article_dir)
    if manifest_candidates:
        return manifest_candidates

    artwork_dir = article_dir / "artwork"
    upload_candidates: list[tuple[str, Path]] = []
    for path in sorted((artwork_dir / "upload_ready").glob("*")):
        if not path.is_file() or path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        kind = "cover" if "cover" in path.stem.lower() else "inline"
        upload_candidates.append((kind, path))
    if upload_candidates:
        return upload_candidates

    candidates: list[tuple[str, Path]] = []
    for path in sorted((artwork_dir / "cover" / "images").glob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            candidates.append(("cover", path))
    for path in sorted((artwork_dir / "illustrations" / "images").glob("*")):
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            candidates.append(("inline", path))
    return candidates


def _artwork_upload_manifest_candidates(article_dir: Path) -> list[tuple[str, Path]]:
    manifest_path = article_dir / "artwork" / "upload_ready" / "manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    images = manifest.get("images")
    if not isinstance(images, list):
        return []

    candidates: list[tuple[str, Path]] = []
    for item in images:
        if not isinstance(item, dict):
            continue
        upload_path = item.get("upload_path")
        if not isinstance(upload_path, str) or not upload_path:
            continue
        source = str(item.get("source") or "").replace("\\", "/")
        if "/cover/images/" in source:
            kind = "cover"
        elif "/illustrations/images/" in source:
            kind = "inline"
        else:
            kind = "cover" if "cover" in Path(upload_path).stem.lower() else "inline"
        candidates.append((kind, Path(upload_path)))
    return candidates


def _trusted_image_path(path: Path, workdir: Path) -> Path:
    if not path.is_absolute():
        path = workdir / path
    resolved = path.resolve(strict=True)
    root = workdir.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("Artwork 图片路径越过任务工作目录") from exc
    if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("Artwork 文件不是允许的图片类型")
    return resolved


def _artwork_asset_outputs(
    job_id: str,
    kind: str,
    paths: list[Path],
) -> list[DailyWriterArtworkAssetOut]:
    assets: list[DailyWriterArtworkAssetOut] = []
    for index, path in enumerate(sorted(paths), start=1):
        key = f"{kind}_{index:02d}"
        suffix = path.suffix.lower()
        assets.append(
            DailyWriterArtworkAssetOut(
                key=key,
                path=path.as_posix(),
                url=f"/api/daily-writer/jobs/{job_id}/artwork/{key}",
                kind="cover" if kind == "cover" else "inline",
                filename=path.name,
                content_type=IMAGE_CONTENT_TYPES.get(suffix, "application/octet-stream"),
            )
        )
    return assets
