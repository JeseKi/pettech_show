# -*- coding: utf-8 -*-
"""Admin services for agent marketplace management."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import Agent, AgentCategory, AgentPromptRevision, AgentTag, AgentTagLink
from ..schemas import (
    AgentCategoryCreateIn,
    AgentCategoryOut,
    AgentCategoryUpdateIn,
    AgentCreateIn,
    AgentOut,
    AgentPromptRevisionOut,
    AgentTagCreateIn,
    AgentTagOut,
    AgentTagUpdateIn,
    AgentUpdateIn,
)
from .defaults import ensure_agent_market_defaults
from .queries import (
    get_agent_or_404,
    get_category_or_400,
    get_category_or_404,
    get_tag_or_404,
    get_tags_or_400,
    next_sort_order,
    normalize_slug,
)
from .serializers import (
    agent_out,
    category_out,
    create_prompt_revision,
    replace_agent_tags,
    revision_out,
    tag_out,
)


def list_admin_categories(db: Session) -> list[AgentCategoryOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(AgentCategory).order_by(AgentCategory.sort_order.asc(), AgentCategory.name.asc()).all()
    return [category_out(row) for row in rows]


def create_admin_category(db: Session, payload: AgentCategoryCreateIn) -> AgentCategoryOut:
    category_id = normalize_slug(payload.id, "分类 id")
    if db.query(AgentCategory).filter(AgentCategory.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类 id 已存在")
    now = datetime.now(timezone.utc)
    category = AgentCategory(
        id=category_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        visibility=payload.visibility,
        sort_order=next_sort_order(db, AgentCategory),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category_out(category)


def update_admin_category(db: Session, category_id: str, payload: AgentCategoryUpdateIn) -> AgentCategoryOut:
    category = get_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.description is not None:
        category.description = payload.description.strip()
    if payload.visibility is not None:
        category.visibility = payload.visibility
    if payload.enabled is not None:
        category.enabled = payload.enabled
    category.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(category)
    return category_out(category)


def delete_admin_category(db: Session, category_id: str) -> None:
    category = get_category_or_404(db, category_id)
    used = db.query(Agent).filter(Agent.category_id == category.id).first()
    if used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类正在被智能体使用，不能删除")
    db.delete(category)
    db.commit()


def list_admin_tags(db: Session) -> list[AgentTagOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(AgentTag).order_by(AgentTag.sort_order.asc(), AgentTag.name.asc()).all()
    return [tag_out(row) for row in rows]


def create_admin_tag(db: Session, payload: AgentTagCreateIn) -> AgentTagOut:
    tag_id = normalize_slug(payload.id, "标签 id")
    if db.query(AgentTag).filter(AgentTag.id == tag_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签 id 已存在")
    now = datetime.now(timezone.utc)
    tag = AgentTag(id=tag_id, name=payload.name.strip(), sort_order=next_sort_order(db, AgentTag), enabled=True, created_at=now, updated_at=now)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag_out(tag)


def update_admin_tag(db: Session, tag_id: str, payload: AgentTagUpdateIn) -> AgentTagOut:
    tag = get_tag_or_404(db, tag_id)
    if payload.name is not None:
        tag.name = payload.name.strip()
    if payload.enabled is not None:
        tag.enabled = payload.enabled
    tag.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tag)
    return tag_out(tag)


def delete_admin_tag(db: Session, tag_id: str) -> None:
    tag = get_tag_or_404(db, tag_id)
    db.query(AgentTagLink).filter(AgentTagLink.tag_id == tag.id).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()


def list_admin_agents(db: Session) -> list[AgentOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(Agent).order_by(Agent.sort_order.asc(), Agent.title.asc()).all()
    return [agent_out(db, agent, include_prompt=False) for agent in rows]


def get_admin_agent_detail(db: Session, agent_id: str) -> AgentOut:
    ensure_agent_market_defaults(db)
    return agent_out(db, get_agent_or_404(db, agent_id), include_prompt=True)


def list_admin_agent_revisions(db: Session, agent_id: str) -> list[AgentPromptRevisionOut]:
    ensure_agent_market_defaults(db)
    agent = get_agent_or_404(db, agent_id)
    rows = (
        db.query(AgentPromptRevision)
        .filter(AgentPromptRevision.agent_id == agent.id)
        .order_by(AgentPromptRevision.version.desc())
        .all()
    )
    return [revision_out(row, include_prompt=True) for row in rows]


def create_admin_agent(db: Session, payload: AgentCreateIn, user: User | None = None) -> AgentOut:
    agent_id = normalize_slug(payload.id, "智能体 id")
    if db.query(Agent).filter(Agent.id == agent_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="智能体 id 已存在")
    category = get_category_or_400(db, payload.category_id, require_enabled=True)
    tags = get_tags_or_400(db, payload.tag_ids, require_enabled=True)
    now = datetime.now(timezone.utc)
    agent = Agent(
        id=agent_id,
        slug=agent_id,
        title=payload.name.strip(),
        category_id=category.id,
        visibility=payload.visibility,
        summary=payload.description.strip()[:240],
        description=payload.description.strip(),
        sort_order=next_sort_order(db, Agent),
        enabled=True,
        is_default=False,
        protected=False,
        created_at=now,
        updated_at=now,
    )
    db.add(agent)
    db.flush()
    replace_agent_tags(db, agent.id, tags)
    revision = create_prompt_revision(
        db,
        agent_id=agent.id,
        system_prompt=payload.system_prompt.strip(),
        change_note=(payload.change_note or "初始版本").strip(),
        created_by_user_id=user.id if user else None,
    )
    agent.current_revision_id = revision.id
    db.commit()
    db.refresh(agent)
    return agent_out(db, agent, include_prompt=False)


def update_admin_agent(db: Session, agent_id: str, payload: AgentUpdateIn, user: User | None = None) -> AgentOut:
    agent = get_agent_or_404(db, agent_id)
    if agent.protected and payload.enabled is False:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="默认智能体不能停用")
    if payload.name is not None:
        agent.title = payload.name.strip()
    if payload.description is not None:
        agent.summary = payload.description.strip()[:240]
        agent.description = payload.description.strip()
    if payload.visibility is not None:
        agent.visibility = payload.visibility
    if payload.enabled is not None:
        agent.enabled = payload.enabled
    if payload.category_id is not None:
        category = get_category_or_400(db, payload.category_id, require_enabled=payload.category_id != agent.category_id)
        agent.category_id = category.id
    if payload.tag_ids is not None:
        replace_agent_tags(db, agent.id, get_tags_or_400(db, payload.tag_ids, require_enabled=True))
    if payload.system_prompt is not None:
        revision = create_prompt_revision(
            db,
            agent_id=agent.id,
            system_prompt=payload.system_prompt.strip(),
            change_note=(payload.change_note or "管理员更新").strip(),
            created_by_user_id=user.id if user else None,
        )
        agent.current_revision_id = revision.id
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(agent)
    return agent_out(db, agent, include_prompt=False)


def delete_admin_agent(db: Session, agent_id: str) -> None:
    agent = get_agent_or_404(db, agent_id)
    if agent.protected or agent.is_default:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="默认智能体不能删除")
    agent.enabled = False
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()
