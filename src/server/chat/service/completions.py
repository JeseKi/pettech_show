# -*- coding: utf-8 -*-
"""Chat completion services."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.config import GlobalConfig, global_config

from ..schemas import ChatCompletionIn, ChatCompletionOut
from .http_client import _parse_completion, _post_chat_completion
from .package_hooks import service_attr
from .payloads import _agent_prompt_from_payload, _build_upstream_payload, _skill_context_from_payload
from .personal_aiwiki import (
    build_personal_aiwiki_chat_context,
    complete_with_personal_aiwiki_tools,
    stream_personal_aiwiki_sse_events,
)
from .streaming import _stream_sse_events


async def create_chat_completion(
    payload: ChatCompletionIn,
    db: Session | None = None,
    user: User | None = None,
    config: GlobalConfig = global_config,
) -> ChatCompletionOut:
    skill_context = _skill_context_from_payload(db, user, payload)
    personal_aiwiki_context = build_personal_aiwiki_chat_context(
        user,
        "\n".join(message.content for message in payload.messages if message.role == "user"),
    )
    agent_prompt = _agent_prompt_from_payload(db, user, payload)
    model, upstream_payload = _build_upstream_payload(
        payload,
        config,
        stream=False,
        agent_system_prompt=agent_prompt,
        extra_system_context=skill_context,
        extra_user_context=personal_aiwiki_context.user_context,
        tools=personal_aiwiki_context.tools,
    )
    post_func = service_attr("_post_chat_completion", _post_chat_completion)
    if personal_aiwiki_context.enabled and user is not None:
        data = await complete_with_personal_aiwiki_tools(config, upstream_payload, user, post_func)
    else:
        data = await post_func(config, upstream_payload)
    return _parse_completion(data, requested_model=model)


def stream_chat_completion(
    payload: ChatCompletionIn,
    db: Session | None = None,
    user: User | None = None,
    config: GlobalConfig = global_config,
) -> AsyncIterator[str]:
    skill_context = _skill_context_from_payload(db, user, payload)
    personal_aiwiki_context = build_personal_aiwiki_chat_context(
        user,
        "\n".join(message.content for message in payload.messages if message.role == "user"),
    )
    agent_prompt = _agent_prompt_from_payload(db, user, payload)
    _, upstream_payload = _build_upstream_payload(
        payload,
        config,
        stream=True,
        agent_system_prompt=agent_prompt,
        extra_system_context=skill_context,
        extra_user_context=personal_aiwiki_context.user_context,
        tools=personal_aiwiki_context.tools,
    )
    if personal_aiwiki_context.enabled and user is not None:
        return stream_personal_aiwiki_sse_events(config, upstream_payload, user)
    return _stream_sse_events(config, upstream_payload)
