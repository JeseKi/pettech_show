# -*- coding: utf-8 -*-
"""Serialization helpers for chat sessions and messages."""

from __future__ import annotations

import json
from typing import Any
from typing import cast

from sqlalchemy.orm import Session

from src.server.agent_market.service import agent_label_for_session

from ..models import ChatMessage, ChatRolloutItem, ChatSession
from ..schemas import ChatMessageOut, ChatRole, ChatSessionSummaryOut, ChatToolStepOut
from .reasoning_adapter import rollout_message_to_chat_input


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


def _message_outs_from_rollout_items(items: list[ChatRolloutItem]) -> list[ChatMessageOut]:
    messages: list[ChatMessageOut] = []
    pending_steps: list[ChatToolStepOut] = []
    for item in items:
        payload = _rollout_payload(item)
        role = payload.get("role")
        if role == "tool":
            pending_steps.append(_tool_result_step(payload))
            continue

        if role not in {"user", "assistant"}:
            continue

        content = payload.get("content")
        text = content if isinstance(content, str) else ""
        tool_calls = payload.get("tool_calls")
        if role == "assistant" and isinstance(tool_calls, list) and tool_calls:
            if text.strip():
                pending_steps.append(ChatToolStepOut(kind="model_output", status="done", title="模型中间输出", content=text.strip()))
            pending_steps.extend(_tool_call_step(tool_call) for tool_call in tool_calls if isinstance(tool_call, dict))
            continue

        messages.append(
            ChatMessageOut(
                id=item.id,
                role=_message_role(str(role)),
                content=text,
                created_at=_iso(item.created_at),
                tool_steps=pending_steps if role == "assistant" else [],
            )
        )
        if role == "assistant":
            pending_steps = []

    return messages


def _rollout_items_to_chat_message_inputs(items: list[ChatRolloutItem]) -> list[dict[str, Any]]:
    messages: list[dict[str, Any]] = []
    for item in items:
        payload = _rollout_payload(item)
        role = payload.get("role")
        if role not in {"system", "user", "assistant", "tool"}:
            continue
        message = rollout_message_to_chat_input(payload)
        if message is not None:
            messages.append(message)
    return messages


def _rollout_payload(item: ChatRolloutItem) -> dict[str, Any]:
    try:
        payload = json.loads(item.payload_json)
    except json.JSONDecodeError:
        return {}
    return payload if isinstance(payload, dict) else {}


def _tool_call_step(tool_call: dict[str, Any]) -> ChatToolStepOut:
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    name = function.get("name") if isinstance(function, dict) and isinstance(function.get("name"), str) else "unknown"
    arguments = function.get("arguments") if isinstance(function, dict) and isinstance(function.get("arguments"), str) else ""
    return ChatToolStepOut(
        kind="tool_call",
        name=name,
        status="done",
        title=f"调用工具：{name}",
        content=arguments,
    )


def _tool_result_step(payload: dict[str, Any]) -> ChatToolStepOut:
    name = payload.get("name") if isinstance(payload.get("name"), str) else None
    content = payload.get("content") if isinstance(payload.get("content"), str) else ""
    return ChatToolStepOut(
        kind="tool_result",
        name=name,
        status="done",
        title=f"工具结果：{name or payload.get('tool_call_id') or 'unknown'}",
        content=content,
    )


def _message_role(role: str) -> ChatRole:
    if role in {"system", "user", "assistant", "tool"}:
        return cast(ChatRole, role)
    return "assistant"


def _session_title_from_prompt(prompt: str) -> str:
    compact = "".join(prompt.split())
    return "".join(list(compact)[:5]) or "新对话"


def _iso(value) -> str:
    return value.isoformat()
