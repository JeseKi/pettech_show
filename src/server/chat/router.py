# -*- coding: utf-8 -*-
"""User chat routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response, Security, status
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_user
from src.server.auth.models import User
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from .schemas import (
    ChatCompletionIn,
    ChatCompletionOut,
    ChatMessageOut,
    ChatSessionRenameIn,
    ChatSessionStreamIn,
    ChatSessionSummaryOut,
)
from .service import (
    create_chat_completion,
    delete_chat_session,
    list_chat_messages,
    list_chat_sessions,
    rename_chat_session,
    stream_chat_completion,
    stream_persistent_chat_session,
)

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post(
    "/completions",
    response_model=ChatCompletionOut,
    summary="创建用户 Chat 回复",
)
async def chat_completion(
    payload: ChatCompletionIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await create_chat_completion(payload, db, current_user)


@router.post(
    "/completions/stream",
    summary="流式创建用户 Chat 回复",
)
async def chat_completion_stream(
    payload: ChatCompletionIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return StreamingResponse(
        stream_chat_completion(payload, db, current_user),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions",
    response_model=list[ChatSessionSummaryOut],
    summary="列出用户 Chat 会话",
)
async def list_sessions(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_chat_sessions(db, current_user))


@router.get(
    "/sessions/{session_id}/messages",
    response_model=list[ChatMessageOut],
    summary="获取用户 Chat 会话消息",
)
async def get_session_messages(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_chat_messages(db, current_user, session_id))


@router.patch(
    "/sessions/{session_id}",
    response_model=ChatSessionSummaryOut,
    summary="重命名用户 Chat 会话",
)
async def rename_session(
    session_id: str,
    payload: ChatSessionRenameIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: rename_chat_session(db, current_user, session_id, payload))


@router.delete(
    "/sessions/{session_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除用户 Chat 会话",
)
async def delete_session(
    session_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    await run_in_thread(lambda: delete_chat_session(db, current_user, session_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/sessions/stream",
    summary="流式创建并持久化用户 Chat 回复",
)
async def chat_session_stream(
    payload: ChatSessionStreamIn,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return StreamingResponse(
        stream_persistent_chat_session(db, current_user, payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
