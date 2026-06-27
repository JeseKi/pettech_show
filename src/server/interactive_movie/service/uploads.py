# -*- coding: utf-8 -*-
"""Asset upload services for interactive movies."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status
from fastapi.responses import FileResponse

from src.server.config import global_config

from ..schemas import UploadedAssetOut, UploadedVideoOut

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}


async def read_video_upload(file: UploadFile) -> bytes:
    return await _read_asset_upload(
        file,
        expected_type="video",
        allowed_extensions=VIDEO_EXTENSIONS,
        max_mb=global_config.interactive_movie_max_video_upload_mb,
        invalid_message="只支持上传视频文件",
    )


async def read_image_upload(file: UploadFile) -> bytes:
    return await _read_asset_upload(
        file,
        expected_type="image",
        allowed_extensions=IMAGE_EXTENSIONS,
        max_mb=global_config.interactive_movie_max_image_upload_mb,
        invalid_message="只支持上传图片文件",
    )


def upload_video(file: UploadFile, content: bytes) -> UploadedVideoOut:
    uploaded = upload_asset(file, content, "video")
    return UploadedVideoOut(**uploaded.model_dump())


def upload_image(file: UploadFile, content: bytes) -> UploadedAssetOut:
    return upload_asset(file, content, "image")


def upload_asset(file: UploadFile, content: bytes, asset_type: str) -> UploadedAssetOut:
    if global_config.interactive_movie_storage_backend.strip().lower() == "s3":
        return _upload_s3_asset(file, content, asset_type)
    return _upload_local_asset(file, content, asset_type)


def local_asset_response(object_key: str) -> FileResponse:
    safe_key = object_key.strip().lstrip("/")
    if not safe_key or ".." in Path(safe_key).parts:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")

    root = _local_asset_root().resolve()
    path = (root / safe_key).resolve()
    if root not in path.parents or not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="资产不存在")
    return FileResponse(path)


async def _read_asset_upload(
    file: UploadFile,
    *,
    expected_type: str,
    allowed_extensions: set[str],
    max_mb: int,
    invalid_message: str,
) -> bytes:
    content_type = file.content_type or ""
    extension = Path(file.filename or "").suffix.lower()
    if not content_type.startswith(f"{expected_type}/") and extension not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=invalid_message,
        )

    max_bytes = max_mb * 1024 * 1024
    content = await file.read(max_bytes + 1)
    if len(content) > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"文件不能超过 {max_mb}MB",
        )
    if not content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="上传文件为空")
    return content


def _upload_s3_asset(file: UploadFile, content: bytes, asset_type: str) -> UploadedAssetOut:
    config = _s3_config()
    filename = _safe_filename(file.filename or _default_filename(asset_type))
    content_type = file.content_type or "application/octet-stream"
    object_key = _object_key(filename, asset_type)
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

    return UploadedAssetOut(
        url=_access_url(config, full_key),
        storage_uri=f"s3://{config['bucket']}/{full_key}",
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        size=len(content),
    )


def _upload_local_asset(file: UploadFile, content: bytes, asset_type: str) -> UploadedAssetOut:
    filename = _safe_filename(file.filename or _default_filename(asset_type))
    content_type = file.content_type or "application/octet-stream"
    object_key = _object_key(filename, asset_type)
    target = _local_asset_root() / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    base_url = global_config.interactive_movie_local_asset_base_url.strip().rstrip("/")
    return UploadedAssetOut(
        url=f"{base_url}/{quote(object_key, safe='/')}" if base_url else None,
        storage_uri=f"local://{object_key}",
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
    return name[:160] or "asset.bin"


def _object_key(filename: str, asset_type: str) -> str:
    now = datetime.now(timezone.utc)
    extension = Path(filename).suffix.lower()
    if asset_type == "image":
        folder = "images"
        if extension not in IMAGE_EXTENSIONS:
            extension = ".jpg"
    else:
        folder = "videos"
        if extension not in VIDEO_EXTENSIONS:
            extension = ".mp4"
    return f"{folder}/{now:%Y/%m/%d}/{uuid4().hex}{extension}"


def _default_filename(asset_type: str) -> str:
    return "image.jpg" if asset_type == "image" else "scene-video.mp4"


def _local_asset_root() -> Path:
    path = global_config.interactive_movie_local_asset_dir
    if path.is_absolute():
        return path
    return global_config.project_root / path


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
