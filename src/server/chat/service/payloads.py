# -*- coding: utf-8 -*-
"""OpenAI-compatible chat payload construction."""

from __future__ import annotations

from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.agent_market.service import resolve_agent_for_new_chat
from src.server.agent_skills.service import build_mentioned_skill_context
from src.server.auth.models import User
from src.server.config import GlobalConfig

from ..schemas import ChatCompletionIn


def _build_upstream_payload(
    payload: ChatCompletionIn,
    config: GlobalConfig,
    *,
    stream: bool,
    agent_system_prompt: str | None = None,
    extra_system_context: str = "",
    extra_user_context: str = "",
    tools: list[dict[str, Any]] | None = None,
) -> tuple[str, dict[str, Any]]:
    model = _resolve_chat_model(payload.model, config)
    upstream_payload: dict[str, Any] = {
        "model": model,
        "messages": _build_messages(
            payload,
            config,
            agent_system_prompt=agent_system_prompt,
            extra_system_context=extra_system_context,
            extra_user_context=extra_user_context,
        ),
        "temperature": payload.temperature if payload.temperature is not None else config.chat_temperature,
        "max_tokens": payload.max_tokens if payload.max_tokens is not None else config.chat_max_tokens,
    }
    if stream:
        upstream_payload["stream"] = True
    if tools:
        upstream_payload["tools"] = tools
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
    extra_user_context: str = "",
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    base_system_prompt = (
        agent_system_prompt.strip()
        if isinstance(agent_system_prompt, str) and agent_system_prompt.strip()
        else config.chat_system_prompt.strip()
    )
    system_parts = [part for part in (base_system_prompt, extra_system_context.strip()) if part]
    if system_parts:
        messages.append({"role": "system", "content": "\n\n".join(system_parts)})

    messages.extend({"role": message.role, "content": message.content} for message in payload.messages)
    if extra_user_context.strip():
        messages.append({"role": "user", "content": extra_user_context.strip()})
    return messages


def _skill_context_from_payload(db: Session | None, user: User | None, payload: ChatCompletionIn) -> str:
    if db is None or user is None:
        return ""
    prompt_text = "\n".join(message.content for message in payload.messages if message.role == "user")
    return build_mentioned_skill_context(db, user, prompt_text)


def _agent_prompt_from_payload(
    db: Session | None,
    user: User | None,
    payload: ChatCompletionIn,
) -> str | None:
    if db is None or user is None:
        return None
    return resolve_agent_for_new_chat(db, user, payload.agent_id).system_prompt
