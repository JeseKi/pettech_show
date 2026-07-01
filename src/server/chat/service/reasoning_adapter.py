# -*- coding: utf-8 -*-
"""Reasoning content adapter for OpenAI-compatible chat APIs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class AssistantMessageParts:
    content: str = ""
    reasoning_content: str | None = None
    tool_calls: list[dict[str, Any]] | None = None


@dataclass(frozen=True)
class StreamMessageDelta:
    content: str = ""
    reasoning_content: str = ""


def message_to_upstream(message: Any, *, keep_reasoning_content: bool = False) -> dict[str, Any]:
    item: dict[str, Any] = {"role": message.role, "content": message.content}
    if getattr(message, "name", None):
        item["name"] = message.name
    if getattr(message, "tool_call_id", None):
        item["tool_call_id"] = message.tool_call_id
    if getattr(message, "tool_calls", None):
        item["tool_calls"] = message.tool_calls
    reasoning_content = getattr(message, "reasoning_content", None)
    if keep_reasoning_content and isinstance(reasoning_content, str):
        item["reasoning_content"] = reasoning_content
    return item


def strip_reasoning_content_from_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {key: value for key, value in message.items() if key != "reasoning_content"}
        for message in messages
    ]


def extract_completion_assistant_message(data: dict[str, Any]) -> AssistantMessageParts:
    message = first_message(data)
    raw_content = message.get("content")
    content = raw_content if isinstance(raw_content, str) else ""
    reasoning_content = message.get("reasoning_content")
    tool_calls = message.get("tool_calls")
    return AssistantMessageParts(
        content=content,
        reasoning_content=reasoning_content if isinstance(reasoning_content, str) else None,
        tool_calls=tool_calls if isinstance(tool_calls, list) else None,
    )


def extract_stream_delta(chunk: dict[str, Any]) -> StreamMessageDelta:
    first_choice = first_choice_from_response(chunk)
    if first_choice is None:
        return StreamMessageDelta()

    delta = first_choice.get("delta")
    if isinstance(delta, dict):
        return StreamMessageDelta(
            content=_string_value(delta.get("content")),
            reasoning_content=_string_value(delta.get("reasoning_content")),
        )

    message = first_choice.get("message")
    if isinstance(message, dict):
        return StreamMessageDelta(
            content=_string_value(message.get("content")),
            reasoning_content=_string_value(message.get("reasoning_content")),
        )

    return StreamMessageDelta(content=_string_value(first_choice.get("text")))


def assistant_rollout_message(
    content: str,
    *,
    reasoning_content: str | None = None,
    tool_calls: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    message: dict[str, Any] = {"type": "message", "role": "assistant", "content": content}
    if reasoning_content is not None:
        message["reasoning_content"] = reasoning_content
    if tool_calls:
        message["tool_calls"] = tool_calls
    return message


def rollout_message_to_chat_input(payload: dict[str, Any]) -> dict[str, Any] | None:
    role = payload.get("role")
    if role not in {"system", "user", "assistant", "tool"}:
        return None
    message: dict[str, Any] = {
        "role": role,
        "content": payload.get("content") if isinstance(payload.get("content"), str) else "",
    }
    if isinstance(payload.get("name"), str):
        message["name"] = payload["name"]
    if isinstance(payload.get("tool_call_id"), str):
        message["tool_call_id"] = payload["tool_call_id"]
    if isinstance(payload.get("tool_calls"), list):
        message["tool_calls"] = payload["tool_calls"]
    if isinstance(payload.get("reasoning_content"), str):
        message["reasoning_content"] = payload["reasoning_content"]
    return message


def first_message(data: dict[str, Any]) -> dict[str, Any]:
    first_choice = first_choice_from_response(data)
    if first_choice is None:
        return {}
    message = first_choice.get("message")
    return message if isinstance(message, dict) else {}


def first_choice_from_response(data: dict[str, Any]) -> dict[str, Any] | None:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        return None
    first_choice = choices[0]
    return first_choice if isinstance(first_choice, dict) else None


def _string_value(value: Any) -> str:
    return value if isinstance(value, str) else ""
