# -*- coding: utf-8 -*-
"""Convert generated local artifacts into upload sources."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.daily_writer.dao import DailyWriterJobDAO
from src.server.daily_writer.parser import parse_daily_writer_result
from src.server.social_card_videos.dao import SocialCardVideoJobDAO, parse_json_dict
from src.server.social_card_videos.parser import parse_social_card_video_result
from src.server.social_cards.dao import SocialCardJobDAO
from src.server.social_cards.parser import parse_social_card_result

from .assets import asset_url


@dataclass(frozen=True)
class UploadSource:
    source_key: str
    source_label: str
    source_path: str | None
    title: str
    keyword: str
    markdown_content: str
    metadata: dict[str, Any]
    content_sha256: str


def upload_type_for_source(source_type: str) -> str:
    if source_type == "daily_writer":
        return "article"
    if source_type == "social_cards":
        return "image_text"
    if source_type == "social_card_videos":
        return "video"
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_type 无效")


def collect_upload_sources(
    db: Session,
    *,
    source_type: str,
    source_job_id: str,
) -> list[UploadSource]:
    if source_type == "daily_writer":
        return _daily_writer_sources(db, source_job_id)
    if source_type == "social_cards":
        return _social_card_sources(db, source_job_id)
    if source_type == "social_card_videos":
        return _social_card_video_sources(db, source_job_id)
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="source_type 无效")


def _daily_writer_sources(db: Session, job_id: str) -> list[UploadSource]:
    job = DailyWriterJobDAO(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="长文任务不存在")
    if job.status not in {"completed", "partial_failed"}:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="长文任务尚未完成")

    result = parse_daily_writer_result(
        job_id=job.id,
        source_seed_matrix_job_id=job.source_seed_matrix_job_id,
        source_aiwiki_job_id=job.source_aiwiki_job_id,
        seed_id=job.seed_id,
        workdir=Path(job.workdir),
        article_path=job.article_path,
        metadata_path=job.metadata_path,
    )
    assets = {
        asset.key: asset_url("daily-writer-artwork", job.id, asset.key)
        for asset in [*result.artwork.cover_images, *result.artwork.inline_images]
    }

    sources = [
        _source_from_markdown(
            source_key=f"daily_writer:{job.id}:main",
            source_label="main",
            source_path=result.article_path,
            markdown=_replace_daily_writer_assets(
                result.illustrated_markdown or result.markdown, assets
            ),
            metadata=result.metadata,
        )
    ]
    for index, variant in enumerate(result.variants, start=1):
        sources.append(
            _source_from_markdown(
                source_key=f"daily_writer:{job.id}:variant:{variant.directory or index}",
                source_label=variant.angle or f"variant:{index}",
                source_path=variant.markdown_path,
                markdown=_replace_daily_writer_assets(
                    variant.illustrated_markdown or variant.markdown, assets
                ),
                metadata=variant.metadata,
            )
        )
    return sources


def _social_card_sources(db: Session, job_id: str) -> list[UploadSource]:
    job = SocialCardJobDAO(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图文任务不存在")
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="图文任务尚未完成")

    result = parse_social_card_result(
        job_id=job.id,
        source_daily_writer_job_id=job.source_daily_writer_job_id,
        workdir=Path(job.workdir),
    )
    sources: list[UploadSource] = []
    for index, post in enumerate(result.posts, start=1):
        assets = {
            asset.key: asset_url("social-card-image", job.id, asset.key)
            for asset in post.images
        }
        metadata = {
            "output_id": f"{job.id}:{post.key}",
            "topic": post.title,
            "article": {
                "role": "image_text",
                "title": post.title,
                "summary": f"{post.title}，共 {len(post.images)} 张图片。",
                "tags": ["小红书图文"],
            },
            "social_card": {
                "post_key": post.key,
                "post_index": index,
                "main_path": post.main_path,
                "manifest_path": post.manifest_path,
                "image_count": len(post.images),
                "images": [
                    {
                        "key": asset.key,
                        "filename": asset.filename,
                        "content_type": asset.content_type,
                        "url": assets[asset.key],
                    }
                    for asset in post.images
                ],
                "summary": post.summary,
            },
        }
        sources.append(
            _source_from_markdown(
                source_key=f"social_cards:{job.id}:{post.key}",
                source_label=post.title or post.key,
                source_path=post.main_path,
                markdown=_replace_social_card_assets(post.markdown, assets),
                metadata=metadata,
                default_title=post.title,
            )
        )
    return sources


def _social_card_video_sources(db: Session, job_id: str) -> list[UploadSource]:
    job = SocialCardVideoJobDAO(db).get(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="视频任务不存在")
    if job.status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="视频任务尚未完成")

    result = parse_social_card_video_result(
        job_id=job.id,
        source_social_card_job_id=job.source_social_card_job_id,
        workdir=Path(job.workdir),
    )
    params = parse_json_dict(job.params_json)
    task_title = str(params.get("title") or "").strip()
    sources: list[UploadSource] = []
    for index, video in enumerate(result.videos, start=1):
        video_url = asset_url("social-card-video", job.id, video.key)
        title = _video_title(task_title, video.key, index, len(result.videos))
        metadata = {
            "output_id": f"{job.id}:{video.key}",
            "topic": title,
            "media_type": "video",
            "video_url": video_url,
            "article": {
                "role": "video",
                "title": title,
                "summary": f"{title}，轮播短视频。",
                "tags": ["小红书视频", "轮播视频"],
            },
            "social_card_video": {
                "video_key": video.key,
                "video_index": index,
                "source_social_card_job_id": job.source_social_card_job_id,
                "markdown_path": video.markdown_path,
                "filename": video.filename,
                "content_type": video.content_type,
                "url": video_url,
                "summary": video.summary,
            },
        }
        sources.append(
            _source_from_markdown(
                source_key=f"social_card_videos:{job.id}:{video.key}",
                source_label=f"video:{video.key}",
                source_path=video.markdown_path,
                markdown=_video_markdown(Path(job.workdir), video.markdown_path, video_url, title, video.key),
                metadata=metadata,
                default_title=title,
            )
        )
    return sources


def _source_from_markdown(
    *,
    source_key: str,
    source_label: str,
    source_path: str | None,
    markdown: str,
    metadata: dict[str, Any],
    default_title: str = "",
) -> UploadSource:
    cleaned_metadata = _copy_metadata(metadata)
    title = _title_from_metadata(cleaned_metadata) or _title_from_markdown(markdown) or default_title
    if not title:
        title = source_label
    keyword = _keyword_from_metadata(cleaned_metadata)
    return UploadSource(
        source_key=source_key,
        source_label=source_label,
        source_path=source_path,
        title=title[:200],
        keyword=keyword[:200],
        markdown_content=markdown,
        metadata=cleaned_metadata,
        content_sha256=hashlib.sha256(markdown.encode("utf-8")).hexdigest(),
    )


def _replace_daily_writer_assets(markdown: str, assets: dict[str, str]) -> str:
    output = markdown
    for key, url in assets.items():
        output = output.replace(f"daily-writer-artwork:{key}", url)
    return output


def _replace_social_card_assets(markdown: str, assets: dict[str, str]) -> str:
    output = markdown
    for key, url in assets.items():
        output = output.replace(f"social-card-image:{key}", url)
    return output


def _video_markdown(
    workdir: Path,
    markdown_path: str | None,
    video_url: str,
    title: str,
    video_key: str,
) -> str:
    if markdown_path:
        path = workdir / markdown_path
        if path.is_file() and path.stat().st_size > 0:
            text = path.read_text(encoding="utf-8").strip()
            output = text.replace("](video/slideshow.mp4)", f"]({video_url})")
            output = output.replace(f"(social-card-video:{video_key})", f"({video_url})")
            return output if output else f"# {title}\n\n[轮播视频]({video_url})\n"
    return f"# {title}\n\n[轮播视频]({video_url})\n"


def _video_title(base_title: str, video_key: str, index: int, total: int) -> str:
    if not base_title:
        base_title = "小红书轮播视频"
    if total <= 1:
        return base_title
    return f"{base_title} {index:02d}"


def _copy_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    try:
        return json.loads(json.dumps(metadata, ensure_ascii=False))
    except TypeError:
        return dict(metadata)


def _title_from_metadata(metadata: dict[str, Any]) -> str:
    article = metadata.get("article")
    if isinstance(article, dict) and article.get("title"):
        return str(article["title"]).strip()
    if metadata.get("title"):
        return str(metadata["title"]).strip()
    return ""


def _title_from_markdown(markdown: str) -> str:
    for line in markdown.splitlines():
        if line.startswith("# "):
            return line[2:].strip()
    return ""


def _keyword_from_metadata(metadata: dict[str, Any]) -> str:
    article = metadata.get("article")
    candidates: list[Any] = [
        metadata.get("keyword"),
        metadata.get("关键词"),
        article.get("keyword") if isinstance(article, dict) else None,
        article.get("关键词") if isinstance(article, dict) else None,
    ]
    if isinstance(article, dict):
        candidates.append(_keyword_from_intents(article.get("search_intents")))
        candidates.append(_keyword_from_intents(article.get("搜索入口")))
    candidates.append(_keyword_from_intents(metadata.get("search_intents")))
    candidates.append(_keyword_from_intents(metadata.get("搜索入口")))
    for candidate in candidates:
        keyword = str(candidate).strip() if candidate is not None else ""
        if keyword:
            return keyword
    return "无"


def _keyword_from_intents(raw: Any) -> str:
    if isinstance(raw, list):
        ordered = sorted(
            enumerate(raw),
            key=lambda pair: 0
            if isinstance(pair[1], dict)
            and str(pair[1].get("role") or "").lower() == "primary"
            else pair[0] + 1,
        )
        for _, item in ordered:
            if isinstance(item, str) and item.strip():
                return item.strip()
            if isinstance(item, dict):
                for key in ("keyword", "关键词", "query", "搜索词"):
                    value = item.get(key)
                    if value:
                        return str(value).strip()
    if isinstance(raw, dict):
        for key in ("keyword", "关键词", "query", "搜索词"):
            value = raw.get(key)
            if value:
                return str(value).strip()
    return ""
