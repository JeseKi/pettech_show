# -*- coding: utf-8 -*-
"""Serialization helpers for agent marketplace services."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import cast
from uuid import uuid4

from sqlalchemy.orm import Session

from ..models import Agent, AgentCategory, AgentPromptRevision, AgentTag, AgentTagLink
from ..schemas import AgentCategoryOut, AgentOut, AgentPromptRevisionOut, AgentTagOut, AgentVisibility


def agent_out(db: Session, agent: Agent, *, include_prompt: bool, added: bool = False) -> AgentOut:
    category = db.query(AgentCategory).filter(AgentCategory.id == agent.category_id).first()
    tags = agent_tags(db, agent.id)
    revision = current_revision(db, agent)
    category_label = category.name if category else agent.category_id
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.title,
        title=agent.title,
        category=agent.category_id,
        category_id=agent.category_id,
        category_label=category_label,
        visibility=visibility(agent.visibility),
        summary=agent.summary,
        description=agent.description,
        tags=[tag.name for tag in tags],
        tag_ids=[tag.id for tag in tags],
        enabled=agent.enabled,
        is_default=agent.is_default,
        protected=agent.protected,
        added=added,
        current_revision_id=agent.current_revision_id,
        current_version=revision.version if revision else None,
        system_prompt=revision.system_prompt if include_prompt and revision else None,
    )


def category_out(category: AgentCategory) -> AgentCategoryOut:
    return AgentCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        visibility=visibility(category.visibility),
        sort_order=category.sort_order,
        enabled=category.enabled,
    )


def tag_out(tag: AgentTag) -> AgentTagOut:
    return AgentTagOut(
        id=tag.id,
        name=tag.name,
        sort_order=tag.sort_order,
        enabled=tag.enabled,
    )


def revision_out(revision: AgentPromptRevision, *, include_prompt: bool) -> AgentPromptRevisionOut:
    return AgentPromptRevisionOut(
        id=revision.id,
        agent_id=revision.agent_id,
        version=revision.version,
        active=revision.active,
        change_note=revision.change_note,
        created_by_user_id=revision.created_by_user_id,
        created_at=revision.created_at.isoformat(),
        system_prompt=revision.system_prompt if include_prompt else None,
    )


def current_revision(db: Session, agent: Agent) -> AgentPromptRevision | None:
    if agent.current_revision_id:
        revision = (
            db.query(AgentPromptRevision)
            .filter(AgentPromptRevision.id == agent.current_revision_id, AgentPromptRevision.agent_id == agent.id)
            .first()
        )
        if revision:
            return revision
    return (
        db.query(AgentPromptRevision)
        .filter(AgentPromptRevision.agent_id == agent.id, AgentPromptRevision.active.is_(True))
        .order_by(AgentPromptRevision.version.desc())
        .first()
    )


def create_prompt_revision(
    db: Session,
    *,
    agent_id: str,
    system_prompt: str,
    change_note: str,
    created_by_user_id: int | None,
) -> AgentPromptRevision:
    current_max = (
        db.query(AgentPromptRevision.version)
        .filter(AgentPromptRevision.agent_id == agent_id)
        .order_by(AgentPromptRevision.version.desc())
        .first()
    )
    next_version = int(current_max[0] if current_max else 0) + 1
    db.query(AgentPromptRevision).filter(AgentPromptRevision.agent_id == agent_id).update(
        {"active": False},
        synchronize_session=False,
    )
    revision = AgentPromptRevision(
        id=f"apr-{uuid4().hex}",
        agent_id=agent_id,
        version=next_version,
        system_prompt=system_prompt,
        change_note=change_note,
        active=True,
        created_by_user_id=created_by_user_id,
        created_at=datetime.now(timezone.utc),
    )
    db.add(revision)
    db.flush()
    return revision


def agent_tags(db: Session, agent_id: str) -> list[AgentTag]:
    return (
        db.query(AgentTag)
        .join(AgentTagLink, AgentTagLink.tag_id == AgentTag.id)
        .filter(AgentTagLink.agent_id == agent_id)
        .order_by(AgentTag.sort_order.asc(), AgentTag.name.asc())
        .all()
    )


def replace_agent_tags(db: Session, agent_id: str, tags: list[AgentTag]) -> None:
    db.query(AgentTagLink).filter(AgentTagLink.agent_id == agent_id).delete(synchronize_session=False)
    for tag in tags:
        db.add(AgentTagLink(agent_id=agent_id, tag_id=tag.id))


def visibility(value: str) -> AgentVisibility:
    if value in {"public", "admin"}:
        return cast(AgentVisibility, value)
    return "public"
