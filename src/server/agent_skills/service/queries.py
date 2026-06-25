# -*- coding: utf-8 -*-
"""Query helpers for agent skill services."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole

from ..models import AgentSkill, AgentSkillCategory, AgentSkillTag, AgentSkillTagLink, UserAgentSkill
from .constants import SLUG_PATTERN, SortableModel


def visible_skills_query(db: Session, user: User):
    return (
        db.query(AgentSkill)
        .join(AgentSkillCategory, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(AgentSkill.enabled.is_(True), AgentSkillCategory.enabled.is_(True))
        .filter(visible_skill_condition(user))
    )


def visible_skill_condition(user: User):
    if user.role == UserRole.ADMIN:
        return or_(AgentSkill.visibility == "public", AgentSkill.visibility == "admin")
    return AgentSkill.visibility == "public"


def apply_skill_search(query, search: str | None):
    keyword = (search or "").strip()
    if not keyword:
        return query
    pattern = f"%{keyword}%"
    return (
        query.outerjoin(AgentSkillTagLink, AgentSkillTagLink.skill_id == AgentSkill.id)
        .outerjoin(AgentSkillTag, AgentSkillTag.id == AgentSkillTagLink.tag_id)
        .filter(
            or_(
                AgentSkill.id.ilike(pattern),
                AgentSkill.slug.ilike(pattern),
                AgentSkill.title.ilike(pattern),
                AgentSkill.summary.ilike(pattern),
                AgentSkill.description.ilike(pattern),
                AgentSkillCategory.name.ilike(pattern),
                AgentSkillTag.name.ilike(pattern),
            )
        )
        .distinct()
    )


def get_skill_or_404(db: Session, skill_id: str) -> AgentSkill:
    skill = db.query(AgentSkill).filter(AgentSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    return skill


def get_category_or_404(db: Session, category_id: str) -> AgentSkillCategory:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


def get_tag_or_404(db: Session, tag_id: str) -> AgentSkillTag:
    tag = db.query(AgentSkillTag).filter(AgentSkillTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


def get_category_or_400(db: Session, category_id: str, *, require_enabled: bool) -> AgentSkillCategory:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first()
    if not category or (require_enabled and not category.enabled):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择有效的系统分类")
    return category


def get_tags_or_400(db: Session, tag_ids: list[str], *, require_enabled: bool) -> list[AgentSkillTag]:
    normalized_ids = [normalize_slug(tag_id, "标签 id") for tag_id in dict.fromkeys(tag_ids)]
    if not normalized_ids:
        return []
    query = db.query(AgentSkillTag).filter(AgentSkillTag.id.in_(normalized_ids))
    if require_enabled:
        query = query.filter(AgentSkillTag.enabled.is_(True))
    tags = query.all()
    tags_by_id = {tag.id: tag for tag in tags}
    missing = [tag_id for tag_id in normalized_ids if tag_id not in tags_by_id]
    if missing:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"标签不存在或已停用：{', '.join(missing)}")
    return [tags_by_id[tag_id] for tag_id in normalized_ids]


def added_skill_ids(db: Session, user: User) -> set[str]:
    return {
        row.skill_id
        for row in db.query(UserAgentSkill.skill_id)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.enabled.is_(True))
        .all()
    }


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
