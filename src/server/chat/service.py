# -*- coding: utf-8 -*-
"""Service layer for user chat."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any, cast

import httpx
from fastapi import HTTPException, status
from loguru import logger
from sqlalchemy.orm import Session

from src.server.agent_skills.service import build_mentioned_skill_context
from src.server.agent_market.service import (
    agent_label_for_session,
    resolve_agent_for_new_chat,
    resolve_pinned_agent_for_chat,
)
from src.server.auth.models import User
from src.server.config import GlobalConfig, global_config

from .dao import ChatDAO
from .models import ChatMessage, ChatSession
from .schemas import (
    ChatCompletionIn,
    ChatCompletionOut,
    ChatMessageIn,
    ChatMessageOut,
    ChatRole,
    ChatSessionRenameIn,
    ChatSessionStreamIn,
    ChatSessionSummaryOut,
    ChatUsageOut,
)


async def create_chat_completion(
    payload: ChatCompletionIn,
    db: Session | None = None,
    user: User | None = None,
    config: GlobalConfig = global_config,
) -> ChatCompletionOut:
    skill_context = _skill_context_from_payload(db, user, payload)
    agent_prompt = _agent_prompt_from_payload(db, user, payload)
    model, upstream_payload = _build_upstream_payload(
        payload,
        config,
        stream=False,
        agent_system_prompt=agent_prompt,
        extra_system_context=skill_context,
    )
    data = await _post_chat_completion(config, upstream_payload)
    return _parse_completion(data, requested_model=model)


def stream_chat_completion(
    payload: ChatCompletionIn,
    db: Session | None = None,
    user: User | None = None,
    config: GlobalConfig = global_config,
) -> AsyncIterator[str]:
    skill_context = _skill_context_from_payload(db, user, payload)
    agent_prompt = _agent_prompt_from_payload(db, user, payload)
    _, upstream_payload = _build_upstream_payload(
        payload,
        config,
        stream=True,
        agent_system_prompt=agent_prompt,
        extra_system_context=skill_context,
    )
    return _stream_sse_events(config, upstream_payload)


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


def rename_chat_session(
    db: Session,
    user: User,
    session_id: str,
    payload: ChatSessionRenameIn,
) -> ChatSessionSummaryOut:
    dao = ChatDAO(db)
    session = dao.rename_session(owner_user_id=user.id, session_id=session_id, title=payload.title.strip())
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")
    return _session_summary_out(db, session, dao.count_messages(owner_user_id=user.id, session_id=session.id))


def delete_chat_session(db: Session, user: User, session_id: str) -> None:
    deleted = ChatDAO(db).delete_session(owner_user_id=user.id, session_id=session_id)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话不存在")


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
    if payload.session_id:
        session = dao.get_session(owner_user_id=user.id, session_id=payload.session_id)
        if not session:
            yield _sse_event("error", {"message": "会话不存在"})
            return
        if payload.agent_id and payload.agent_id != session.agent_id:
            yield _sse_event("error", {"message": "已有会话不能切换智能体，请新建对话"})
            return
        try:
            agent_context = resolve_pinned_agent_for_chat(
                db,
                user,
                session.agent_id,
                session.agent_revision_id,
            )
        except HTTPException as exc:
            yield _sse_event("error", {"message": str(exc.detail)})
            return
    else:
        try:
            agent_context = resolve_agent_for_new_chat(db, user, payload.agent_id)
        except HTTPException as exc:
            yield _sse_event("error", {"message": str(exc.detail)})
            return
        session = dao.create_session_with_agent(
            owner_user_id=user.id,
            title=_session_title_from_prompt(prompt),
            agent_id=agent_context.agent_id,
            agent_revision_id=agent_context.revision_id,
        )

    dao.append_message(
        owner_user_id=user.id,
        session_id=session.id,
        role="user",
        content=prompt,
    )
    skill_context = build_mentioned_skill_context(db, user, prompt)
    session = dao.get_session(owner_user_id=user.id, session_id=session.id) or session
    messages = dao.list_messages(owner_user_id=user.id, session_id=session.id)
    completion_payload = ChatCompletionIn(
        messages=[
            ChatMessageIn(role=_message_role(message.role), content=message.content)
            for message in messages[-30:]
        ],
        agent_id=agent_context.agent_id,
        model=payload.model,
        temperature=payload.temperature,
        max_tokens=payload.max_tokens,
    )
    model, upstream_payload = _build_upstream_payload(
        completion_payload,
        config,
        stream=True,
        agent_system_prompt=agent_context.system_prompt,
        extra_system_context=skill_context,
    )
    yield _sse_event("session", _session_summary_out(
        db,
        session,
        dao.count_messages(owner_user_id=user.id, session_id=session.id),
    ).model_dump())

    assistant_parts: list[str] = []
    assistant_completed = False
    try:
        async for event, data in _stream_chat_events(config, upstream_payload):
            if event == "delta":
                content = data.get("content")
                if isinstance(content, str) and content:
                    assistant_parts.append(content)
                yield _sse_event(event, data)
                continue

            if event == "done":
                assistant_content = "".join(assistant_parts)
                if assistant_content.strip():
                    dao.append_message(
                        owner_user_id=user.id,
                        session_id=session.id,
                        role="assistant",
                        content=assistant_content,
                        model=model,
                    )
                    assistant_completed = True
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


def _build_upstream_payload(
    payload: ChatCompletionIn,
    config: GlobalConfig,
    *,
    stream: bool,
    agent_system_prompt: str | None = None,
    extra_system_context: str = "",
) -> tuple[str, dict[str, Any]]:
    model = _resolve_chat_model(payload.model, config)

    upstream_payload: dict[str, Any] = {
        "model": model,
        "messages": _build_messages(
            payload,
            config,
            agent_system_prompt=agent_system_prompt,
            extra_system_context=extra_system_context,
        ),
        "temperature": (
            payload.temperature
            if payload.temperature is not None
            else config.chat_temperature
        ),
        "max_tokens": (
            payload.max_tokens
            if payload.max_tokens is not None
            else config.chat_max_tokens
        ),
    }
    if stream:
        upstream_payload["stream"] = True

    return model, upstream_payload


def _resolve_chat_model(model: str | None, config: GlobalConfig) -> str:
    if not config.chat_api_key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat API 未配置：请设置 CHAT_API_KEY",
        )

    resolved_model = (model or config.chat_model).strip()
    if not resolved_model:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Chat API 未配置：请设置 CHAT_MODEL",
        )
    return resolved_model


def _build_messages(
    payload: ChatCompletionIn,
    config: GlobalConfig,
    *,
    agent_system_prompt: str | None = None,
    extra_system_context: str = "",
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    base_system_prompt = (
        agent_system_prompt.strip()
        if isinstance(agent_system_prompt, str) and agent_system_prompt.strip()
        else config.chat_system_prompt.strip()
    )
    system_parts = [
        part
        for part in (base_system_prompt, extra_system_context.strip())
        if part
    ]
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    messages.extend(
        {"role": message.role, "content": message.content}
        for message in payload.messages
    )
    return messages


def _skill_context_from_payload(
    db: Session | None,
    user: User | None,
    payload: ChatCompletionIn,
) -> str:
    if db is None or user is None:
        return ""
    prompt_text = "\n".join(
        message.content
        for message in payload.messages
        if message.role == "user"
    )
    return build_mentioned_skill_context(db, user, prompt_text)


def _agent_prompt_from_payload(
    db: Session | None,
    user: User | None,
    payload: ChatCompletionIn,
) -> str | None:
    if db is None or user is None:
        return None
    return resolve_agent_for_new_chat(db, user, payload.agent_id).system_prompt


async def _post_chat_completion(
    config: GlobalConfig,
    payload: dict[str, Any],
) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(timeout=config.chat_timeout_seconds) as client:
            response = await client.post(
                _chat_completions_url(config),
                headers=_chat_headers(config),
                json=payload,
            )
            response.raise_for_status()
            data = response.json()
    except httpx.TimeoutException as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail="Chat API 请求超时",
        ) from exc
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Chat API 上游错误：{detail}",
        ) from exc
    except httpx.HTTPError as exc:
        logger.warning("Chat API request failed: {}", exc)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API 请求失败",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API 返回了无效 JSON",
        ) from exc

    if not isinstance(data, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API 返回格式无效",
        )
    return data


async def _stream_sse_events(
    config: GlobalConfig,
    payload: dict[str, Any],
) -> AsyncIterator[str]:
    try:
        async for event, data in _stream_chat_events(config, payload):
            yield _sse_event(event, data)
    except httpx.TimeoutException:
        yield _sse_event("error", {"message": "Chat API 请求超时"})
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API stream upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        yield _sse_event("error", {"message": f"Chat API 上游错误：{detail}"})
    except httpx.HTTPError as exc:
        logger.warning("Chat API stream request failed: {}", exc)
        yield _sse_event("error", {"message": "Chat API 请求失败"})
    except ValueError:
        yield _sse_event("error", {"message": "Chat API 返回了无效流式数据"})


async def _stream_chat_events(
    config: GlobalConfig,
    payload: dict[str, Any],
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    sent_done = False
    async with httpx.AsyncClient(timeout=config.chat_timeout_seconds) as client:
        async with client.stream(
            "POST",
            _chat_completions_url(config),
            headers=_chat_headers(config),
            json=payload,
        ) as response:
            if response.is_error:
                await response.aread()
            response.raise_for_status()

            async for raw_line in response.aiter_lines():
                line = raw_line.strip()
                if not line or line.startswith(":"):
                    continue

                if line.startswith("data:"):
                    line = line.removeprefix("data:").strip()

                if line == "[DONE]":
                    sent_done = True
                    yield "done", {}
                    break

                chunk = json.loads(line)
                content = _extract_stream_content(chunk)
                if content:
                    yield "delta", {"content": content}

    if not sent_done:
        yield "done", {}


def _chat_completions_url(config: GlobalConfig) -> str:
    base_url = config.chat_api_base_url.rstrip("/")
    return f"{base_url}/chat/completions"


def _chat_headers(config: GlobalConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.chat_api_key}",
        "Content-Type": "application/json",
    }


def _sse_event(event: str, data: dict[str, Any]) -> str:
    encoded = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {encoded}\n\n"


def _extract_stream_content(chunk: dict[str, Any]) -> str:
    choices = chunk.get("choices")
    if not isinstance(choices, list) or not choices:
        return ""

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        return ""

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        content = delta.get("content")
        if isinstance(content, str):
            return content

    message = first_choice.get("message")
    if isinstance(message, dict):
        content = message.get("content")
        if isinstance(content, str):
            return content

    text = first_choice.get("text")
    return text if isinstance(text, str) else ""


def _parse_completion(data: dict[str, Any], requested_model: str) -> ChatCompletionOut:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API 返回缺少 choices",
        )

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API choices 格式无效",
        )

    message = first_choice.get("message")
    content = ""
    if isinstance(message, dict):
        raw_content = message.get("content")
        if isinstance(raw_content, str):
            content = raw_content

    if not content:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Chat API 返回缺少 assistant content",
        )

    raw_id = data.get("id")
    raw_model = data.get("model")
    usage = data.get("usage")
    parsed_usage = ChatUsageOut.model_validate(usage) if isinstance(usage, dict) else None
    return ChatCompletionOut(
        id=raw_id if isinstance(raw_id, str) else None,
        model=raw_model if isinstance(raw_model, str) else requested_model,
        content=content,
        usage=parsed_usage,
    )


def _upstream_error_detail(response: httpx.Response) -> str:
    try:
        data = response.json()
    except httpx.ResponseNotRead:
        return f"HTTP {response.status_code}"
    except ValueError:
        try:
            text = response.text
        except httpx.ResponseNotRead:
            return f"HTTP {response.status_code}"
        return text[:500] or f"HTTP {response.status_code}"

    if isinstance(data, dict):
        error = data.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        detail = data.get("detail")
        if isinstance(detail, str) and detail:
            return detail

    return f"HTTP {response.status_code}"


def _session_summary_out(db: Session, session: ChatSession, message_count: int) -> ChatSessionSummaryOut:
    return ChatSessionSummaryOut(
        id=session.id,
        title=session.title,
        agent_id=session.agent_id,
        agent_revision_id=session.agent_revision_id,
        agent_name=agent_label_for_session(db, session.agent_id),
        created_at=_iso(session.created_at),
        updated_at=_iso(session.updated_at),
        message_count=message_count,
    )


def _message_out(message: ChatMessage) -> ChatMessageOut:
    return ChatMessageOut(
        id=message.id,
        role=_message_role(message.role),
        content=message.content,
        created_at=_iso(message.created_at),
    )


def _message_role(role: str) -> ChatRole:
    if role in {"system", "user", "assistant"}:
        return cast(ChatRole, role)
    return "assistant"


def _session_title_from_prompt(prompt: str) -> str:
    compact = "".join(prompt.split())
    return "".join(list(compact)[:5]) or "新对话"


def _iso(value) -> str:
    return value.isoformat()
