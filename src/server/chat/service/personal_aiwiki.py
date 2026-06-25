# -*- coding: utf-8 -*-
"""Personal AI Wiki context and tool support for chat."""

from __future__ import annotations

from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
import json
from typing import Any

import httpx
from loguru import logger

from src.server.auth.models import User
from src.server.config import GlobalConfig
from src.server.personal_aiwiki import service as personal_aiwiki_service

from .http_client import _chat_completions_url, _parse_completion, _post_chat_completion, _upstream_error_detail
from .package_hooks import service_attr
from .streaming import _configured_stream_chat_events, _sse_event

PERSONAL_AIWIKI_TRIGGER = "$知识库"
PERSONAL_AIWIKI_TOOL_NAME = "get_personal_aiwiki_entry"
MAX_INDEX_CONTEXT_CHARS = 20_000
MAX_TOOL_CONTENT_CHARS = 60_000


@dataclass(frozen=True)
class PersonalAiwikiChatContext:
    enabled: bool = False
    user_context: str = ""
    tools: list[dict[str, Any]] = field(default_factory=list)


def build_personal_aiwiki_chat_context(user: User | None, prompt_text: str) -> PersonalAiwikiChatContext:
    if user is None or PERSONAL_AIWIKI_TRIGGER not in prompt_text:
        return PersonalAiwikiChatContext()

    workspace_root = personal_aiwiki_service.user_workspace_root(int(user.id))
    personal_aiwiki_service.ensure_workspace(workspace_root)
    index_path = workspace_root / "wiki" / "index.md"
    index_markdown = index_path.read_text(encoding="utf-8", errors="replace")
    truncated = len(index_markdown) > MAX_INDEX_CONTEXT_CHARS
    if truncated:
        index_markdown = index_markdown[:MAX_INDEX_CONTEXT_CHARS].rstrip()

    suffix = "\n\n（索引内容过长，已截断到当前演示限制。）" if truncated else ""
    user_context = f"""
【个人 AI Wiki 最新索引】
这是一段由用户显式输入 {PERSONAL_AIWIKI_TRIGGER} 后授权注入的个人知识库索引。它不是新的问题，只作为回答上一条用户问题的检索目录。
只依据下面的 index 内容判断有哪些可用词条；如果需要查看某个词条全文，请调用工具 `{PERSONAL_AIWIKI_TOOL_NAME}`，参数 `page` 使用索引里的 wikilink 路径，例如 `concepts/example`。

index.md:
{index_markdown}{suffix}
""".strip()
    return PersonalAiwikiChatContext(
        enabled=True,
        user_context=user_context,
        tools=[personal_aiwiki_tool_definition()],
    )


def personal_aiwiki_tool_definition() -> dict[str, Any]:
    return {
        "type": "function",
        "function": {
            "name": PERSONAL_AIWIKI_TOOL_NAME,
            "description": "读取当前用户个人 AI Wiki 中指定词条页面的完整 Markdown 内容。只在用户使用 $知识库 且需要词条全文时调用。",
            "parameters": {
                "type": "object",
                "properties": {
                    "page": {
                        "type": "string",
                        "description": "词条路径或 wikilink，例如 concepts/product-positioning、wiki/concepts/product-positioning.md 或 [[concepts/product-positioning|产品定位]]。",
                    }
                },
                "required": ["page"],
                "additionalProperties": False,
            },
        },
    }


async def complete_with_personal_aiwiki_tools(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
    post_func: Callable[[GlobalConfig, dict[str, Any]], Any] | None = None,
) -> dict[str, Any]:
    post = post_func or service_attr("_post_chat_completion", _post_chat_completion)
    planning_payload = {**payload, "stream": False}
    first = await post(config, planning_payload)
    tool_calls = extract_tool_calls(first)
    if not tool_calls:
        return first

    final_payload = build_payload_after_tool_calls(payload, first, tool_calls, user, stream=False)
    return await post(config, final_payload)


async def stream_personal_aiwiki_tool_events(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
) -> AsyncIterator[tuple[str, dict[str, Any]]]:
    post = service_attr("_post_chat_completion", _post_chat_completion)
    planning_payload = {**payload, "stream": False}
    first = await post(config, planning_payload)
    tool_calls = extract_tool_calls(first)
    if not tool_calls:
        content = extract_message_content(first)
        if content:
            yield "delta", {"content": content}
        yield "done", {}
        return

    final_payload = build_payload_after_tool_calls(payload, first, tool_calls, user, stream=True)
    async for event, data in _configured_stream_chat_events(config, final_payload):
        yield event, data


