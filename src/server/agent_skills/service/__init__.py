# -*- coding: utf-8 -*-
"""Service layer for file-backed agent skill marketplace with DB indexes."""

from __future__ import annotations

from .admin import (
    create_admin_category,
    create_admin_skill,
    create_admin_tag,
    delete_admin_category,
    delete_admin_skill,
    delete_admin_tag,
    get_admin_skill_detail,
    list_admin_categories,
    list_admin_skills,
    list_admin_tags,
    update_admin_category,
    update_admin_skill,
    update_admin_tag,
)
from .files import ensure_skill_market_root
from .market import (
    add_user_skill,
    build_mentioned_skill_context,
    list_market_categories,
    list_market_skills,
    list_user_skills,
    remove_user_skill,
)

__all__ = [
    "add_user_skill",
    "build_mentioned_skill_context",
    "create_admin_category",
    "create_admin_skill",
    "create_admin_tag",
    "delete_admin_category",
    "delete_admin_skill",
    "delete_admin_tag",
    "ensure_skill_market_root",
    "get_admin_skill_detail",
    "list_admin_categories",
    "list_admin_skills",
    "list_admin_tags",
    "list_market_categories",
    "list_market_skills",
    "list_user_skills",
    "remove_user_skill",
    "update_admin_category",
    "update_admin_skill",
    "update_admin_tag",
]
