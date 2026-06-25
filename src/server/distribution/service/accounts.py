# -*- coding: utf-8 -*-
"""Remote directory filtering helpers."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status


@dataclass(frozen=True)
class AccountRef:
    id: int
    user_id: int | None
    user_name: str
    platform: str
    account_name: str
    publication_type: str
    theme_id: int | None
    project_ids: tuple[int, ...]
    raw: dict[str, Any]


def validate_project_theme(
    project_theme_directory: dict[str, Any], project_id: int, theme_id: int
) -> tuple[dict[str, Any], dict[str, Any]]:
    projects = project_theme_directory.get("projects") or []
    themes = project_theme_directory.get("themes") or []
    project = next((item for item in projects if int(item.get("id") or 0) == project_id), None)
    theme = next((item for item in themes if int(item.get("id") or 0) == theme_id), None)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"项目不存在或 API Key 无权访问：{project_id}",
        )
    if not theme:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"主题不存在或 API Key 无权访问：{theme_id}",
        )

    theme_ids = project.get("theme_ids") or []
    if not theme_ids and isinstance(project.get("themes"), list):
        theme_ids = [
            item.get("id")
            for item in project["themes"]
            if isinstance(item, dict) and item.get("id") is not None
        ]
    if theme_id not in {int(item) for item in theme_ids if item is not None}:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"主题 {theme_id} 不属于项目 {project_id}",
        )
    return project, theme


def filter_accounts(
    account_directory: list[dict[str, Any]],
    *,
    upload_type: str,
    project_id: int,
    theme_id: int,
    platforms: list[str] | None = None,
    account_query: str | None = None,
    user_query: str | None = None,
    account_ids: list[int] | None = None,
) -> list[AccountRef]:
    platform_set = {
        normalize_text(platform) for platform in platforms or [] if normalize_text(platform)
    }
    account_query_normalized = normalize_text(account_query)
    user_query_normalized = normalize_text(user_query)
    account_id_set = set(account_ids or [])
    return [
        account
        for account in flatten_accounts(account_directory)
        if account.publication_type == upload_type
        and account.raw.get("is_active") is True
        and account.theme_id == theme_id
        and project_id in account.project_ids
        and (not platform_set or normalize_text(account.platform) in platform_set)
        and (not account_query_normalized or account_query_normalized in normalize_text(account.account_name))
        and (not user_query_normalized or user_query_normalized in normalize_text(account.user_name))
        and (not account_id_set or account.id in account_id_set)
    ]


def flatten_accounts(account_directory: list[dict[str, Any]]) -> list[AccountRef]:
    accounts: list[AccountRef] = []
    for user in account_directory:
        user_id = int(user["id"]) if user.get("id") is not None else None
        user_name = str(user.get("name") or "")
        for account in user.get("accounts") or []:
            project_ids = account.get("project_ids") or []
            if not project_ids and isinstance(account.get("projects"), list):
                project_ids = [
                    project.get("id")
                    for project in account["projects"]
                    if isinstance(project, dict) and project.get("id") is not None
                ]
            accounts.append(
                AccountRef(
                    id=int(account["id"]),
                    user_id=user_id,
                    user_name=user_name,
                    platform=str(account.get("platform") or ""),
                    account_name=str(account.get("account_name") or ""),
                    publication_type=str(account.get("publication_type") or ""),
                    theme_id=int(account["theme_id"]) if account.get("theme_id") is not None else None,
                    project_ids=tuple(int(pid) for pid in project_ids if pid is not None),
                    raw=account,
                )
            )
    return accounts


def account_summary(account: AccountRef) -> dict[str, Any]:
    return {
        "id": account.id,
        "user_id": account.user_id,
        "user_name": account.user_name,
        "platform": account.platform,
        "account_name": account.account_name,
        "publication_type": account.publication_type,
        "theme_id": account.theme_id,
        "project_ids": list(account.project_ids),
    }


def public_project(project: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": project.get("id"),
        "name": project.get("name"),
        "code": project.get("code"),
        "theme_ids": project.get("theme_ids") or [],
    }


def public_theme(theme: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": theme.get("id"),
        "name": theme.get("name"),
        "project_ids": theme.get("project_ids") or [],
    }


def normalize_text(value: Any) -> str:
    return str(value or "").strip().casefold()

