# -*- coding: utf-8 -*-
"""Serialization helpers for chat sessions and messages."""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from src.server.agent_market.service import agent_label_for_session

from ..models import ChatMessage, ChatSession
from ..schemas import ChatMessageOut, ChatRole, ChatSessionSummaryOut


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
