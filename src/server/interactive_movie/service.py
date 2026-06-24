# -*- coding: utf-8 -*-
"""Interactive movie editing services."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from src.server.config import global_config

from .schemas import UploadedVideoOut


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


def prompt_template() -> dict[str, Any]:
    """Return a structured prompt helper for future video generation."""
    return {
        "sections": [
            "主体：谁或什么是画面核心，保持描述具体。",
            "动作：主体正在做什么，单镜头只保留一组主要动作。",
            "场景：空间、时代、天气、道具、情绪氛围。",
            "镜头：景别、机位、运镜或镜头切换方式。",
            "时序：按秒描述关键动作变化，例如 [0-2s] / [2-5s]。",
            "风格：写实、动画、电影质感、色彩、光线、材质。",
            "约束：不要出现的内容、主体一致性、字幕/水印限制。",
        ],
        "example": (
            "主体：年轻女性林夏站在老式公寓走廊。\n"
            "动作：[0-2s] 她低头看见门口湿掉的信封；[2-5s] 她缓慢蹲下捡起信，神情迟疑。\n"
            "场景：雨夜，狭窄老公寓走廊，暖黄色灯光闪烁，地面潮湿。\n"
            "镜头：电影级中景缓慢推近，浅景深，轻微手持感。\n"
            "风格：悬疑短片，写实，低饱和，高对比，环境声紧张。\n"
            "约束：不出现文字水印，不切换主角，不夸张恐怖。"
        ),
    }


async def read_video_upload(file: UploadFile) -> bytes:
    content_type = file.content_type or ""
    extension = Path(file.filename or "").suffix.lower()
    if not content_type.startswith("video/") and extension not in VIDEO_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="只支持上传视频文件",
        )

    max_bytes = global_config.interactive_movie_max_video_upload_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"视频不能超过 {global_config.interactive_movie_max_video_upload_mb}MB",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    return content


def upload_video(file: UploadFile, content: bytes) -> UploadedVideoOut:
    config = _s3_config()
    filename = _safe_filename(file.filename or "scene-video.mp4")
    content_type = file.content_type or "application/octet-stream"
    object_key = _object_key(filename)
    full_key = _full_key(config["prefix"], object_key)

    try:
        _s3_client(config).put_object(
            Bucket=config["bucket"],
            Key=full_key,
            Body=content,
            ContentType=content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"S3 上传失败：{exc}") from exc

    return UploadedVideoOut(
        url=_access_url(config, full_key),
        storage_uri=f"s3://{config['bucket']}/{full_key}",
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size=len(content),
    )


def _s3_config() -> dict[str, str]:
    config = {
        "endpoint_url": global_config.interactive_movie_s3_endpoint_url.strip(),
        "region_name": global_config.interactive_movie_s3_region_name.strip(),
        "bucket": global_config.interactive_movie_s3_bucket.strip(),
        "access_key_id": global_config.interactive_movie_s3_access_key_id.strip(),
        "secret_access_key": global_config.interactive_movie_s3_secret_access_key.strip(),
        "prefix": global_config.interactive_movie_s3_prefix.strip(),
        "public_base_url": global_config.interactive_movie_s3_public_base_url.strip(),
    }
    missing = [
        name
        for name in ("endpoint_url", "bucket", "access_key_id", "secret_access_key")
        if not config[name]
    ]
    if missing:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"互动电影 S3 配置缺失：{', '.join(missing)}",
        )
    return config


def _s3_client(config: dict[str, str]) -> Any:
    try:
        import boto3  # type: ignore[import-untyped]
    except ImportError as exc:
        raise RuntimeError("S3 上传需要安装 boto3") from exc

    return boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"] or None,
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
    )


def _safe_filename(filename: str) -> str:
    name = Path(filename).name.strip().replace("\\", "_").replace("/", "_")
    return name[:160] or "scene-video.mp4"


def _object_key(filename: str) -> str:
    now = datetime.now(timezone.utc)
    extension = Path(filename).suffix.lower()
    if extension not in VIDEO_EXTENSIONS:
        extension = ".mp4"
    return f"videos/{now:%Y/%m/%d}/{uuid4().hex}{extension}"


def _full_key(prefix: str, object_key: str) -> str:
    normalized_prefix = prefix.strip("/")
    return f"{normalized_prefix}/{object_key}" if normalized_prefix else object_key


def _access_url(config: dict[str, str], full_key: str) -> str | None:
    if config["public_base_url"]:
        return f"{config['public_base_url'].rstrip('/')}/{quote(full_key, safe='/')}"

    try:
        return _s3_client(config).generate_presigned_url(
            "get_object",
            Params={"Bucket": config["bucket"], "Key": full_key},
            ExpiresIn=global_config.interactive_movie_s3_presign_expires_seconds,
        )
    except Exception:
        return None
