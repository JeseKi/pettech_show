# -*- coding: utf-8 -*-
"""Image prompt reverse engineering service for interactive movies."""

from __future__ import annotations

import base64
import json
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import uuid4

import httpx
from fastapi import HTTPException, UploadFile, status
from loguru import logger
from sqlalchemy.orm import Session
from structured_llm import build_schema_spec, parse_structured_text
from structured_llm.errors import StructuredLLMError

from src.server.auth.models import User
from src.server.config import global_config

from ..models import InteractiveMoviePromptReverseRecord, utc_now
from ..schemas import ImagePromptReverseRecordOut, ImagePromptReverseResultOut
from .access import get_owned_project
from .uploads import (
    IMAGE_EXTENSIONS,
    _configured_s3_client,
    _full_key,
    _local_asset_root,
    _s3_config,
    _safe_filename,
)

PROMPT_REVERSE_IMAGE_PREFIX = "prompt-reverse/images"
PROMPT_TEMPLATE_FILENAME = "prompt_temp.md"


async def read_prompt_reverse_image_upload(file: UploadFile) -> bytes:
    content_type = file.content_type or ""
    extension = Path(file.filename or "").suffix.lower()
    if not content_type.startswith("image/") and extension not in IMAGE_EXTENSIONS:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="只支持上传图片文件")

    max_mb = global_config.interactive_movie_prompt_max_image_mb
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


async def create_prompt_reverse_record(
    db: Session,
    user: User,
    *,
    file: UploadFile,
    content: bytes,
    project_id: str | None = None,
) -> ImagePromptReverseRecordOut:
    if project_id:
        get_owned_project(db, user, project_id)

    config = _prompt_model_config()
    uploaded = _upload_prompt_reverse_image(file, content)
    try:
        result = await reverse_image_prompt(content, uploaded["content_type"], config=config)
    except Exception:
        _best_effort_delete_s3_object(uploaded["full_key"])
        raise

    record = InteractiveMoviePromptReverseRecord(
        id=uuid4().hex,
        owner_user_id=user.id,
        project_id=project_id,
        filename=uploaded["filename"],
        content_type=uploaded["content_type"],
        size=len(content),
        object_key=uploaded["object_key"],
        storage_uri=uploaded["storage_uri"],
        result_json=result.model_dump_json(),
        created_at=utc_now(),
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return prompt_reverse_record_out(record)


def list_prompt_reverse_history(db: Session, user: User) -> list[ImagePromptReverseRecordOut]:
    records = (
        db.query(InteractiveMoviePromptReverseRecord)
        .filter(InteractiveMoviePromptReverseRecord.owner_user_id == user.id)
        .order_by(InteractiveMoviePromptReverseRecord.created_at.desc())
        .all()
    )
    return [prompt_reverse_record_out(record) for record in records]


def delete_prompt_reverse_record(db: Session, user: User, record_id: str) -> None:
    record = (
        db.query(InteractiveMoviePromptReverseRecord)
        .filter(
            InteractiveMoviePromptReverseRecord.id == record_id,
            InteractiveMoviePromptReverseRecord.owner_user_id == user.id,
        )
        .first()
    )
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Prompt 反推记录不存在")

    _delete_prompt_reverse_image(record)
    db.delete(record)
    db.commit()


async def reverse_image_prompt(
    content: bytes,
    content_type: str,
    *,
    config: dict[str, Any] | None = None,
) -> ImagePromptReverseResultOut:
    resolved_config = config or _prompt_model_config()
    spec = build_schema_spec(ImagePromptReverseResultOut)
    prompt = _prompt_with_schema(spec.prompt_schema)
    payload = _completion_payload(
        prompt=prompt,
        image_data_url=_image_data_url(content, content_type),
        config=resolved_config,
    )
    raw_text = await _post_prompt_reverse_completion(payload, config=resolved_config)
    try:
        return parse_structured_text(raw_text, ImagePromptReverseResultOut)
    except StructuredLLMError as exc:
        logger.warning("Interactive movie prompt reverse parse failed: {}", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prompt 反推返回格式无效") from exc


def prompt_reverse_record_out(record: InteractiveMoviePromptReverseRecord) -> ImagePromptReverseRecordOut:
    return ImagePromptReverseRecordOut(
        id=record.id,
        project_id=record.project_id,
        filename=record.filename,
        content_type=record.content_type,
        size=record.size,
        object_key=record.object_key,
        storage_uri=record.storage_uri,
        image_url=_prompt_reverse_image_url(record.object_key, record.storage_uri),
        result=ImagePromptReverseResultOut.model_validate(json.loads(record.result_json)),
        created_at=record.created_at.isoformat(),
    )


def _prompt_model_config() -> dict[str, Any]:
    api_key = global_config.interactive_movie_prompt_api_key.strip()
    model = global_config.interactive_movie_prompt_model.strip()
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prompt 反推 API 未配置：请设置 INTERACTIVE_MOVIE_PROMPT_API_KEY",
        )
    if not model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Prompt 反推 API 未配置：请设置 INTERACTIVE_MOVIE_PROMPT_MODEL",
        )
    return {
        "api_key": api_key,
        "base_url": global_config.interactive_movie_prompt_base_url.strip().rstrip("/"),
        "model": model,
        "timeout": global_config.interactive_movie_prompt_timeout_seconds,
        "temperature": global_config.interactive_movie_prompt_temperature,
        "max_tokens": global_config.interactive_movie_prompt_max_tokens,
    }


