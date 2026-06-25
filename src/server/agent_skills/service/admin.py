# -*- coding: utf-8 -*-
"""Admin services for agent skill marketplace management."""

from __future__ import annotations

import shutil
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import AgentSkill, AgentSkillCategory, AgentSkillTag, AgentSkillTagLink, UserAgentSkill
from ..schemas import (
    AgentSkillCategoryCreateIn,
    AgentSkillCategoryOut,
    AgentSkillCategoryUpdateIn,
    AgentSkillCreateIn,
    AgentSkillOut,
    AgentSkillTagCreateIn,
    AgentSkillTagOut,
    AgentSkillTagUpdateIn,
    AgentSkillUpdateIn,
)
from .files import build_metadata, read_skill_markdown, skill_directory, write_skill_files
from .queries import (
    get_category_or_400,
    get_category_or_404,
    get_skill_or_404,
    get_tag_or_404,
    get_tags_or_400,
    next_sort_order,
    normalize_slug,
)
from .serializers import category_out, replace_skill_tags, skill_out, skill_tag_ids, tag_out


def list_admin_categories(db: Session) -> list[AgentSkillCategoryOut]:
    rows = db.query(AgentSkillCategory).order_by(AgentSkillCategory.sort_order.asc(), AgentSkillCategory.name.asc()).all()
    return [category_out(row) for row in rows]


def create_admin_category(db: Session, payload: AgentSkillCategoryCreateIn) -> AgentSkillCategoryOut:
    category_id = normalize_slug(payload.id, "分类 id")
    if db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类 id 已存在")
    now = datetime.now(timezone.utc)
    category = AgentSkillCategory(
        id=category_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        sort_order=next_sort_order(db, AgentSkillCategory),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return category_out(category)


def update_admin_category(db: Session, category_id: str, payload: AgentSkillCategoryUpdateIn) -> AgentSkillCategoryOut:
    category = get_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.description is not None:
        category.description = payload.description.strip()
    if payload.enabled is not None:
        category.enabled = payload.enabled
    category.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(category)
    return category_out(category)


def delete_admin_category(db: Session, category_id: str) -> None:
    category = get_category_or_404(db, category_id)
    used = db.query(AgentSkill).filter(AgentSkill.category_id == category.id).first()
    if used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类正在被 Skill 使用，不能删除")
    db.delete(category)
    db.commit()


def list_admin_tags(db: Session) -> list[AgentSkillTagOut]:
    rows = db.query(AgentSkillTag).order_by(AgentSkillTag.sort_order.asc(), AgentSkillTag.name.asc()).all()
    return [tag_out(row) for row in rows]


def create_admin_tag(db: Session, payload: AgentSkillTagCreateIn) -> AgentSkillTagOut:
    tag_id = normalize_slug(payload.id, "标签 id")
    if db.query(AgentSkillTag).filter(AgentSkillTag.id == tag_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签 id 已存在")
    now = datetime.now(timezone.utc)
    tag = AgentSkillTag(id=tag_id, name=payload.name.strip(), sort_order=next_sort_order(db, AgentSkillTag), enabled=True, created_at=now, updated_at=now)
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return tag_out(tag)


def update_admin_tag(db: Session, tag_id: str, payload: AgentSkillTagUpdateIn) -> AgentSkillTagOut:
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
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.tag_id == tag.id).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()


def list_admin_skills(db: Session) -> list[AgentSkillOut]:
    rows = db.query(AgentSkill).order_by(AgentSkill.sort_order.asc(), AgentSkill.title.asc()).all()
    return [skill_out(db, skill, added=False) for skill in rows]


def get_admin_skill_detail(db: Session, skill_id: str) -> AgentSkillOut:
    return skill_out(db, get_skill_or_404(db, skill_id), added=False, include_markdown=True)


def create_admin_skill(db: Session, payload: AgentSkillCreateIn) -> AgentSkillOut:
    skill_id = normalize_slug(payload.id, "Skill id")
    if db.query(AgentSkill).filter(AgentSkill.id == skill_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill id 已存在")
    directory = skill_directory(skill_id)
    if directory.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill 文件目录已存在")
    category = get_category_or_400(db, payload.category_id, require_enabled=True)
    tags = get_tags_or_400(db, payload.tag_ids, require_enabled=True)
    now = datetime.now(timezone.utc)
    metadata = build_metadata(
        skill_id=skill_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        category=category,
        tags=tags,
        visibility=payload.visibility,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    paths = write_skill_files(directory, payload.skill_markdown.strip(), metadata)
    skill = AgentSkill(
        id=skill_id,
        slug=skill_id,
        title=str(metadata["name"]),
        category_id=category.id,
        visibility=payload.visibility,
        summary=str(metadata["description"])[:240],
        description=str(metadata["description"]),
        skill_dir=str(paths["directory"]),
        skill_path=str(paths["skill_path"]),
        metadata_path=str(paths["metadata_path"]),
        sort_order=next_sort_order(db, AgentSkill),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    replace_skill_tags(db, skill.id, tags)
    db.commit()
    db.refresh(skill)
    return skill_out(db, skill, added=False)


def update_admin_skill(db: Session, skill_id: str, payload: AgentSkillUpdateIn) -> AgentSkillOut:
    skill = get_skill_or_404(db, skill_id)
    skill_markdown = payload.skill_markdown.strip() if payload.skill_markdown is not None else read_skill_markdown(skill)
    name = payload.name.strip() if payload.name is not None else skill.title
    description = payload.description.strip() if payload.description is not None else skill.description
    visibility = payload.visibility if payload.visibility is not None else skill.visibility
    category = get_category_or_400(
        db,
        payload.category_id if payload.category_id is not None else skill.category_id,
        require_enabled=payload.category_id is not None and payload.category_id != skill.category_id,
    )
    current_tag_ids = skill_tag_ids(db, skill.id)
    tags = get_tags_or_400(
        db,
        payload.tag_ids if payload.tag_ids is not None else current_tag_ids,
        require_enabled=payload.tag_ids is not None and payload.tag_ids != current_tag_ids,
    )
    now = datetime.now(timezone.utc)
    metadata = build_metadata(
        skill_id=skill.id,
        name=name,
        description=description,
        category=category,
        tags=tags,
        visibility=visibility,
        created_at=skill.created_at.isoformat(),
        updated_at=now.isoformat(),
    )
    paths = write_skill_files(Path(skill.skill_dir), skill_markdown, metadata)
    skill.slug = skill.id
    skill.title = str(metadata["name"])
    skill.category_id = category.id
    skill.visibility = visibility
    skill.summary = str(metadata["description"])[:240]
    skill.description = str(metadata["description"])
    skill.skill_dir = str(paths["directory"])
    skill.skill_path = str(paths["skill_path"])
    skill.metadata_path = str(paths["metadata_path"])
    skill.enabled = True
    skill.updated_at = now
    if payload.tag_ids is not None:
        replace_skill_tags(db, skill.id, tags)
    db.commit()
    db.refresh(skill)
    return skill_out(db, skill, added=False)


def delete_admin_skill(db: Session, skill_id: str) -> None:
    skill = get_skill_or_404(db, skill_id)
    directory = Path(skill.skill_dir)
    if directory.exists():
        shutil.rmtree(directory)
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.skill_id == skill.id).delete(synchronize_session=False)
    db.query(UserAgentSkill).filter(UserAgentSkill.skill_id == skill.id).delete(synchronize_session=False)
    db.delete(skill)
    db.commit()
