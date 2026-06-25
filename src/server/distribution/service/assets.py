# -*- coding: utf-8 -*-
"""Signed asset URL helpers for generated distribution uploads."""

from __future__ import annotations

import hmac
from hashlib import sha256
from pathlib import Path
from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.config import global_config
from src.server.daily_writer.dao import DailyWriterJobDAO
from src.server.daily_writer.parser import resolve_artwork_asset_path, resolve_result_paths
from src.server.social_cards.dao import SocialCardJobDAO
from src.server.social_cards.parser import resolve_social_card_asset_path

AssetType = Literal["daily-writer-artwork", "social-card-image"]


def sign_asset(asset_type: str, job_id: str, asset_key: str) -> str:
    message = f"{asset_type}\n{job_id}\n{asset_key}".encode("utf-8")
    secret = global_config.app_secret_key.encode("utf-8")
    return hmac.new(secret, message, sha256).hexdigest()


def asset_url(asset_type: AssetType, job_id: str, asset_key: str) -> str:
    base_url = (
        global_config.info_distribution_public_asset_base_url.strip().rstrip("/")
        or global_config.app_domain.strip().rstrip("/")
    )
    if not base_url:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="含图片内容上传前，请配置 INFO_DISTRIBUTION_PUBLIC_ASSET_BASE_URL 或 APP_DOMAIN",
        )
    signature = sign_asset(asset_type, job_id, asset_key)
    return f"{base_url}/api/distribution/assets/{asset_type}/{job_id}/{asset_key}?sig={signature}"


def resolve_signed_asset(
    db: Session,
    *,
    asset_type: str,
    job_id: str,
    asset_key: str,
    signature: str,
) -> tuple[Path, str]:
    expected = sign_asset(asset_type, job_id, asset_key)
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="图片签名无效")

    if asset_type == "daily-writer-artwork":
        job = DailyWriterJobDAO(db).get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
        _, metadata_path = resolve_result_paths(
            Path(job.workdir),
            article_path=job.article_path,
            metadata_path=job.metadata_path,
        )
        return resolve_artwork_asset_path(
            job_id=job.id,
            workdir=Path(job.workdir),
            article_dir=metadata_path.parent,
            asset_key=asset_key,
        )

    if asset_type == "social-card-image":
        job = SocialCardJobDAO(db).get(job_id)
        if job is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")
        return resolve_social_card_asset_path(
            job_id=job.id,
            source_daily_writer_job_id=job.source_daily_writer_job_id,
            workdir=Path(job.workdir),
            asset_key=asset_key,
        )

    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="图片不存在")

