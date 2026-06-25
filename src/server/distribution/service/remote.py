# -*- coding: utf-8 -*-
"""HTTP client for the remote Info Distribution API."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status

from src.server.config import global_config

V2_ACCOUNTS_PATH = "/api/v2/article-distribution/accounts"
V2_PROJECT_THEMES_PATH = "/api/v2/article-distribution/project-themes"
V3_ARTICLES_PATH = "/api/v3/article-distribution/articles"


def remote_base_url() -> str:
    value = global_config.info_distribution_base_url.strip().rstrip("/")
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请配置 INFO_DISTRIBUTION_BASE_URL",
        )
    if not value.startswith(("http://", "https://")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="INFO_DISTRIBUTION_BASE_URL 必须以 http:// 或 https:// 开头",
        )
    return value


def remote_api_key() -> str:
    value = global_config.info_distribution_api_key.strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="请配置 INFO_DISTRIBUTION_API_KEY",
        )
    return value


async def fetch_remote_directory() -> tuple[list[dict[str, Any]], dict[str, Any]]:
    base_url = remote_base_url()
    headers = {"X-API-Key": remote_api_key()}
    async with httpx.AsyncClient(
        timeout=global_config.info_distribution_timeout_seconds,
        verify=global_config.info_distribution_verify_ssl,
    ) as client:
        accounts_response = await client.get(f"{base_url}{V2_ACCOUNTS_PATH}", headers=headers)
        _raise_remote_error(accounts_response)
        project_theme_response = await client.get(
            f"{base_url}{V2_PROJECT_THEMES_PATH}", headers=headers
        )
        _raise_remote_error(project_theme_response)
    return accounts_response.json(), project_theme_response.json()


async def upload_batches(plan: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = remote_base_url()
    headers = {"X-API-Key": remote_api_key(), "content-type": "application/json"}
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(
        timeout=global_config.info_distribution_timeout_seconds,
        verify=global_config.info_distribution_verify_ssl,
    ) as client:
        for batch in plan["batches"]:
            response = await client.post(
                f"{base_url}{V3_ARTICLES_PATH}",
                headers=headers,
                json=batch["payload"],
            )
            _raise_remote_error(response)
            response_json = response.json()
            results.append(
                {
                    "account": batch["account"],
                    "created_count": len(response_json) if isinstance(response_json, list) else 0,
                    "response": response_json,
                }
            )
    return results


def _raise_remote_error(response: httpx.Response) -> None:
    try:
        response.raise_for_status()
    except httpx.HTTPStatusError as exc:
        detail = exc.response.text
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"分发平台请求失败：{detail}",
        ) from exc

