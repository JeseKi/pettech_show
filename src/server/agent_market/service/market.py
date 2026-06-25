# -*- coding: utf-8 -*-
"""Public and user agent marketplace services."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import Agent, AgentCategory, UserAgent
from ..schemas import AgentCategoryOut, AgentOut, AgentPageOut, UserAgentOut, UserAgentPageOut
from .constants import DEFAULT_AGENT_ID
from .defaults import ensure_agent_market_defaults
from .queries import (
    added_agent_ids,
    agent_matches_search,
    apply_agent_search,
    apply_visible_agent_filters,
    visible_agents_query,
)
from .serializers import agent_out, agent_tags, category_out


def list_market_categories(db: Session, user: User) -> list[AgentCategoryOut]:
    ensure_agent_market_defaults(db)
    query = (
        db.query(AgentCategory)
        .join(Agent, Agent.category_id == AgentCategory.id)
        .filter(AgentCategory.enabled.is_(True), Agent.enabled.is_(True))
    )
    query = apply_visible_agent_filters(query, user)
    rows = (
        query.distinct()
        .order_by(AgentCategory.sort_order.asc(), AgentCategory.name.asc())
        .all()
    )
    return [category_out(row) for row in rows]


def list_market_agents(
    db: Session,
    user: User,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AgentPageOut:
    ensure_agent_market_defaults(db)
    query = visible_agents_query(db, user)
    if category:
        query = query.filter(Agent.category_id == category)
    query = apply_agent_search(query, search)
    total = query.order_by(None).count()
    rows = (
        query.order_by(Agent.sort_order.asc(), Agent.title.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    added_ids = added_agent_ids(db, user)
    return AgentPageOut(
        items=[agent_out(db, agent, include_prompt=False, added=agent.id in added_ids) for agent in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_default_agent(db: Session, user: User) -> AgentOut:
    ensure_agent_market_defaults(db)
    agent = visible_agents_query(db, user).filter(Agent.id == DEFAULT_AGENT_ID).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="默认智能体不可用")
    return agent_out(db, agent, include_prompt=False, added=True)


def list_user_agents(
    db: Session,
    user: User,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserAgentPageOut:
    ensure_agent_market_defaults(db)
    query = (
        db.query(UserAgent, Agent)
        .join(Agent, UserAgent.agent_id == Agent.id)
        .join(AgentCategory, Agent.category_id == AgentCategory.id)
        .filter(UserAgent.owner_user_id == user.id, UserAgent.enabled.is_(True))
        .filter(Agent.enabled.is_(True), AgentCategory.enabled.is_(True), Agent.id != DEFAULT_AGENT_ID)
    )
    query = apply_visible_agent_filters(query, user)
    query = apply_agent_search(query, search)
    rows = query.order_by(UserAgent.created_at.desc()).all()

    items: list[UserAgentOut] = []
    default_agent = visible_agents_query(db, user).filter(Agent.id == DEFAULT_AGENT_ID).first()
    if default_agent and agent_matches_search(db, default_agent, search, agent_tags(db, default_agent.id)):
        items.append(
            UserAgentOut(
                **agent_out(db, default_agent, include_prompt=False, added=True).model_dump(),
                added_at=default_agent.created_at.isoformat(),
            )
        )
    items.extend(
        UserAgentOut(
            **agent_out(db, agent, include_prompt=False, added=True).model_dump(),
            added_at=link.created_at.isoformat(),
        )
        for link, agent in rows
    )

    total = len(items)
    offset = (page - 1) * page_size
    return UserAgentPageOut(items=items[offset:offset + page_size], total=total, page=page, page_size=page_size)


def add_user_agent(db: Session, user: User, agent_id: str) -> UserAgentOut:
    ensure_agent_market_defaults(db)
    agent = visible_agents_query(db, user).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在或不可见")

    if agent.id == DEFAULT_AGENT_ID:
        return UserAgentOut(
            **agent_out(db, agent, include_prompt=False, added=True).model_dump(),
            added_at=agent.created_at.isoformat(),
        )

    now = datetime.now(timezone.utc)
    link = db.query(UserAgent).filter(UserAgent.owner_user_id == user.id, UserAgent.agent_id == agent.id).first()
    if link:
        link.enabled = True
        link.updated_at = now
    else:
        link = UserAgent(owner_user_id=user.id, agent_id=agent.id, enabled=True, created_at=now, updated_at=now)
        db.add(link)
    db.commit()
    db.refresh(link)
    return UserAgentOut(
        **agent_out(db, agent, include_prompt=False, added=True).model_dump(),
        added_at=link.created_at.isoformat(),
    )


def remove_user_agent(db: Session, user: User, agent_id: str) -> None:
    if agent_id == DEFAULT_AGENT_ID:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="默认智能体不能移除")
    deleted = (
        db.query(UserAgent)
        .filter(UserAgent.owner_user_id == user.id, UserAgent.agent_id == agent_id)
        .delete(synchronize_session=False)
    )
    if not deleted:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户未添加该智能体")
    db.commit()
