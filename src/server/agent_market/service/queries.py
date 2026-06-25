# -*- coding: utf-8 -*-
"""Query helpers for agent marketplace services."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ..models import Agent, AgentCategory, AgentTag, AgentTagLink, UserAgent
from .constants import DEFAULT_AGENT_ID, SLUG_PATTERN, SortableModel


def visible_agents_query(db: Session, user: User):
    query = (
        db.query(Agent)
        .join(AgentCategory, Agent.category_id == AgentCategory.id)
        .filter(Agent.enabled.is_(True), AgentCategory.enabled.is_(True))
    )
    return apply_visible_agent_filters(query, user)


def apply_visible_agent_filters(query, user: User):
    if user.role == UserRole.ADMIN:
        return query.filter(
            or_(Agent.visibility == "public", Agent.visibility == "admin"),
            or_(AgentCategory.visibility == "public", AgentCategory.visibility == "admin"),
        )
    return query.filter(Agent.visibility == "public", AgentCategory.visibility == "public")


def apply_agent_search(query, search: str | None):
    keyword = (search or "").strip()
    if not keyword:
        return query
    pattern = f"%{keyword}%"
    return (
        query.outerjoin(AgentTagLink, AgentTagLink.agent_id == Agent.id)
        .outerjoin(AgentTag, AgentTag.id == AgentTagLink.tag_id)
        .filter(
            or_(
                Agent.id.ilike(pattern),
                Agent.slug.ilike(pattern),
                Agent.title.ilike(pattern),
                Agent.summary.ilike(pattern),
                Agent.description.ilike(pattern),
                AgentCategory.name.ilike(pattern),
                AgentTag.name.ilike(pattern),
            )
        )
        .distinct()
    )


def get_agent_or_404(db: Session, agent_id: str) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    return agent


def get_category_or_404(db: Session, category_id: str) -> AgentCategory:
    category = db.query(AgentCategory).filter(AgentCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


def get_tag_or_404(db: Session, tag_id: str) -> AgentTag:
    tag = db.query(AgentTag).filter(AgentTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


def get_category_or_400(db: Session, category_id: str, *, require_enabled: bool) -> AgentCategory:
    category = db.query(AgentCategory).filter(AgentCategory.id == category_id).first()
    if not category or (require_enabled and not category.enabled):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择有效的智能体分类")
    return category


def get_tags_or_400(db: Session, tag_ids: list[str], *, require_enabled: bool) -> list[AgentTag]:
    normalized_ids = [normalize_slug(tag_id, "标签 id") for tag_id in dict.fromkeys(tag_ids)]
    if not normalized_ids:
        return []
    query = db.query(AgentTag).filter(AgentTag.id.in_(normalized_ids))
    if require_enabled:
        query = query.filter(AgentTag.enabled.is_(True))
    tags = query.all()
    tags_by_id = {tag.id: tag for tag in tags}
    missing = [tag_id for tag_id in normalized_ids if tag_id not in tags_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"标签不存在或已停用：{', '.join(missing)}")
    return [tags_by_id[tag_id] for tag_id in normalized_ids]


def added_agent_ids(db: Session, user: User) -> set[str]:
    ids = {
        row[0]
        for row in (
            db.query(UserAgent.agent_id)
            .filter(UserAgent.owner_user_id == user.id, UserAgent.enabled.is_(True))
            .all()
        )
    }
    ids.add(DEFAULT_AGENT_ID)
    return ids


def agent_matches_search(db: Session, agent: Agent, search: str | None, tags: list[AgentTag]) -> bool:
    keyword = (search or "").strip().lower()
    if not keyword:
        return True
    category = db.query(AgentCategory).filter(AgentCategory.id == agent.category_id).first()
    values = [
        agent.id,
        agent.slug,
        agent.title,
        agent.summary,
        agent.description,
        category.name if category else agent.category_id,
        *(tag.name for tag in tags),
    ]
    return any(keyword in value.lower() for value in values if value)


def next_sort_order(db: Session, model: type[SortableModel]) -> int:
    current = db.query(model).order_by(model.sort_order.desc()).first()
    return (current.sort_order if current else 0) + 10


def normalize_slug(value: str, field_name: str) -> str:
    slug = value.strip()
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 只能包含字母、数字、下划线或连字符，长度 2-61",
        )
    return slug
