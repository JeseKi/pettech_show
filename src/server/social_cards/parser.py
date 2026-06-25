# -*- coding: utf-8 -*-
"""Parse and validate generated social card artifacts."""

from __future__ import annotations

import json
from pathlib import Path

from .schemas import SocialCardAssetOut, SocialCardPostOut, SocialCardResultOut

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}
IMAGE_CONTENT_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}


def parse_social_card_result(
    *,
    job_id: str,
    source_daily_writer_job_id: str,
    workdir: Path,
) -> SocialCardResultOut:
    deck_dirs = _deck_directories(workdir)
    if not deck_dirs:
        raise FileNotFoundError("小红书图文卡输出目录尚未生成")

    posts = [
        _parse_deck(
            job_id=job_id,
            workdir=workdir,
            xhs_dir=xhs_dir,
            post_index=index,
            multiple=len(deck_dirs) > 1,
        )
        for index, xhs_dir in enumerate(deck_dirs, start=1)
    ]
    images = [image for post in posts for image in post.images]
    first_post = posts[0]
    markdown = _combined_markdown(posts)
    main_path = first_post.main_path
    manifest_path = first_post.manifest_path
    index_path = first_post.index_path
    plan_path = first_post.plan_path

    summary = {
        "image_count": len(images),
        "post_count": len(posts),
        "main_path": main_path,
        "manifest_path": manifest_path,
        "index_path": index_path,
        "plan_path": plan_path,
        "posts": [post.summary for post in posts],
    }
    return SocialCardResultOut(
        job_id=job_id,
        source_daily_writer_job_id=source_daily_writer_job_id,
        images=images,
        posts=posts,
        markdown=markdown,
        main_path=main_path,
        manifest_path=manifest_path,
        index_path=index_path,
        plan_path=plan_path,
        summary=summary,
    )


def resolve_social_card_asset_path(
    *,
    job_id: str,
    source_daily_writer_job_id: str,
    workdir: Path,
    asset_key: str,
) -> tuple[Path, str]:
    result = parse_social_card_result(
        job_id=job_id,
        source_daily_writer_job_id=source_daily_writer_job_id,
        workdir=workdir,
    )
    for asset in result.images:
        if asset.key == asset_key:
            return Path(asset.path), asset.content_type
    raise FileNotFoundError("图文卡图片不存在")


def _deck_directories(workdir: Path) -> list[Path]:
    deck_dirs: list[Path] = []
    main_dir = workdir / "xhs_guizang"
    if main_dir.is_dir():
        deck_dirs.append(main_dir)

    variants_root = workdir / "xhs_guizang_variants"
    if variants_root.is_dir():
        deck_dirs.extend(
            path for path in sorted(variants_root.glob("variant-*")) if path.is_dir()
        )

    deck_dirs.extend(
        path for path in sorted(workdir.glob("xhs_guizang_variant_*")) if path.is_dir()
    )
    return _unique_sorted_paths(deck_dirs)


def _parse_deck(
    *,
    job_id: str,
    workdir: Path,
    xhs_dir: Path,
    post_index: int,
    multiple: bool,
) -> SocialCardPostOut:
    key = f"post_{post_index:02d}"
    title = "主图文" if post_index == 1 else f"图文变体 {post_index - 1:02d}"
    image_paths = _image_candidates(xhs_dir, workdir)
    image_key_prefix = "" if not multiple and post_index == 1 else f"{key}_"
    images = _asset_outputs(job_id, image_paths, key_prefix=image_key_prefix)
    main_path = xhs_dir / "main.md"
    manifest_path = xhs_dir / "manifest.json"
    index_path = xhs_dir / "index.html"
    plan_path = _first_existing_file(xhs_dir, ["plan.md", "prompts.md"])
    markdown = ""
    if main_path.is_file():
        markdown = _markdown_with_internal_refs(main_path.read_text(encoding="utf-8"), images)
    elif images:
        markdown = _build_markdown(images)
    main_path_text = main_path.relative_to(workdir).as_posix() if main_path.is_file() else None
    manifest_path_text = (
        manifest_path.relative_to(workdir).as_posix()
        if manifest_path.is_file()
        else None
    )
    index_path_text = index_path.relative_to(workdir).as_posix() if index_path.is_file() else None
    plan_path_text = plan_path.relative_to(workdir).as_posix() if plan_path else None
    summary = {
        "key": key,
        "title": title,
        "image_count": len(images),
        "main_path": main_path_text,
        "manifest_path": manifest_path_text,
        "index_path": index_path_text,
        "plan_path": plan_path_text,
    }
    return SocialCardPostOut(
        key=key,
        title=title,
        images=images,
        markdown=markdown,
        main_path=main_path_text,
        manifest_path=manifest_path_text,
        index_path=index_path_text,
        plan_path=plan_path_text,
        summary=summary,
    )


