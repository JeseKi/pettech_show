# -*- coding: utf-8 -*-
"""Parse and validate generated social card video artifacts."""

from __future__ import annotations

from pathlib import Path

from .schemas import SocialCardVideoAssetOut, SocialCardVideoResultOut

VIDEO_CONTENT_TYPES = {".mp4": "video/mp4", ".mov": "video/quicktime", ".webm": "video/webm"}


def parse_social_card_video_result(
    *,
    job_id: str,
    source_social_card_job_id: str,
    workdir: Path,
) -> SocialCardVideoResultOut:
    video_paths = _video_candidates(workdir)
    if not video_paths:
        raise FileNotFoundError("轮播视频尚未生成")
    videos = [_asset_output(job_id, workdir, path, index) for index, path in enumerate(video_paths, start=1)]
    markdown = _combined_markdown(workdir, videos)
    summary = {
        "video_count": len(videos),
        "videos": [video.summary for video in videos],
    }
    return SocialCardVideoResultOut(
        job_id=job_id,
        source_social_card_job_id=source_social_card_job_id,
        videos=videos,
        markdown=markdown,
        summary=summary,
    )


def resolve_social_card_video_asset_path(
    *,
    job_id: str,
    source_social_card_job_id: str,
    workdir: Path,
    asset_key: str,
) -> tuple[Path, str]:
    result = parse_social_card_video_result(
        job_id=job_id,
        source_social_card_job_id=source_social_card_job_id,
        workdir=workdir,
    )
    for asset in result.videos:
        if asset.key == asset_key:
            return Path(asset.path), asset.content_type
    raise FileNotFoundError("轮播视频不存在")


def _video_candidates(workdir: Path) -> list[Path]:
    candidates = sorted(path for path in (workdir / "source").rglob("video/slideshow.mp4") if path.is_file())
    return [_trusted_video_path(path, workdir) for path in candidates]


def _trusted_video_path(path: Path, workdir: Path) -> Path:
    resolved = path.resolve(strict=True)
    root = workdir.resolve(strict=True)
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ValueError("视频路径越过任务工作目录") from exc
    if resolved.suffix.lower() not in VIDEO_CONTENT_TYPES:
        raise ValueError("视频文件不是允许的视频类型")
    return resolved


def _asset_output(job_id: str, workdir: Path, path: Path, index: int) -> SocialCardVideoAssetOut:
    key = _asset_key(workdir, path, index)
    markdown_path = path.parent.parent / "video.md"
    relative_path = path.relative_to(workdir).as_posix()
    summary = {
        "key": key,
        "path": relative_path,
        "markdown_path": markdown_path.relative_to(workdir).as_posix() if markdown_path.is_file() else None,
    }
    return SocialCardVideoAssetOut(
        key=key,
        path=path.as_posix(),
        url=f"/api/social-card-videos/jobs/{job_id}/videos/{key}",
        filename=path.name if index == 1 else f"{key}.mp4",
        content_type=VIDEO_CONTENT_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        markdown_path=summary["markdown_path"],
        summary=summary,
    )


def _asset_key(workdir: Path, path: Path, index: int) -> str:
    rel = path.relative_to(workdir).as_posix()
    if rel.startswith("source/xhs_guizang/video/"):
        return "post_01"
    marker = "source/xhs_guizang_variants/variant-"
    if rel.startswith(marker):
        suffix = rel[len(marker) :].split("/", 1)[0]
        try:
            return f"post_{int(suffix) + 1:02d}"
        except ValueError:
            pass
    return f"video_{index:02d}"


def _combined_markdown(workdir: Path, videos: list[SocialCardVideoAssetOut]) -> str:
    chunks: list[str] = []
    for video in videos:
        label = video.key.replace("_", " ")
        chunks.append(f"## {label}")
        if video.markdown_path:
            text = (workdir / video.markdown_path).read_text(encoding="utf-8").strip()
            chunks.append(text.replace("](video/slideshow.mp4)", f"](social-card-video:{video.key})"))
        else:
            chunks.append(f"[轮播视频](social-card-video:{video.key})")
    return "\n\n".join(chunks).strip() + "\n"

