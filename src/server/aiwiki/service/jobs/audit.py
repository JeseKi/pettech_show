# -*- coding: utf-8 -*-
"""AI Wiki audit log queries."""

from __future__ import annotations

from typing import Literal

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ...dao import AiwikiJobDAO
from ...models import AiwikiAuditLog
from ...schemas import AiwikiAuditLogListOut, AiwikiAuditLogOut
from .access import is_admin


def list_audit_logs(
    db: Session,
    *,
    current_user: User,
    scope: str,
    limit: int,
    offset: int,
) -> AiwikiAuditLogListOut:
    normalized_scope: Literal["mine", "all"] = "all" if scope == "all" else "mine"
    if normalized_scope == "all" and not is_admin(current_user):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="只有管理员可以查看全部操作日志")
    normalized_limit = max(1, min(limit, 100))
    normalized_offset = max(0, offset)
    actor_filter = None if normalized_scope == "all" else current_user.id
    dao = AiwikiJobDAO(db)
    return AiwikiAuditLogListOut(
        items=[
            audit_log_out(log)
            for log in dao.list_audit_logs(
                limit=normalized_limit,
                offset=normalized_offset,
                actor_user_id=actor_filter,
            )
        ],
        total=dao.count_audit_logs(actor_user_id=actor_filter),
        limit=normalized_limit,
        offset=normalized_offset,
        scope=normalized_scope,
    )


def audit_log_out(log: AiwikiAuditLog) -> AiwikiAuditLogOut:
    from ..serializers import parse_json_dict

    return AiwikiAuditLogOut(
        id=log.id,
        actor_user_id=log.actor_user_id,
        actor_username=log.actor_username,
        action=log.action,
        job_id=log.job_id,
        target_filename=log.target_filename,
        message=log.message,
        metadata=parse_json_dict(log.metadata_json),
        created_at=log.created_at,
    )
