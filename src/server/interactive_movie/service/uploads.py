# -*- coding: utf-8 -*-
"""Video upload services for interactive movies."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status

from src.server.config import global_config

from ..schemas import UploadedVideoOut

VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


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
        _configured_s3_client(config).put_object(
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


def _s3_client(config: dict[str, str]) -> Any:
    try:
        import boto3  # type: ignore[import-not-found, import-untyped]
    except ImportError as exc:
        raise RuntimeError("S3 上传需要安装 boto3") from exc

    return boto3.client(
        "s3",
        endpoint_url=config["endpoint_url"],
        region_name=config["region_name"] or None,
        aws_access_key_id=config["access_key_id"],
        aws_secret_access_key=config["secret_access_key"],
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


def _configured_s3_client(config: dict[str, str]) -> Any:
    if __package__ is None:
        return _s3_client(config)
    package = sys.modules.get(__package__)
    client_factory = getattr(package, "_s3_client", _s3_client)
    return client_factory(config)


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
        base_url = config["public_base_url"].rstrip("/")
        bucket = config["bucket"].strip("/")
        bucket_segment = quote(bucket, safe="")
        base_path_segments = [segment for segment in urlsplit(base_url).path.split("/") if segment]
        key_path = quote(full_key, safe="/")
        if base_path_segments and base_path_segments[-1] == bucket:
            return f"{base_url}/{key_path}"
        return f"{base_url}/{bucket_segment}/{key_path}"

    try:
        return _configured_s3_client(config).generate_presigned_url(
            "get_object",
            Params={"Bucket": config["bucket"], "Key": full_key},
            ExpiresIn=global_config.interactive_movie_s3_presign_expires_seconds,
        )
    except Exception:
        return None
