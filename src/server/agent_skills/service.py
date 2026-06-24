# -*- coding: utf-8 -*-
"""Service layer for file-backed agent skill marketplace with DB indexes."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import shutil
from typing import TypeVar, cast

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config

from .models import AgentSkill, AgentSkillCategory, AgentSkillTag, AgentSkillTagLink, UserAgentSkill
from .schemas import (
    AgentSkillCategoryCreateIn,
    AgentSkillCategoryOut,
    AgentSkillCategoryUpdateIn,
    AgentSkillCreateIn,
    AgentSkillOut,
    AgentSkillPageOut,
    AgentSkillTagCreateIn,
    AgentSkillTagOut,
    AgentSkillTagUpdateIn,
    AgentSkillUpdateIn,
    SkillVisibility,
    UserAgentSkillPageOut,
    UserAgentSkillOut,
)


MENTION_PATTERN = re.compile(r"(?<![\w-])@([A-Za-z0-9][A-Za-z0-9_-]{1,60})")
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$")
SortableModel = TypeVar("SortableModel", AgentSkill, AgentSkillCategory, AgentSkillTag)


def ensure_skill_market_root() -> None:
    _skill_market_root().mkdir(parents=True, exist_ok=True)


def list_market_categories(db: Session, user: User) -> list[AgentSkillCategoryOut]:
    rows = (
        db.query(AgentSkillCategory)
        .join(AgentSkill, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(AgentSkillCategory.enabled.is_(True), AgentSkill.enabled.is_(True))
        .filter(_visible_skill_condition(user))
        .distinct()
        .order_by(AgentSkillCategory.sort_order.asc(), AgentSkillCategory.name.asc())
        .all()
    )
    return [_category_out(row) for row in rows]


def list_market_skills(
    db: Session,
    user: User,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AgentSkillPageOut:
    query = _visible_skills_query(db, user)
    if category:
        query = query.filter(AgentSkill.category_id == category)
    query = _apply_skill_search(query, search)
    total = query.order_by(None).count()
    rows = (
        query.order_by(AgentSkill.sort_order.asc(), AgentSkill.title.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    added_ids = _added_skill_ids(db, user)
    return AgentSkillPageOut(
        items=[_skill_out(db, skill, added=skill.id in added_ids) for skill in rows],
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
        .filter(_visible_skill_condition(user))
    )
    query = _apply_skill_search(query, search)
    total = query.order_by(None).count()
    rows = (
        query
        .order_by(UserAgentSkill.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return UserAgentSkillPageOut(
        items=[
            UserAgentSkillOut(
                **_skill_out(db, skill, added=True).model_dump(),
                added_at=link.created_at.isoformat(),
            )
            for link, skill in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


def add_user_skill(db: Session, user: User, skill_id: str) -> UserAgentSkillOut:
    skill = _visible_skills_query(db, user).filter(AgentSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在或不可见")

    now = datetime.now(timezone.utc)
    link = (
        db.query(UserAgentSkill)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.skill_id == skill.id)
        .first()
    )
    if link:
        link.enabled = True
        link.updated_at = now
    else:
        link = UserAgentSkill(
            owner_user_id=user.id,
            skill_id=skill.id,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(link)
    db.commit()
    db.refresh(link)
    return UserAgentSkillOut(
        **_skill_out(db, skill, added=True).model_dump(),
        added_at=link.created_at.isoformat(),
    )


def remove_user_skill(db: Session, user: User, skill_id: str) -> None:
    deleted = (
        db.query(UserAgentSkill)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.skill_id == skill_id)
        .delete(synchronize_session=False)
    )
    db.commit()
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="用户未添加该 Skill")


def list_admin_categories(db: Session) -> list[AgentSkillCategoryOut]:
    rows = db.query(AgentSkillCategory).order_by(AgentSkillCategory.sort_order.asc(), AgentSkillCategory.name.asc()).all()
    return [_category_out(row) for row in rows]


def create_admin_category(db: Session, payload: AgentSkillCategoryCreateIn) -> AgentSkillCategoryOut:
    category_id = _normalize_slug(payload.id, "分类 id")
    if db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类 id 已存在")

    now = datetime.now(timezone.utc)
    category = AgentSkillCategory(
        id=category_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        sort_order=_next_sort_order(db, AgentSkillCategory),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(category)
    db.commit()
    db.refresh(category)
    return _category_out(category)


def update_admin_category(
    db: Session,
    category_id: str,
    payload: AgentSkillCategoryUpdateIn,
) -> AgentSkillCategoryOut:
    category = _get_category_or_404(db, category_id)
    if payload.name is not None:
        category.name = payload.name.strip()
    if payload.description is not None:
        category.description = payload.description.strip()
    if payload.enabled is not None:
        category.enabled = payload.enabled
    category.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(category)
    return _category_out(category)


def delete_admin_category(db: Session, category_id: str) -> None:
    category = _get_category_or_404(db, category_id)
    used = db.query(AgentSkill).filter(AgentSkill.category_id == category.id).first()
    if used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类正在被 Skill 使用，不能删除")
    db.delete(category)
    db.commit()


def list_admin_tags(db: Session) -> list[AgentSkillTagOut]:
    rows = db.query(AgentSkillTag).order_by(AgentSkillTag.sort_order.asc(), AgentSkillTag.name.asc()).all()
    return [_tag_out(row) for row in rows]


def create_admin_tag(db: Session, payload: AgentSkillTagCreateIn) -> AgentSkillTagOut:
    tag_id = _normalize_slug(payload.id, "标签 id")
    if db.query(AgentSkillTag).filter(AgentSkillTag.id == tag_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签 id 已存在")

    now = datetime.now(timezone.utc)
    tag = AgentSkillTag(
        id=tag_id,
        name=payload.name.strip(),
        sort_order=_next_sort_order(db, AgentSkillTag),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)


def update_admin_tag(db: Session, tag_id: str, payload: AgentSkillTagUpdateIn) -> AgentSkillTagOut:
    tag = _get_tag_or_404(db, tag_id)
    if payload.name is not None:
        tag.name = payload.name.strip()
    if payload.enabled is not None:
        tag.enabled = payload.enabled
    tag.updated_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)


def delete_admin_tag(db: Session, tag_id: str) -> None:
    tag = _get_tag_or_404(db, tag_id)
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.tag_id == tag.id).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()


def list_admin_skills(db: Session) -> list[AgentSkillOut]:
    rows = db.query(AgentSkill).order_by(AgentSkill.sort_order.asc(), AgentSkill.title.asc()).all()
    return [_skill_out(db, skill, added=False) for skill in rows]


def get_admin_skill_detail(db: Session, skill_id: str) -> AgentSkillOut:
    skill = _get_skill_or_404(db, skill_id)
    return _skill_out(db, skill, added=False, include_markdown=True)


def create_admin_skill(db: Session, payload: AgentSkillCreateIn) -> AgentSkillOut:
    skill_id = _normalize_slug(payload.id, "Skill id")
    if db.query(AgentSkill).filter(AgentSkill.id == skill_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill id 已存在")

    directory = _skill_directory(skill_id)
    if directory.exists():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Skill 文件目录已存在")

    category = _get_category_or_400(db, payload.category_id, require_enabled=True)
    tags = _get_tags_or_400(db, payload.tag_ids, require_enabled=True)
    now = datetime.now(timezone.utc)
    skill_markdown = payload.skill_markdown.strip()
    metadata = _build_metadata(
        skill_id=skill_id,
        name=payload.name.strip(),
        description=payload.description.strip(),
        category=category,
        tags=tags,
        visibility=payload.visibility,
        created_at=now.isoformat(),
        updated_at=now.isoformat(),
    )
    paths = _write_skill_files(directory, skill_markdown, metadata)
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
        sort_order=_next_sort_order(db, AgentSkill),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(skill)
    db.flush()
    _replace_skill_tags(db, skill.id, tags)
    db.commit()
    db.refresh(skill)
    return _skill_out(db, skill, added=False)


def update_admin_skill(db: Session, skill_id: str, payload: AgentSkillUpdateIn) -> AgentSkillOut:
    skill = _get_skill_or_404(db, skill_id)
    skill_markdown = payload.skill_markdown.strip() if payload.skill_markdown is not None else _read_skill_markdown(skill)
    name = payload.name.strip() if payload.name is not None else skill.title
    description = payload.description.strip() if payload.description is not None else skill.description
    visibility = payload.visibility if payload.visibility is not None else skill.visibility

    category = _get_category_or_400(
        db,
        payload.category_id if payload.category_id is not None else skill.category_id,
        require_enabled=payload.category_id is not None and payload.category_id != skill.category_id,
    )
    current_tag_ids = _skill_tag_ids(db, skill.id)
    tags = _get_tags_or_400(
        db,
        payload.tag_ids if payload.tag_ids is not None else current_tag_ids,
        require_enabled=payload.tag_ids is not None and payload.tag_ids != current_tag_ids,
    )

    now = datetime.now(timezone.utc)
    metadata = _build_metadata(
        skill_id=skill.id,
        name=name,
        description=description,
        category=category,
        tags=tags,
        visibility=visibility,
        created_at=skill.created_at.isoformat(),
        updated_at=now.isoformat(),
    )
    paths = _write_skill_files(Path(skill.skill_dir), skill_markdown, metadata)
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
        _replace_skill_tags(db, skill.id, tags)
    db.commit()
    db.refresh(skill)
    return _skill_out(db, skill, added=False)


def delete_admin_skill(db: Session, skill_id: str) -> None:
    skill = _get_skill_or_404(db, skill_id)
    directory = Path(skill.skill_dir)
    if directory.exists():
        shutil.rmtree(directory)
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.skill_id == skill.id).delete(synchronize_session=False)
    db.query(UserAgentSkill).filter(UserAgentSkill.skill_id == skill.id).delete(synchronize_session=False)
    db.delete(skill)
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
        .filter(_visible_skill_condition(user))
        .all()
    )
    skills_by_id = {skill.id: skill for skill in rows}
    ordered_skills = [skills_by_id[handle] for handle in handles if handle in skills_by_id]
    if not ordered_skills:
        return ""
    blocks = [
        (
            f'<skill mention="@{skill.id}" title="{skill.title}">\n'
            f"{_read_skill_markdown(skill).strip()}\n"
            "</skill>"
        )
        for skill in ordered_skills
    ]
    return (
        "用户在消息中 @ 了以下已添加到智能体的 Skill。"
        "请把对应 SKILL.md 作为本轮额外工作规范，但不要向用户暴露内部注入细节。\n\n"
        + "\n\n".join(blocks)
    )


def _visible_skills_query(db: Session, user: User):
    return (
        db.query(AgentSkill)
        .join(AgentSkillCategory, AgentSkill.category_id == AgentSkillCategory.id)
        .filter(AgentSkill.enabled.is_(True), AgentSkillCategory.enabled.is_(True))
        .filter(_visible_skill_condition(user))
    )


def _visible_skill_condition(user: User):
    if user.role == UserRole.ADMIN:
        return or_(AgentSkill.visibility == "public", AgentSkill.visibility == "admin")
    return AgentSkill.visibility == "public"


def _apply_skill_search(query, search: str | None):
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


def _get_skill_or_404(db: Session, skill_id: str) -> AgentSkill:
    skill = db.query(AgentSkill).filter(AgentSkill.id == skill_id).first()
    if not skill:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 不存在")
    return skill


def _get_category_or_404(db: Session, category_id: str) -> AgentSkillCategory:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


def _get_tag_or_404(db: Session, tag_id: str) -> AgentSkillTag:
    tag = db.query(AgentSkillTag).filter(AgentSkillTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


def _get_category_or_400(db: Session, category_id: str, *, require_enabled: bool) -> AgentSkillCategory:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == category_id).first()
    if not category or (require_enabled and not category.enabled):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择有效的系统分类")
    return category


def _get_tags_or_400(db: Session, tag_ids: list[str], *, require_enabled: bool) -> list[AgentSkillTag]:
    normalized_ids = [_normalize_slug(tag_id, "标签 id") for tag_id in dict.fromkeys(tag_ids)]
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


def _added_skill_ids(db: Session, user: User) -> set[str]:
    return {
        row.skill_id
        for row in db.query(UserAgentSkill.skill_id)
        .filter(UserAgentSkill.owner_user_id == user.id, UserAgentSkill.enabled.is_(True))
        .all()
    }


def _skill_visibility(value: str) -> SkillVisibility:
    if value in {"public", "admin"}:
        return cast(SkillVisibility, value)
    return "public"


def _skill_out(db: Session, skill: AgentSkill, *, added: bool, include_markdown: bool = False) -> AgentSkillOut:
    category = db.query(AgentSkillCategory).filter(AgentSkillCategory.id == skill.category_id).first()
    tags = _skill_tags(db, skill.id)
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
        visibility=_skill_visibility(skill.visibility),
        summary=skill.summary,
        description=skill.description,
        tags=[tag.name for tag in tags],
        tag_ids=[tag.id for tag in tags],
        added=added,
        skill_markdown=_read_skill_markdown(skill) if include_markdown else None,
    )


def _category_out(category: AgentSkillCategory) -> AgentSkillCategoryOut:
    return AgentSkillCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        sort_order=category.sort_order,
        enabled=category.enabled,
    )


def _tag_out(tag: AgentSkillTag) -> AgentSkillTagOut:
    return AgentSkillTagOut(
        id=tag.id,
        name=tag.name,
        sort_order=tag.sort_order,
        enabled=tag.enabled,
    )


def _read_skill_markdown(skill: AgentSkill) -> str:
    path = Path(skill.skill_path)
    if not path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skill 文件不存在")
    return path.read_text(encoding="utf-8")


def _skill_tags(db: Session, skill_id: str) -> list[AgentSkillTag]:
    return (
        db.query(AgentSkillTag)
        .join(AgentSkillTagLink, AgentSkillTagLink.tag_id == AgentSkillTag.id)
        .filter(AgentSkillTagLink.skill_id == skill_id)
        .order_by(AgentSkillTag.sort_order.asc(), AgentSkillTag.name.asc())
        .all()
    )


def _skill_tag_ids(db: Session, skill_id: str) -> list[str]:
    return [tag.id for tag in _skill_tags(db, skill_id)]


def _replace_skill_tags(db: Session, skill_id: str, tags: list[AgentSkillTag]) -> None:
    db.query(AgentSkillTagLink).filter(AgentSkillTagLink.skill_id == skill_id).delete(synchronize_session=False)
    for tag in tags:
        db.add(AgentSkillTagLink(skill_id=skill_id, tag_id=tag.id))


def _skill_market_root() -> Path:
    return Path(global_config.project_root) / "data" / "skill_market"


def _skill_directory(skill_id: str) -> Path:
    return _skill_market_root() / skill_id


def _write_skill_files(directory: Path, skill_markdown: str, metadata: dict[str, object]) -> dict[str, Path]:
    directory.mkdir(parents=True, exist_ok=True)
    agents_dir = directory / "agents"
    agents_dir.mkdir(parents=True, exist_ok=True)
    skill_path = directory / "SKILL.md"
    metadata_path = agents_dir / "openai.yaml"
    skill_path.write_text(f"{skill_markdown.rstrip()}\n", encoding="utf-8")
    metadata_path.write_text(_dump_generated_yaml(metadata), encoding="utf-8")
    return {"directory": directory, "skill_path": skill_path, "metadata_path": metadata_path}


def _build_metadata(
    *,
    skill_id: str,
    name: str,
    description: str,
    category: AgentSkillCategory,
    tags: list[AgentSkillTag],
    visibility: str,
    created_at: str,
    updated_at: str,
) -> dict[str, object]:
    return {
        "id": skill_id,
        "name": name,
        "description": description,
        "mention": f"@{skill_id}",
        "category": category.id,
        "category_id": category.id,
        "category_label": category.name,
        "visibility": visibility,
        "tag_ids": [tag.id for tag in tags],
        "tags": [tag.name for tag in tags],
        "created_at": created_at,
        "updated_at": updated_at,
        "source": "admin",
        "managed_by": "pettech_show",
    }


def _next_sort_order(db: Session, model: type[SortableModel]) -> int:
    current = db.query(model).order_by(model.sort_order.desc()).first()
    return (current.sort_order if current else 0) + 10


def _normalize_slug(value: str, field_name: str) -> str:
    slug = value.strip()
    if not SLUG_PATTERN.match(slug):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"{field_name} 只能包含字母、数字、下划线或连字符，长度 2-61",
        )
    return slug


def _dump_generated_yaml(metadata: dict[str, object]) -> str:
    lines = ["# This file is generated by pettech_show. Edit through the admin UI."]
    for key, value in metadata.items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {_quote_yaml_scalar(str(item))}")
            continue
        lines.append(f"{key}: {_quote_yaml_scalar(str(value))}")
    return "\n".join(lines) + "\n"


def _quote_yaml_scalar(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
