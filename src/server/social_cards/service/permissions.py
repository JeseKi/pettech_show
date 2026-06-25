# -*- coding: utf-8 -*-
"""Social card authorization helpers."""

from __future__ import annotations

from src.server.auth.models import User
from src.server.auth.schemas import UserRole


def is_admin(user: User) -> bool:
    return user.role == UserRole.ADMIN


def can_access_job(user: User, owner_user_id: int | None) -> bool:
    return is_admin(user) or owner_user_id == user.id