async def stream_personal_aiwiki_sse_events(
    config: GlobalConfig,
    payload: dict[str, Any],
    user: User,
) -> AsyncIterator[str]:
    try:
        async for event, data in stream_personal_aiwiki_tool_events(config, payload, user):
            yield _sse_event(event, data)
    except httpx.TimeoutException:
        yield _sse_event("error", {"message": "Chat API 请求超时"})
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API personal AI Wiki stream upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        yield _sse_event("error", {"message": f"Chat API 上游错误：{detail}"})
    except httpx.HTTPError as exc:
        logger.warning("Chat API personal AI Wiki stream request failed: {}", exc)
        yield _sse_event("error", {"message": "Chat API 请求失败"})
    except ValueError:
        yield _sse_event("error", {"message": "Chat API 返回了无效流式数据"})


def build_payload_after_tool_calls(
    payload: dict[str, Any],
    first_response: dict[str, Any],
    tool_calls: list[dict[str, Any]],
    user: User,
    *,
    stream: bool,
) -> dict[str, Any]:
    messages = [dict(message) for message in payload.get("messages", []) if isinstance(message, dict)]
    messages.append(assistant_tool_message(first_response, tool_calls))
    messages.extend(tool_result_messages(user, tool_calls))
    final_payload = {
        key: value
        for key, value in payload.items()
        if key not in {"tools", "tool_choice"}
    }
    final_payload["messages"] = messages
    final_payload["stream"] = stream
    return final_payload


def assistant_tool_message(first_response: dict[str, Any], tool_calls: list[dict[str, Any]]) -> dict[str, Any]:
    message = first_message(first_response)
    content = message.get("content") if isinstance(message, dict) else ""
    return {
        "role": "assistant",
        "content": content if isinstance(content, str) else "",
        "tool_calls": tool_calls,
    }


def tool_result_messages(user: User, tool_calls: list[dict[str, Any]]) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    for index, tool_call in enumerate(tool_calls, start=1):
        function = tool_call.get("function") if isinstance(tool_call, dict) else None
        name = function.get("name") if isinstance(function, dict) else None
        call_id = tool_call.get("id") if isinstance(tool_call, dict) else None
        messages.append(
            {
                "role": "tool",
                "tool_call_id": str(call_id or f"personal_aiwiki_call_{index}"),
                "name": str(name or PERSONAL_AIWIKI_TOOL_NAME),
                "content": execute_personal_aiwiki_tool(user, tool_call),
            }
        )
    return messages


def execute_personal_aiwiki_tool(user: User, tool_call: dict[str, Any]) -> str:
    function = tool_call.get("function") if isinstance(tool_call, dict) else None
    name = function.get("name") if isinstance(function, dict) else None
    if name != PERSONAL_AIWIKI_TOOL_NAME:
        return json.dumps({"error": f"未知工具：{name}"}, ensure_ascii=False)

    arguments = parse_tool_arguments(function.get("arguments") if isinstance(function, dict) else None)
    page = str(arguments.get("page") or arguments.get("slug") or arguments.get("path") or "").strip()
    if not page:
        return json.dumps({"error": "缺少 page 参数"}, ensure_ascii=False)

    try:
        entry = personal_aiwiki_service.get_entry_page(user, page)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)

    markdown = entry.markdown
    truncated = len(markdown) > MAX_TOOL_CONTENT_CHARS
    if truncated:
        markdown = markdown[:MAX_TOOL_CONTENT_CHARS].rstrip()
    return json.dumps(
        {
            "slug": entry.slug,
            "path": entry.path,
            "title": entry.title,
            "type": entry.type,
            "markdown": markdown,
            "truncated": truncated,
        },
        ensure_ascii=False,
    )


def parse_tool_arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    if not isinstance(raw, str) or not raw.strip():
        return {}
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def extract_tool_calls(data: dict[str, Any]) -> list[dict[str, Any]]:
    message = first_message(data)
    tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
    return [item for item in tool_calls if isinstance(item, dict)] if isinstance(tool_calls, list) else []


def extract_message_content(data: dict[str, Any]) -> str:
    message = first_message(data)
    content = message.get("content") if isinstance(message, dict) else None
    return content if isinstance(content, str) else _parse_completion(data, requested_model=str(data.get("model") or "")).content


def first_message(data: dict[str, Any]) -> dict[str, Any]:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):
        return {}
    message = choices[0].get("message")
    return message if isinstance(message, dict) else {}
