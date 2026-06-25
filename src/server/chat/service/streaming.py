# -*- coding: utf-8 -*-
"""SSE streaming helpers for chat services."""

from __future__ import annotations

from collections.abc import AsyncIterator
import json
from typing import Any

import httpx
from loguru import logger

from src.server.config import GlobalConfig

from .http_client import _chat_completions_url, _chat_headers, _upstream_error_detail
from .package_hooks import service_attr


async def _stream_sse_events(config: GlobalConfig, payload: dict[str, Any]) -> AsyncIterator[str]:
    try:
        async for event, data in _configured_stream_chat_events(config, payload):
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


async def _stream_chat_events(config: GlobalConfig, payload: dict[str, Any]) -> AsyncIterator[tuple[str, dict[str, Any]]]:
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


def _configured_stream_chat_events(config: GlobalConfig, payload: dict[str, Any]):
    stream_func = service_attr("_stream_chat_events", _stream_chat_events)
    return stream_func(config, payload)


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
