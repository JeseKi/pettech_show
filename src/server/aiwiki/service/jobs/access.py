# -*- coding: utf-8 -*-
"""Access helpers for AI Wiki jobs."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ...dao import AiwikiJobDAO


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def can_access_job(user: User, owner_user_id: int | None) -> bool:
    return owner_user_id == user.id or is_admin(user)


def default_admin_user_id(db: Session) -> int | None:
    return AiwikiJobDAO(db).default_admin_user_id()


def normalize_optional_text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
