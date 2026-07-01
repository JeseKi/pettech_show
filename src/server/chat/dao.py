# -*- coding: utf-8 -*-
"""DAO for persistent user chat sessions."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.server.dao.dao_base import BaseDAO

from .models import ChatMessage, ChatRolloutItem, ChatSession, utc_now


class ChatDAO(BaseDAO):
    def __init__(self, db_session: Session):
        super().__init__(db_session)

    def create_session(self, *, owner_user_id: int, title: str) -> ChatSession:
        return self.create_session_with_agent(
            owner_user_id=owner_user_id,
            title=title,
            agent_id="zhongying-advertising",
            agent_revision_id="apr-zhongying-advertising-v1",
        )

    def create_session_with_agent(
        self,
        *,
        owner_user_id: int,
        title: str,
        agent_id: str,
        agent_revision_id: str,
    ) -> ChatSession:
        now = utc_now()
        session = ChatSession(
            id=f"chat-{uuid4().hex}",
            owner_user_id=owner_user_id,
            title=title[:100] or "新对话",
            agent_id=agent_id,
            agent_revision_id=agent_revision_id,
            created_at=now,
            updated_at=now,
        )
        self.db_session.add(session)
        self.db_session.commit()
        self.db_session.refresh(session)
        return session

    def get_session(self, *, owner_user_id: int, session_id: str) -> ChatSession | None:
        return (
            self.db_session.query(ChatSession)
            .populate_existing()
            .filter(ChatSession.id == session_id, ChatSession.owner_user_id == owner_user_id)
            .first()
        )

    def list_sessions(self, *, owner_user_id: int) -> list[ChatSession]:
        return (
            self.db_session.query(ChatSession)
            .filter(ChatSession.owner_user_id == owner_user_id)
            .order_by(ChatSession.updated_at.desc(), ChatSession.created_at.desc())
            .all()
        )

    def list_messages(self, *, owner_user_id: int, session_id: str) -> list[ChatMessage]:
        return (
            self.db_session.query(ChatMessage)
            .filter(ChatMessage.owner_user_id == owner_user_id, ChatMessage.session_id == session_id)
            .order_by(ChatMessage.sequence.asc(), ChatMessage.created_at.asc())
            .all()
        )

    def list_rollout_items(self, *, owner_user_id: int, session_id: str) -> list[ChatRolloutItem]:
        return (
            self.db_session.query(ChatRolloutItem)
            .filter(ChatRolloutItem.owner_user_id == owner_user_id, ChatRolloutItem.session_id == session_id)
            .order_by(ChatRolloutItem.sequence.asc(), ChatRolloutItem.created_at.asc())
            .all()
        )

    def append_message(
        self,
        *,
        owner_user_id: int,
        session_id: str,
        role: str,
        content: str,
        model: str | None = None,
    ) -> ChatMessage:
        now = utc_now()
        next_sequence = self.next_sequence(session_id=session_id)
        message = ChatMessage(
            id=f"msg-{uuid4().hex}",
            session_id=session_id,
            owner_user_id=owner_user_id,
            role=role,
            content=content,
            sequence=next_sequence,
            model=model,
            created_at=now,
        )
        session = (
            self.db_session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.owner_user_id == owner_user_id)
            .first()
        )
        if session:
            session.updated_at = now
        self.db_session.add(message)
        self.db_session.commit()
        self.db_session.refresh(message)
        return message

    def append_rollout_item(
        self,
        *,
        owner_user_id: int,
        session_id: str,
        item_type: str,
        payload: dict[str, Any],
    ) -> ChatRolloutItem:
        now = utc_now()
        next_sequence = self.next_rollout_sequence(session_id=session_id)
        item = ChatRolloutItem(
            id=f"rollout-{uuid4().hex}",
            session_id=session_id,
            owner_user_id=owner_user_id,
            sequence=next_sequence,
            item_type=item_type,
            payload_json=json.dumps(payload, ensure_ascii=False),
            created_at=now,
        )
        session = (
            self.db_session.query(ChatSession)
            .filter(ChatSession.id == session_id, ChatSession.owner_user_id == owner_user_id)
            .first()
        )
        if session:
            session.updated_at = now
        self.db_session.add(item)
        self.db_session.commit()
        self.db_session.refresh(item)
        return item

    def append_rollout_items(
        self,
        *,
        owner_user_id: int,
        session_id: str,
        items: list[dict[str, Any]],
    ) -> list[ChatRolloutItem]:
        created: list[ChatRolloutItem] = []
        for payload in items:
            item_type = str(payload.get("type") or "message")
            created.append(
                self.append_rollout_item(
                    owner_user_id=owner_user_id,
                    session_id=session_id,
                    item_type=item_type,
                    payload=payload,
                )
            )
        return created

    def next_sequence(self, *, session_id: str) -> int:
        current_max = (
            self.db_session.query(func.max(ChatMessage.sequence))
            .filter(ChatMessage.session_id == session_id)
            .scalar()
        )
        return int(current_max or 0) + 1

    def next_rollout_sequence(self, *, session_id: str) -> int:
        current_max = (
            self.db_session.query(func.max(ChatRolloutItem.sequence))
            .filter(ChatRolloutItem.session_id == session_id)
            .scalar()
        )
        return int(current_max or 0) + 1

    def rename_session(self, *, owner_user_id: int, session_id: str, title: str) -> ChatSession | None:
        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if not session:
            return None
        session.title = title[:100] or "新对话"
        self.db_session.commit()
        self.db_session.refresh(session)
        return session

    def delete_session(self, *, owner_user_id: int, session_id: str) -> bool:
        session = self.get_session(owner_user_id=owner_user_id, session_id=session_id)
        if not session:
            return False
        self.db_session.query(ChatMessage).filter(
            ChatMessage.owner_user_id == owner_user_id,
            ChatMessage.session_id == session_id,
        ).delete(synchronize_session=False)
        self.db_session.query(ChatRolloutItem).filter(
            ChatRolloutItem.owner_user_id == owner_user_id,
            ChatRolloutItem.session_id == session_id,
        ).delete(synchronize_session=False)
        self.db_session.delete(session)
        self.db_session.commit()
        return True

    def count_messages(self, *, owner_user_id: int, session_id: str) -> int:
        return (
            self.db_session.query(ChatMessage)
            .filter(ChatMessage.owner_user_id == owner_user_id, ChatMessage.session_id == session_id)
            .count()
        )
