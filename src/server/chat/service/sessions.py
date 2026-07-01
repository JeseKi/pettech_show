# -*- coding: utf-8 -*-
"""Persistent chat session services."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass

import httpx
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from src.server.agent_market.service import AgentPromptContext
from src.server.agent_market.service import resolve_agent_for_new_chat, resolve_pinned_agent_for_chat
from src.server.agent_skills.service import build_mentioned_skill_context
from src.server.auth.models import User
from src.server.config import GlobalConfig, global_config

from ..dao import ChatDAO
from ..models import ChatSession
from ..schemas import ChatCompletionIn, ChatMessageIn, ChatMessageOut, ChatSessionPersistIn, ChatSessionRenameIn, ChatSessionStreamIn, ChatSessionSummaryOut
from .http_client import _chat_completions_url, _upstream_error_detail
from .payloads import _build_upstream_payload, _resolve_chat_model
from .personal_aiwiki import build_personal_aiwiki_chat_context, stream_personal_aiwiki_tool_events
from .serializers import _message_out, _message_role, _session_summary_out, _session_title_from_prompt
from .streaming import _configured_stream_chat_events, _sse_event


@dataclass(frozen=True)
class SessionAgentResolution:
    session: ChatSession | None = None
    agent_context: AgentPromptContext | None = None
    error: str | None = None


def list_chat_sessions(db: Session, user: User) -> list[ChatSessionSummaryOut]:
    dao = ChatDAO(db)
    return [
        _session_summary_out(db, session, dao.count_messages(owner_user_id=user.id, session_id=session.id))
        for session in dao.list_sessions(owner_user_id=user.id)
    ]


def list_chat_messages(db: Session, user: User, session_id: str) -> list[ChatMessageOut]:
    dao = ChatDAO(db)
    session = dao.get_session(owner_user_id=user.id, session_id=session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return [_message_out(message) for message in dao.list_messages(owner_user_id=user.id, session_id=session_id)]


def rename_chat_session(db: Session, user: User, session_id: str, payload: ChatSessionRenameIn) -> ChatSessionSummaryOut:
    dao = ChatDAO(db)
    session = dao.rename_session(owner_user_id=user.id, session_id=session_id, title=payload.title.strip())
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return _session_summary_out(db, session, dao.count_messages(owner_user_id=user.id, session_id=session.id))


def delete_chat_session(db: Session, user: User, session_id: str) -> None:
    deleted = ChatDAO(db).delete_session(owner_user_id=user.id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")


def persist_frontend_chat_turn(db: Session, user: User, payload: ChatSessionPersistIn) -> ChatSessionSummaryOut:
    user_content = payload.user_content.strip()
    assistant_content = payload.assistant_content.strip()
    if not user_content or not assistant_content:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="消息不能为空")

    dao = ChatDAO(db)
    resolution = _resolve_session_and_agent(db, user, dao, payload, user_content)
    if resolution.error:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=resolution.error)
    if resolution.session is None or resolution.agent_context is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="会话初始化失败")

    session = resolution.session
    dao.append_message(owner_user_id=user.id, session_id=session.id, role="user", content=user_content)
    dao.append_message(
        owner_user_id=user.id,
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        model=payload.model,
    )
    session = dao.get_session(owner_user_id=user.id, session_id=session.id) or session
    return _session_summary_out(db, session, dao.count_messages(owner_user_id=user.id, session_id=session.id))


async def stream_persistent_chat_session(
    db: Session,
    user: User,
    payload: ChatSessionStreamIn,
    config: GlobalConfig = global_config,
) -> AsyncIterator[str]:
    prompt = payload.content.strip()
    if not prompt:
        yield _sse_event("error", {"message": "消息不能为空"})
        return

    try:
        _resolve_chat_model(payload.model, config)
    except HTTPException as exc:
        yield _sse_event("error", {"message": str(exc.detail)})
        return

    dao = ChatDAO(db)
    resolution = _resolve_session_and_agent(db, user, dao, payload, prompt)
    if resolution.error:
        yield _sse_event("error", {"message": resolution.error})
        return
    if resolution.session is None or resolution.agent_context is None:
        yield _sse_event("error", {"message": "会话初始化失败"})
        return
    session = resolution.session
    agent_context = resolution.agent_context

    dao.append_message(owner_user_id=user.id, session_id=session.id, role="user", content=prompt)
    skill_context = build_mentioned_skill_context(db, user, prompt)
    personal_aiwiki_context = build_personal_aiwiki_chat_context(user, prompt)
    session = dao.get_session(owner_user_id=user.id, session_id=session.id) or session
    messages = dao.list_messages(owner_user_id=user.id, session_id=session.id)
    completion_payload = ChatCompletionIn(
        messages=[ChatMessageIn(role=_message_role(message.role), content=message.content) for message in messages[-30:]],
        agent_id=agent_context.agent_id,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
        tools=payload.tools,
    )
    model, upstream_payload = _build_upstream_payload(
        completion_payload,
        config,
        stream=True,
        agent_system_prompt=agent_context.system_prompt,
        extra_system_context=skill_context,
        extra_user_context=personal_aiwiki_context.user_context,
        tools=personal_aiwiki_context.tools,
    )
    yield _sse_event("session", _session_summary_out(
        db,
        session,
        dao.count_messages(owner_user_id=user.id, session_id=session.id),
    ).model_dump())

    assistant_parts: list[str] = []
    assistant_completed = False
    try:
        event_stream = (
            stream_personal_aiwiki_tool_events(config, upstream_payload, user, frontend_canvas_mode="unavailable")
            if personal_aiwiki_context.enabled
            else _configured_stream_chat_events(config, upstream_payload)
        )
        async for event, data in event_stream:
            if event == "delta":
                content = data.get("content")
                if isinstance(content, str) and content:
                    assistant_parts.append(content)
                yield _sse_event(event, data)
                continue
            if event == "done":
                assistant_completed = _append_assistant_message(
                    dao,
                    user_id=user.id,
                    session_id=session.id,
                    model=model,
                    assistant_parts=assistant_parts,
                )
                yield _sse_event("done", {"session_id": session.id})
                continue
            yield _sse_event(event, data)
    except httpx.TimeoutException:
        yield _sse_event("error", {"message": "Chat API 请求超时"})
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API persistent stream upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        yield _sse_event("error", {"message": f"Chat API 上游错误：{detail}"})
    except httpx.HTTPError as exc:
        logger.warning("Chat API persistent stream request failed: {}", exc)
        yield _sse_event("error", {"message": "Chat API 请求失败"})
    except ValueError:
        yield _sse_event("error", {"message": "Chat API 返回了无效流式数据"})
    finally:
        if assistant_completed:
            logger.info("Persistent chat session completed: session_id={} user_id={}", session.id, user.id)


def _resolve_session_and_agent(
    db: Session,
    user: User,
    dao: ChatDAO,
    payload: ChatSessionStreamIn | ChatSessionPersistIn,
    prompt: str,
) -> SessionAgentResolution:
    if payload.session_id:
        session = dao.get_session(owner_user_id=user.id, session_id=payload.session_id)
        if not session:
            return SessionAgentResolution(error="会话不存在")
        if payload.agent_id and payload.agent_id != session.agent_id:
            return SessionAgentResolution(error="已有会话不能切换智能体，请新建对话")
        try:
            agent_context = resolve_pinned_agent_for_chat(db, user, session.agent_id, session.agent_revision_id)
        except HTTPException as exc:
            return SessionAgentResolution(error=str(exc.detail))
        return SessionAgentResolution(session=session, agent_context=agent_context)

    try:
        agent_context = resolve_agent_for_new_chat(db, user, payload.agent_id)
    except HTTPException as exc:
        return SessionAgentResolution(error=str(exc.detail))
    session = dao.create_session_with_agent(
        owner_user_id=user.id,
        title=_session_title_from_prompt(prompt),
        agent_id=agent_context.agent_id,
        agent_revision_id=agent_context.revision_id,
    )
    return SessionAgentResolution(session=session, agent_context=agent_context)


def _append_assistant_message(
    dao: ChatDAO,
    *,
    user_id: int,
    session_id: str,
    model: str,
    assistant_parts: list[str],
) -> bool:
    assistant_content = "".join(assistant_parts)
    if not assistant_content.strip():
        return False
    dao.append_message(
        owner_user_id=user_id,
        session_id=session_id,
        role="assistant",
        content=assistant_content,
        model=model,
    )
    return True