def _image_candidates(xhs_dir: Path, workdir: Path) -> list[Path]:
    candidates: list[Path] = []
    for base in (xhs_dir / "output", xhs_dir):
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*")):
            if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
                candidates.append(_trusted_image_path(path, workdir))

    if candidates:
        return _unique_sorted_paths(candidates)

    manifest_path = xhs_dir / "manifest.json"
    if not manifest_path.is_file():
        return []
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return []
    uploaded_images = manifest.get("uploaded_images")
    if not isinstance(uploaded_images, list):
        return []

    manifest_candidates: list[Path] = []
    for item in uploaded_images:
        if not isinstance(item, dict):
            continue
        file_value = item.get("file")
        if not isinstance(file_value, str) or not file_value.strip():
            continue
        path = Path(file_value)
        if not path.is_absolute():
            path = xhs_dir / path
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS:
            manifest_candidates.append(_trusted_image_path(path, workdir))
    return _unique_sorted_paths(manifest_candidates)


def _trusted_image_path(path: Path, workdir: Path) -> Path:
    if not path.is_absolute():
        path = workdir / path
    resolved = path.resolve(strict=True)
    root = workdir.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("图文卡图片路径越过任务工作目录") from exc
    if resolved.suffix.lower() not in IMAGE_EXTENSIONS:
        raise ValueError("图文卡文件不是允许的图片类型")
    return resolved


def _unique_sorted_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in sorted(paths):
        if path in seen:
            continue
        seen.add(path)
        unique.append(path)
    return unique


def _asset_outputs(
    job_id: str,
    paths: list[Path],
    *,
    key_prefix: str = "",
) -> list[SocialCardAssetOut]:
    assets: list[SocialCardAssetOut] = []
    for index, path in enumerate(paths, start=1):
        key = f"{key_prefix}card_{index:02d}"
        suffix = path.suffix.lower()
        assets.append(
            SocialCardAssetOut(
                key=key,
                path=path.as_posix(),
                url=f"/api/social-cards/jobs/{job_id}/images/{key}",
                filename=path.name,
                content_type=IMAGE_CONTENT_TYPES.get(suffix, "application/octet-stream"),
            )
        )
    return assets


def _markdown_with_internal_refs(
    markdown: str,
    images: list[SocialCardAssetOut],
) -> str:
    output = markdown
    for image in images:
        path = Path(image.path)
        replacements = {
            path.as_posix(),
            path.name,
            f"output/{path.name}",
            f"./output/{path.name}",
        }
        for value in sorted(replacements, key=len, reverse=True):
            output = output.replace(f"]({value})", f"](social-card-image:{image.key})")
            output = output.replace(f"](<{value}>)", f"](social-card-image:{image.key})")
    return output


def _build_markdown(images: list[SocialCardAssetOut]) -> str:
    lines = ["# 小红书图文卡", ""]
    for image in images:
        lines.append(f"![{image.filename}](social-card-image:{image.key})")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


def _combined_markdown(posts: list[SocialCardPostOut]) -> str:
    if not posts:
        return ""
    if len(posts) == 1:
        return posts[0].markdown
    chunks: list[str] = []
    for index, post in enumerate(posts, start=1):
        chunks.append(f"## 第 {index} 篇：{post.title}")
        if post.markdown:
            chunks.append(post.markdown.strip())
    return "\n\n".join(chunks).strip() + "\n"


def _first_existing_file(base: Path, filenames: list[str]) -> Path | None:
    for filename in filenames:
        path = base / filename
        if path.is_file():
            return path
    return None