def _upload_prompt_reverse_image(file: UploadFile, content: bytes) -> dict[str, str]:
    filename = _safe_filename(file.filename or "prompt-image.jpg")
    content_type = file.content_type or "application/octet-stream"
    extension = Path(filename).suffix.lower()
    if extension not in IMAGE_EXTENSIONS:
        extension = ".jpg"
    object_key = f"{PROMPT_REVERSE_IMAGE_PREFIX}/{utc_now():%Y/%m/%d}/{uuid4().hex}{extension}"

    if global_config.interactive_movie_storage_backend.strip().lower() != "s3":
        return _upload_local_prompt_reverse_image(
            object_key=object_key,
            filename=filename,
            content_type=content_type,
            content=content,
        )

    return _upload_s3_prompt_reverse_image(
        object_key=object_key,
        filename=filename,
        content_type=content_type,
        content=content,
    )


def _upload_local_prompt_reverse_image(
    *,
    object_key: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> dict[str, str]:
    target = _local_asset_root() / object_key
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return {
        "filename": filename,
        "content_type": content_type,
        "object_key": object_key,
        "full_key": object_key,
        "storage_uri": f"local://{object_key}",
    }


def _upload_s3_prompt_reverse_image(
    *,
    object_key: str,
    filename: str,
    content_type: str,
    content: bytes,
) -> dict[str, str]:
    s3_config = _s3_config()
    full_key = _full_key(s3_config["prefix"], object_key)

    try:
        _configured_s3_client(s3_config).put_object(
            Bucket=s3_config["bucket"],
            Key=full_key,
            Body=content,
            ContentType=content_type,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"S3 上传失败：{exc}") from exc

    return {
        "filename": filename,
        "content_type": content_type,
        "object_key": object_key,
        "full_key": full_key,
        "storage_uri": f"s3://{s3_config['bucket']}/{full_key}",
    }


def _delete_prompt_reverse_image(record: InteractiveMoviePromptReverseRecord) -> None:
    if record.storage_uri.startswith("s3://"):
        _delete_s3_object(_full_key(_s3_config()["prefix"], record.object_key))
        return
    if record.storage_uri.startswith("local://"):
        _delete_local_prompt_reverse_image(record.object_key)


def _delete_local_prompt_reverse_image(object_key: str) -> None:
    safe_key = object_key.strip().lstrip("/")
    if not safe_key or ".." in Path(safe_key).parts:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地图片路径无效")
    root = _local_asset_root().resolve()
    path = (root / safe_key).resolve()
    if root not in path.parents and path != root:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="本地图片路径无效")
    try:
        if path.is_file():
            path.unlink()
    except OSError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"本地图片删除失败：{exc}") from exc


def _delete_s3_object(full_key: str) -> None:
    s3_config = _s3_config()
    try:
        _configured_s3_client(s3_config).delete_object(Bucket=s3_config["bucket"], Key=full_key)
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"S3 删除失败：{exc}") from exc


