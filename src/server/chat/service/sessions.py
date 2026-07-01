# -*- coding: utf-8 -*-
"""Persistent chat session services."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from typing import Any

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
from .reasoning_adapter import assistant_rollout_message
from .serializers import _message_out, _message_outs_from_rollout_items, _message_role, _rollout_items_to_chat_message_inputs, _session_summary_out, _session_title_from_prompt
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
    rollout_items = dao.list_rollout_items(owner_user_id=user.id, session_id=session_id)
    if rollout_items:
        return _message_outs_from_rollout_items(rollout_items)
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
    _ensure_rollout_items_from_messages(dao, user_id=user.id, session_id=session.id)
    dao.append_message(owner_user_id=user.id, session_id=session.id, role="user", content=user_content)
    dao.append_message(
        owner_user_id=user.id,
        session_id=session.id,
        role="assistant",
        content=assistant_content,
        model=payload.model,
    )
    rollout_items = payload.rollout_items or [
        rollout_message("user", user_content),
        rollout_message("assistant", assistant_content),
    ]
    dao.append_rollout_items(owner_user_id=user.id, session_id=session.id, items=rollout_items)
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

    _ensure_rollout_items_from_messages(dao, user_id=user.id, session_id=session.id)
    dao.append_message(owner_user_id=user.id, session_id=session.id, role="user", content=prompt)
    dao.append_rollout_item(
        owner_user_id=user.id,
        session_id=session.id,
        item_type="message",
        payload=rollout_message("user", prompt),
    )
    skill_context = build_mentioned_skill_context(db, user, prompt)
    personal_aiwiki_context = build_personal_aiwiki_chat_context(user, prompt)
    session = dao.get_session(owner_user_id=user.id, session_id=session.id) or session
    rollout_items = dao.list_rollout_items(owner_user_id=user.id, session_id=session.id)
    if rollout_items:
        history_messages = _rollout_items_to_chat_message_inputs(rollout_items)
    else:
        messages = dao.list_messages(owner_user_id=user.id, session_id=session.id)
        history_messages = [
            {
                "role": _message_role(message.role),
                "content": message.content,
                **({"reasoning_content": message.reasoning_content} if message.reasoning_content is not None else {}),
            }
            for message in messages
        ]
    completion_payload = ChatCompletionIn(
        messages=[ChatMessageIn(**message) for message in tail_chat_history_preserving_tool_pairs(history_messages, limit=30)],
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
    reasoning_parts: list[str] = []
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
            if event == "reasoning_delta":
                reasoning_content = data.get("reasoning_content")
                if isinstance(reasoning_content, str) and reasoning_content:
                    reasoning_parts.append(reasoning_content)
                continue
            if event == "rollout_items":
                items = data.get("items")
                if isinstance(items, list):
                    dao.append_rollout_items(
                        owner_user_id=user.id,
                        session_id=session.id,
                        items=[item for item in items if isinstance(item, dict)],
                    )
                continue
            if event == "done":
                assistant_completed = _append_assistant_message(
                    dao,
                    user_id=user.id,
                    session_id=session.id,
                    model=model,
                    assistant_parts=assistant_parts,
                    reasoning_parts=reasoning_parts,
                )
                assistant_content = "".join(assistant_parts)
                if assistant_content.strip():
                    dao.append_rollout_item(
                        owner_user_id=user.id,
                        session_id=session.id,
                        item_type="message",
                        payload=rollout_message(
                            "assistant",
                            assistant_content,
                            reasoning_content="".join(reasoning_parts) if reasoning_parts else None,
                        ),
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
    reasoning_parts: list[str],
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
        reasoning_content="".join(reasoning_parts) if reasoning_parts else None,
    )
    return True


def _ensure_rollout_items_from_messages(dao: ChatDAO, *, user_id: int, session_id: str) -> None:
    if dao.list_rollout_items(owner_user_id=user_id, session_id=session_id):
        return
    legacy_messages = dao.list_messages(owner_user_id=user_id, session_id=session_id)
    if not legacy_messages:
        return
    dao.append_rollout_items(
        owner_user_id=user_id,
        session_id=session_id,
        items=[
            rollout_message(
                _message_role(message.role),
                message.content,
                reasoning_content=message.reasoning_content if message.role == "assistant" else None,
            )
            for message in legacy_messages
            if message.role in {"user", "assistant", "system"}
        ],
    )


def rollout_message(role: str, content: str, *, reasoning_content: str | None = None) -> dict[str, Any]:
    if role == "assistant":
        return assistant_rollout_message(content, reasoning_content=reasoning_content)
    return {"type": "message", "role": role, "content": content}


def tail_chat_history_preserving_tool_pairs(messages: list[dict], *, limit: int) -> list[dict]:
    if len(messages) <= limit:
        return messages
    start = len(messages) - limit
    while start > 0 and messages[start].get("role") == "tool":
        start -= 1
    return messages[start:]
