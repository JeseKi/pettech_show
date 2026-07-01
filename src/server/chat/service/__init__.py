# -*- coding: utf-8 -*-
"""Service layer for user chat."""

from __future__ import annotations

from .completions import create_chat_completion, stream_chat_completion
from .http_client import (
    _chat_completions_url,
    _chat_headers,
    _parse_completion,
    _post_chat_completion,
    _upstream_error_detail,
)
from .payloads import (
    _agent_prompt_from_payload,
    _build_messages,
    _build_upstream_payload,
    _resolve_chat_model,
    _skill_context_from_payload,
)
from .personal_aiwiki import (
    PERSONAL_AIWIKI_TOOL_NAME,
    build_personal_aiwiki_chat_context,
    complete_with_personal_aiwiki_tools,
)
from .serializers import (
    _message_out,
    _message_role,
    _session_summary_out,
    _session_title_from_prompt,
)
from .sessions import (
    delete_chat_session,
    list_chat_messages,
    list_chat_sessions,
    persist_frontend_chat_turn,
    rename_chat_session,
    stream_persistent_chat_session,
)
from .streaming import _extract_stream_content, _sse_event, _stream_chat_events, _stream_sse_events

__all__ = [
    "_agent_prompt_from_payload",
    "_build_messages",
    "_build_upstream_payload",
    "_chat_completions_url",
    "_chat_headers",
    "_extract_stream_content",
    "_message_out",
    "_message_role",
    "_parse_completion",
    "_post_chat_completion",
    "_resolve_chat_model",
    "_session_summary_out",
    "_session_title_from_prompt",
    "_skill_context_from_payload",
    "_sse_event",
    "_stream_chat_events",
    "_stream_sse_events",
    "_upstream_error_detail",
    "PERSONAL_AIWIKI_TOOL_NAME",
    "build_personal_aiwiki_chat_context",
    "complete_with_personal_aiwiki_tools",
    "create_chat_completion",
    "delete_chat_session",
    "list_chat_messages",
    "list_chat_sessions",
    "persist_frontend_chat_turn",
    "rename_chat_session",
    "stream_chat_completion",
    "stream_persistent_chat_session",
]