def _best_effort_delete_s3_object(full_key: str) -> None:
    try:
        _delete_s3_object(full_key)
    except Exception as exc:
        logger.warning("Prompt reverse orphan S3 cleanup failed for {}: {}", full_key, exc)


def _prompt_reverse_image_url(object_key: str, storage_uri: str) -> str | None:
    try:
        if storage_uri.startswith("local://"):
            base_url = global_config.interactive_movie_local_asset_base_url.strip().rstrip("/")
            return f"{base_url}/{quote(object_key, safe='/')}" if base_url else None
        s3_config = _s3_config()
        full_key = _full_key(s3_config["prefix"], object_key)
        if s3_config["public_base_url"]:
            base_url = s3_config["public_base_url"].rstrip("/")
            bucket = s3_config["bucket"].strip("/")
            bucket_segment = quote(bucket, safe="")
            base_path_segments = [segment for segment in urlsplit(base_url).path.split("/") if segment]
            key_path = quote(full_key, safe="/")
            if base_path_segments and base_path_segments[-1] == bucket:
                return f"{base_url}/{key_path}"
            return f"{base_url}/{bucket_segment}/{key_path}"
        return _configured_s3_client(s3_config).generate_presigned_url(
            "get_object",
            Params={"Bucket": s3_config["bucket"], "Key": full_key},
            ExpiresIn=global_config.interactive_movie_s3_presign_expires_seconds,
        )
    except Exception:
        return None


def _prompt_with_schema(prompt_schema: str) -> str:
    return (
        f"{_prompt_template_text().rstrip()}\n\n"
        "请把分析结果输出为一个 JSON 对象，字段语义必须匹配下面的 output format。\n"
        "不要输出 Markdown、代码块、解释性前后缀或额外字段。\n\n"
        "Return a JSON value that matches this output format:\n"
        f"{prompt_schema}\n\n"
        "Return only the JSON value."
    )


def _prompt_template_text() -> str:
    path = global_config.project_root / PROMPT_TEMPLATE_FILENAME
    try:
        text = path.read_text(encoding="utf-8").strip()
    except OSError:
        text = ""
    if text:
        return text
    return "你是一名专业的 AI 图像提示词反推专家。请分析图片并反推出可用于 AI 生成的提示词。"


def _image_data_url(content: bytes, content_type: str) -> str:
    safe_content_type = content_type if content_type.startswith("image/") else "image/jpeg"
    encoded = base64.b64encode(content).decode("ascii")
    return f"data:{safe_content_type};base64,{encoded}"


def _completion_payload(
    *,
    prompt: str,
    image_data_url: str,
    config: dict[str, Any],
) -> dict[str, Any]:
    return {
        "model": config["model"],
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_data_url}},
                ],
            }
        ],
        "temperature": config["temperature"],
        "max_tokens": config["max_tokens"],
    }


async def _post_prompt_reverse_completion(payload: dict[str, Any], *, config: dict[str, Any]) -> str:
    try:
        async with httpx.AsyncClient(timeout=config["timeout"]) as client:
            response = await client.post(
                f"{config['base_url']}/chat/completions",
                headers={
                    "Authorization": f"Bearer {config['api_key']}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Prompt 反推 API 请求超时") from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Prompt 反推 API 上游错误：{_upstream_error_detail(exc.response)}",
        ) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prompt 反推 API 请求失败") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prompt 反推 API 返回了无效 JSON") from exc

    content = _completion_content(data)
    if not content:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Prompt 反推 API 返回缺少内容")
    return content


def _completion_content(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""
    first = choices[0]
    if not isinstance(first, dict):
        return ""
    message = first.get("message")
    if not isinstance(message, dict):
        return ""
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and isinstance(item.get("text"), str):
                parts.append(item["text"])
        return "".join(parts)
    return ""


def _upstream_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return response.text[:500] or f"HTTP {response.status_code}"
    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict) and isinstance(error.get("message"), str):
            return error["message"]
        detail = data.get("detail")
        if isinstance(detail, str):
            return detail
    return f"HTTP {response.status_code}"
