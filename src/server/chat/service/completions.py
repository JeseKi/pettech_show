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
from .streaming import _stream_sse_events


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
    post_func = service_attr("_post_chat_completion", _post_chat_completion)
    data = await post_func(config, upstream_payload)
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
