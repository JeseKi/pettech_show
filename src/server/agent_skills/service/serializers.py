# -*- coding: utf-8 -*-
"""Serialization helpers for agent skills."""

from __future__ import annotations

from typing import cast

from sqlalchemy.orm import Session

from ..models import AgentSkill, AgentSkillCategory, AgentSkillTag, AgentSkillTagLink
from ..schemas import AgentSkillCategoryOut, AgentSkillOut, AgentSkillTagOut, SkillVisibility
from .files import read_skill_markdown


def skill_out(db: Session, skill: AgentSkill, *, added: bool, include_markdown: bool = False) -> AgentSkillOut:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == skill.category_id).first()
    tags = skill_tags(db, skill.id)
    category_label = category.name if category else skill.category_id
    return AgentSkillOut(
        id=skill.id,
        slug=skill.slug,
        mention=f"@{skill.slug}",
        name=skill.title,
        title=skill.title,
        category=skill.category_id,
        category_id=skill.category_id,
        category_label=category_label,
        visibility=skill_visibility(skill.visibility),
        summary=skill.summary,
        description=skill.description,
        tags=[tag.name for tag in tags],
        tag_ids=[tag.id for tag in tags],
        added=added,
        skill_markdown=read_skill_markdown(skill) if include_markdown else None,
    )


def category_out(category: AgentSkillCategory) -> AgentSkillCategoryOut:
    return AgentSkillCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        enabled=category.enabled,
    )


def tag_out(tag: AgentSkillTag) -> AgentSkillTagOut:
    return AgentSkillTagOut(
        id=tag.id,
        name=tag.name,
        sort_order=tag.sort_order,
        enabled=tag.enabled,
    )


def skill_tags(db: Session, skill_id: str) -> list[AgentSkillTag]:
    return (
        db.query(AgentSkillTag)
        .join(AgentSkillTagLink, AgentSkillTagLink.tag_id == AgentSkillTag.id)
        .filter(AgentSkillTagLink.skill_id == skill_id)
        .order_by(AgentSkillTag.sort_order.asc(), AgentSkillTag.name.asc())
        .all()
    )


def skill_tag_ids(db: Session, skill_id: str) -> list[str]:
    return [tag.id for tag in skill_tags(db, skill_id)]


def replace_skill_tags(db: Session, skill_id: str, tags: list[AgentSkillTag]) -> None:
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.skill_id == skill_id).delete(synchronize_session=False)
    for tag in tags:
        db.add(AgentSkillTagLink(skill_id=skill_id, tag_id=tag.id))


def skill_visibility(value: str) -> SkillVisibility:
    if value in {"public", "admin"}:
        return cast(SkillVisibility, value)
    return "public"
