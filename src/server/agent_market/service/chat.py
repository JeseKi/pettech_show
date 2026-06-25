# -*- coding: utf-8 -*-
"""Agent prompt resolution for chat sessions."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import Agent, AgentPromptRevision
from .constants import DEFAULT_AGENT_ID
from .defaults import ensure_agent_market_defaults
from .queries import visible_agents_query
from .serializers import current_revision
from .types import AgentPromptContext


def resolve_agent_for_new_chat(db: Session, user: User, agent_id: str | None) -> AgentPromptContext:
    ensure_agent_market_defaults(db)
    target_agent_id = (agent_id or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID
    agent = visible_agents_query(db, user).filter(Agent.id == target_agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在或不可见")
    revision = current_revision(db, agent)
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体 Prompt 版本不存在")
    return AgentPromptContext(
        agent_id=agent.id,
        revision_id=revision.id,
        name=agent.title,
        system_prompt=revision.system_prompt,
    )


def resolve_pinned_agent_for_chat(db: Session, user: User, agent_id: str, revision_id: str) -> AgentPromptContext:
    ensure_agent_market_defaults(db)
    agent = visible_agents_query(db, user).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话智能体不存在或不可见")
    revision = (
        db.query(AgentPromptRevision)
        .filter(AgentPromptRevision.id == revision_id, AgentPromptRevision.agent_id == agent.id)
        .first()
    )
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="会话智能体 Prompt 版本不存在")
    return AgentPromptContext(
        agent_id=agent.id,
        revision_id=revision.id,
        name=agent.title,
        system_prompt=revision.system_prompt,
    )


def agent_label_for_session(db: Session, agent_id: str | None) -> str | None:
    if not agent_id:
        return None
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    return agent.title if agent else agent_id
