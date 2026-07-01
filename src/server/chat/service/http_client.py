# -*- coding: utf-8 -*-
"""HTTP helpers for OpenAI-compatible chat APIs."""

from __future__ import annotations

from typing import Any

import httpx
from fastapi import HTTPException, status
from loguru import logger

from src.server.config import GlobalConfig

from ..schemas import ChatCompletionOut, ChatUsageOut
from .reasoning_adapter import extract_completion_assistant_message


async def _post_chat_completion(config: GlobalConfig, payload: dict[str, Any]) -> dict[str, Any]:
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
        raise HTTPException(status_code=status.HTTP_504_GATEWAY_TIMEOUT, detail="Chat API 请求超时") from exc
    except httpx.HTTPStatusError as exc:
        detail = _upstream_error_detail(exc.response)
        logger.warning(
            "Chat API upstream error: url={} status={} detail={}",
            _chat_completions_url(config),
            exc.response.status_code,
            detail,
        )
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Chat API 上游错误：{detail}") from exc
    except httpx.HTTPError as exc:
        logger.warning("Chat API request failed: {}", exc)
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API 请求失败") from exc
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API 返回了无效 JSON") from exc

    if not isinstance(data, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API 返回格式无效")
    return data


def _chat_completions_url(config: GlobalConfig) -> str:
    base_url = config.chat_api_base_url.rstrip("/")
    return f"{base_url}/chat/completions"


def _chat_headers(config: GlobalConfig) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {config.chat_api_key}",
        "Content-Type": "application/json",
    }


def _parse_completion(data: dict[str, Any], requested_model: str) -> ChatCompletionOut:
    choices = data.get("choices")
    if not isinstance(choices, list) or not choices:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API 返回缺少 choices")

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API choices 格式无效")

    assistant_message = extract_completion_assistant_message(data)
    content = assistant_message.content
    tool_calls = assistant_message.tool_calls
    if not content and not tool_calls:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Chat API 返回缺少 assistant content")

    raw_id = data.get("id")
    raw_model = data.get("model")
    usage = data.get("usage")
    parsed_usage = ChatUsageOut.model_validate(usage) if isinstance(usage, dict) else None
    return ChatCompletionOut(
        id=raw_id if isinstance(raw_id, str) else None,
        model=raw_model if isinstance(raw_model, str) else requested_model,
        content=content,
        usage=parsed_usage,
        raw=data,
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
