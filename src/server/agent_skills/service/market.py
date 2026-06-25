# -*- coding: utf-8 -*-
"""Public and user skill marketplace services."""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import AgentSkill, AgentSkillCategory, AgentSkillUsageEvent, UserAgentSkill
from ..schemas import (
    AgentSkillCategoryOut,
    AgentSkillPageOut,
    UserAgentSkillOut,
    UserAgentSkillPageOut,
)
from .constants import MENTION_PATTERN
from .files import read_skill_markdown
from .queries import added_skill_ids, apply_skill_search, visible_skill_condition, visible_skills_query
from .serializers import category_out, skill_out


def list_market_categories(db: Session, user: User) -> list[AgentSkillCategoryOut]:
    rows = (
        db.query(AgentSkillCategory)
        .join(AgentSkill, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(AgentSkillCategory.enabled.is_(True), AgentSkill.enabled.is_(True))
        .filter(visible_skill_condition(user))
        .distinct()
        .order_by(AgentSkillCategory.sort_order.asc(), AgentSkillCategory.name.asc())
        .all()
    )
    return [category_out(row) for row in rows]


def list_market_skills(
    db: Session,
    user: User,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AgentSkillPageOut:
    query = visible_skills_query(db, user)
    if category:
        query = query.filter(AgentSkill.category_id == category)
    query = apply_skill_search(query, search)
    total = query.order_by(None).count()
    rows = (
        query.order_by(AgentSkill.sort_order.asc(), AgentSkill.title.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    added_ids = added_skill_ids(db, user)
    return AgentSkillPageOut(
        items=[skill_out(db, skill, added=skill.id in added_ids) for skill in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def list_user_skills(
    db: Session,
    user: User,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> UserAgentSkillPageOut:
    query = (
        db.query(UserAgentSkill, AgentSkill)
        .join(AgentSkill, UserAgentSkill.skill_id == AgentSkill.id)
        .join(AgentSkillCategory, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.enabled.is_(True))
        .filter(AgentSkill.enabled.is_(True), AgentSkillCategory.enabled.is_(True))
        .filter(visible_skill_condition(user))
    )
    query = apply_skill_search(query, search)
    total = query.order_by(None).count()
    rows = query.order_by(UserAgentSkill.created_at.desc()).offset((page - 1) * page_size).limit(page_size).all()
    return UserAgentSkillPageOut(
        items=[
            UserAgentSkillOut(
                **skill_out(db, skill, added=True).model_dump(),
                added_at=link.created_at.isoformat(),
            )
            for link, skill in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def add_user_skill(db: Session, user: User, skill_id: str) -> UserAgentSkillOut:
    skill = visible_skills_query(db, user).filter(AgentSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在或不可见")

    now = datetime.now(timezone.utc)
    link = db.query(UserAgentSkill).filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.skill_id == skill.id).first()
    should_log_event = link is None or not link.enabled
    if link:
        link.enabled = True
        link.updated_at = now
    else:
        link = UserAgentSkill(owner_user_id=user.id, skill_id=skill.id, enabled=True, created_at=now, updated_at=now)
        db.add(link)
    if should_log_event:
        db.add(AgentSkillUsageEvent(owner_user_id=user.id, skill_id=skill.id, action="add", created_at=now))
    db.commit()
    db.refresh(link)
    return UserAgentSkillOut(
        **skill_out(db, skill, added=True).model_dump(),
        added_at=link.created_at.isoformat(),
    )


def remove_user_skill(db: Session, user: User, skill_id: str) -> None:
    now = datetime.now(timezone.utc)
    deleted = (
        db.query(UserAgentSkill)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.skill_id == skill_id)
        .delete(synchronize_session=False)
    )
    if not deleted:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户未添加该 Skill")
    db.add(AgentSkillUsageEvent(owner_user_id=user.id, skill_id=skill_id, action="remove", created_at=now))
    db.commit()


def build_mentioned_skill_context(db: Session, user: User, text: str) -> str:
    handles = list(dict.fromkeys(MENTION_PATTERN.findall(text)))
    if not handles:
        return ""
    rows = (
        db.query(AgentSkill)
        .join(UserAgentSkill, UserAgentSkill.skill_id == AgentSkill.id)
        .join(AgentSkillCategory, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.enabled.is_(True))
        .filter(AgentSkill.enabled.is_(True), AgentSkillCategory.enabled.is_(True), AgentSkill.id.in_(handles))
        .filter(visible_skill_condition(user))
        .all()
    )
    skills_by_id = {skill.id: skill for skill in rows}
    ordered_skills = [skills_by_id[handle] for handle in handles if handle in skills_by_id]
    if not ordered_skills:
        return ""
    blocks = [
        (
            f'<skill mention="@{skill.id}" title="{skill.title}">\n'
            f"{read_skill_markdown(skill).strip()}\n"
            "</skill>"
        )
        for skill in ordered_skills
    ]
    return (
        "用户在消息中 @ 了以下已添加到智能体的 Skill。"
        "请把对应 SKILL.md 作为本轮额外工作规范，但不要向用户暴露内部注入细节。\n\n"
        + "\n\n".join(blocks)
    )
