# -*- coding: utf-8 -*-
"""Service layer for versioned agent marketplace."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import re
from typing import TypeVar, cast
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config

from .models import Agent, AgentCategory, AgentPromptRevision, AgentTag, AgentTagLink, UserAgent
from .schemas import (
    AgentCategoryCreateIn,
    AgentCategoryOut,
    AgentCategoryUpdateIn,
    AgentCreateIn,
    AgentOut,
    AgentPageOut,
    AgentPromptRevisionOut,
    AgentTagCreateIn,
    AgentTagOut,
    AgentTagUpdateIn,
    AgentUpdateIn,
    AgentVisibility,
    UserAgentOut,
    UserAgentPageOut,
)


DEFAULT_AGENT_ID = "zhongying-advertising"
DEFAULT_AGENT_REVISION_ID = "apr-zhongying-advertising-v1"
DEFAULT_AGENT_CATEGORY_ID = "staff-agents"
OWNER_AGENT_CATEGORY_ID = "owner-agents"
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$")
SortableModel = TypeVar("SortableModel", Agent, AgentCategory, AgentTag)


@dataclass(frozen=True)
class AgentPromptContext:
    agent_id: str
    revision_id: str
    name: str
    system_prompt: str


def ensure_agent_market_defaults(db: Session) -> None:
    """Seed the protected default agent and baseline categories if missing."""
    now = datetime.now(timezone.utc)
    changed = False

    staff_category = db.query(AgentCategory).filter(AgentCategory.id == DEFAULT_AGENT_CATEGORY_ID).first()
    if not staff_category:
        staff_category = AgentCategory(
            id=DEFAULT_AGENT_CATEGORY_ID,
            name="员工智能体",
            description="适合宠物企业一线员工、运营和内容团队使用的智能体。",
            visibility="public",
            sort_order=10,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(staff_category)
        changed = True

    owner_category = db.query(AgentCategory).filter(AgentCategory.id == OWNER_AGENT_CATEGORY_ID).first()
    if not owner_category:
        owner_category = AgentCategory(
            id=OWNER_AGENT_CATEGORY_ID,
            name="老板智能体",
            description="仅老板和管理员可见的经营、管理、决策类智能体。",
            visibility="admin",
            sort_order=20,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(owner_category)
        changed = True

    default_tag = db.query(AgentTag).filter(AgentTag.id == "content-creation").first()
    if not default_tag:
        default_tag = AgentTag(
            id="content-creation",
            name="内容创作",
            sort_order=10,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(default_tag)
        changed = True

    agent = db.query(Agent).filter(Agent.id == DEFAULT_AGENT_ID).first()
    if not agent:
        agent = Agent(
            id=DEFAULT_AGENT_ID,
            slug=DEFAULT_AGENT_ID,
            title="中影广告智能体",
            category_id=DEFAULT_AGENT_CATEGORY_ID,
            visibility="public",
            summary="互动影游、宠物企业内容和中影广告工作流的默认智能体。",
            description="擅长把用户想法整理成剧本、分镜、角色、选择节点和可执行的下一步。",
            current_revision_id=DEFAULT_AGENT_REVISION_ID,
            sort_order=10,
            enabled=True,
            is_default=True,
            protected=True,
            created_at=now,
            updated_at=now,
        )
        db.add(agent)
        changed = True
    else:
        if not agent.is_default or not agent.protected or not agent.enabled:
            agent.is_default = True
            agent.protected = True
            agent.enabled = True
            agent.updated_at = now
            changed = True

    db.flush()

    revision = db.query(AgentPromptRevision).filter(AgentPromptRevision.id == DEFAULT_AGENT_REVISION_ID).first()
    if not revision:
        revision = AgentPromptRevision(
            id=DEFAULT_AGENT_REVISION_ID,
            agent_id=DEFAULT_AGENT_ID,
            version=1,
            system_prompt=_default_agent_prompt(),
            change_note="系统默认版本",
            active=True,
            created_by_user_id=None,
            created_at=now,
        )
        db.add(revision)
        agent.current_revision_id = DEFAULT_AGENT_REVISION_ID
        changed = True

    link = (
        db.query(AgentTagLink)
        .filter(AgentTagLink.agent_id == DEFAULT_AGENT_ID, AgentTagLink.tag_id == "content-creation")
        .first()
    )
    if not link:
        db.add(AgentTagLink(agent_id=DEFAULT_AGENT_ID, tag_id="content-creation"))
        changed = True

    if changed:
        db.commit()


def list_market_categories(db: Session, user: User) -> list[AgentCategoryOut]:
    ensure_agent_market_defaults(db)
    query = (
        db.query(AgentCategory)
        .join(Agent, Agent.category_id == AgentCategory.id)
        .filter(AgentCategory.enabled.is_(True), Agent.enabled.is_(True))
    )
    query = _apply_visible_agent_filters(query, user)
    rows = (
        query.distinct()
        .order_by(AgentCategory.sort_order.asc(), AgentCategory.name.asc())
        .all()
    )
    return [_category_out(row) for row in rows]


def list_market_agents(
    db: Session,
    user: User,
    category: str | None = None,
    search: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> AgentPageOut:
    ensure_agent_market_defaults(db)
    query = _visible_agents_query(db, user)
    if category:
        query = query.filter(Agent.category_id == category)
    query = _apply_agent_search(query, search)
    total = query.order_by(None).count()
    rows = (
        query.order_by(Agent.sort_order.asc(), Agent.title.asc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    added_ids = _added_agent_ids(db, user)
    return AgentPageOut(
        items=[_agent_out(db, agent, include_prompt=False, added=agent.id in added_ids) for agent in rows],
        total=total,
        page=page,
        page_size=page_size,
    )


def get_default_agent(db: Session, user: User) -> AgentOut:
    ensure_agent_market_defaults(db)
    agent = _visible_agents_query(db, user).filter(Agent.id == DEFAULT_AGENT_ID).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="默认智能体不可用")
    return _agent_out(db, agent, include_prompt=False, added=True)


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
    query = _apply_visible_agent_filters(query, user)
    query = _apply_agent_search(query, search)
    rows = query.order_by(UserAgent.created_at.desc()).all()

    items: list[UserAgentOut] = []
    default_agent = _visible_agents_query(db, user).filter(Agent.id == DEFAULT_AGENT_ID).first()
    if default_agent and _agent_matches_search(db, default_agent, search):
        items.append(
            UserAgentOut(
                **_agent_out(db, default_agent, include_prompt=False, added=True).model_dump(),
                added_at=default_agent.created_at.isoformat(),
            )
        )
    items.extend(
        UserAgentOut(
            **_agent_out(db, agent, include_prompt=False, added=True).model_dump(),
            added_at=link.created_at.isoformat(),
        )
        for link, agent in rows
    )

    total = len(items)
    offset = (page - 1) * page_size
    return UserAgentPageOut(
        items=items[offset:offset + page_size],
        total=total,
        page=page,
        page_size=page_size,
    )


def add_user_agent(db: Session, user: User, agent_id: str) -> UserAgentOut:
    ensure_agent_market_defaults(db)
    agent = _visible_agents_query(db, user).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在或不可见")

    if agent.id == DEFAULT_AGENT_ID:
        return UserAgentOut(
            **_agent_out(db, agent, include_prompt=False, added=True).model_dump(),
            added_at=agent.created_at.isoformat(),
        )

    now = datetime.now(timezone.utc)
    link = (
        db.query(UserAgent)
        .filter(UserAgent.owner_user_id == user.id, UserAgent.agent_id == agent.id)
        .first()
    )
    if link:
        link.enabled = True
        link.updated_at = now
    else:
        link = UserAgent(
            owner_user_id=user.id,
            agent_id=agent.id,
            enabled=True,
            created_at=now,
            updated_at=now,
        )
        db.add(link)
    db.commit()
    db.refresh(link)
    return UserAgentOut(
        **_agent_out(db, agent, include_prompt=False, added=True).model_dump(),
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


def list_admin_categories(db: Session) -> list[AgentCategoryOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(AgentCategory).order_by(AgentCategory.sort_order.asc(), AgentCategory.name.asc()).all()
    return [_category_out(row) for row in rows]


def create_admin_category(db: Session, payload: AgentCategoryCreateIn) -> AgentCategoryOut:
    category_id = _normalize_slug(payload.id, "分类 id")
    if db.query(AgentCategory).filter(AgentCategory.id == category_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类 id 已存在")
    now = datetime.now(timezone.utc)
    category = AgentCategory(
        id=category_id,
        name=payload.name.strip(),
        description=(payload.description or "").strip(),
        visibility=payload.visibility,
        sort_order=_next_sort_order(db, AgentCategory),
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
    payload: AgentCategoryUpdateIn,
) -> AgentCategoryOut:
    category = _get_category_or_404(db, category_id)
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
    return _category_out(category)


def delete_admin_category(db: Session, category_id: str) -> None:
    category = _get_category_or_404(db, category_id)
    used = db.query(Agent).filter(Agent.category_id == category.id).first()
    if used:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="分类正在被智能体使用，不能删除")
    db.delete(category)
    db.commit()


def list_admin_tags(db: Session) -> list[AgentTagOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(AgentTag).order_by(AgentTag.sort_order.asc(), AgentTag.name.asc()).all()
    return [_tag_out(row) for row in rows]


def create_admin_tag(db: Session, payload: AgentTagCreateIn) -> AgentTagOut:
    tag_id = _normalize_slug(payload.id, "标签 id")
    if db.query(AgentTag).filter(AgentTag.id == tag_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="标签 id 已存在")
    now = datetime.now(timezone.utc)
    tag = AgentTag(
        id=tag_id,
        name=payload.name.strip(),
        sort_order=_next_sort_order(db, AgentTag),
        enabled=True,
        created_at=now,
        updated_at=now,
    )
    db.add(tag)
    db.commit()
    db.refresh(tag)
    return _tag_out(tag)


def update_admin_tag(db: Session, tag_id: str, payload: AgentTagUpdateIn) -> AgentTagOut:
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
    db.query(AgentTagLink).filter(AgentTagLink.tag_id == tag.id).delete(synchronize_session=False)
    db.delete(tag)
    db.commit()


def list_admin_agents(db: Session) -> list[AgentOut]:
    ensure_agent_market_defaults(db)
    rows = db.query(Agent).order_by(Agent.sort_order.asc(), Agent.title.asc()).all()
    return [_agent_out(db, agent, include_prompt=False) for agent in rows]


def get_admin_agent_detail(db: Session, agent_id: str) -> AgentOut:
    ensure_agent_market_defaults(db)
    agent = _get_agent_or_404(db, agent_id)
    return _agent_out(db, agent, include_prompt=True)


def list_admin_agent_revisions(db: Session, agent_id: str) -> list[AgentPromptRevisionOut]:
    ensure_agent_market_defaults(db)
    agent = _get_agent_or_404(db, agent_id)
    rows = (
        db.query(AgentPromptRevision)
        .filter(AgentPromptRevision.agent_id == agent.id)
        .order_by(AgentPromptRevision.version.desc())
        .all()
    )
    return [_revision_out(row, include_prompt=True) for row in rows]


def create_admin_agent(db: Session, payload: AgentCreateIn, user: User | None = None) -> AgentOut:
    agent_id = _normalize_slug(payload.id, "智能体 id")
    if db.query(Agent).filter(Agent.id == agent_id).first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="智能体 id 已存在")
    category = _get_category_or_400(db, payload.category_id, require_enabled=True)
    tags = _get_tags_or_400(db, payload.tag_ids, require_enabled=True)
    now = datetime.now(timezone.utc)
    agent = Agent(
        id=agent_id,
        slug=agent_id,
        title=payload.name.strip(),
        category_id=category.id,
        visibility=payload.visibility,
        summary=payload.description.strip()[:240],
        description=payload.description.strip(),
        sort_order=_next_sort_order(db, Agent),
        enabled=True,
        is_default=False,
        protected=False,
        created_at=now,
        updated_at=now,
    )
    db.add(agent)
    db.flush()
    _replace_agent_tags(db, agent.id, tags)
    revision = _create_prompt_revision(
        db,
        agent_id=agent.id,
        system_prompt=payload.system_prompt.strip(),
        change_note=(payload.change_note or "初始版本").strip(),
        created_by_user_id=user.id if user else None,
    )
    agent.current_revision_id = revision.id
    db.commit()
    db.refresh(agent)
    return _agent_out(db, agent, include_prompt=False)


def update_admin_agent(
    db: Session,
    agent_id: str,
    payload: AgentUpdateIn,
    user: User | None = None,
) -> AgentOut:
    agent = _get_agent_or_404(db, agent_id)
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
        category = _get_category_or_400(db, payload.category_id, require_enabled=payload.category_id != agent.category_id)
        agent.category_id = category.id
    if payload.tag_ids is not None:
        tags = _get_tags_or_400(db, payload.tag_ids, require_enabled=True)
        _replace_agent_tags(db, agent.id, tags)

    if payload.system_prompt is not None:
        revision = _create_prompt_revision(
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
    return _agent_out(db, agent, include_prompt=False)


def delete_admin_agent(db: Session, agent_id: str) -> None:
    agent = _get_agent_or_404(db, agent_id)
    if agent.protected or agent.is_default:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="默认智能体不能删除")
    agent.enabled = False
    agent.updated_at = datetime.now(timezone.utc)
    db.commit()


def resolve_agent_for_new_chat(db: Session, user: User, agent_id: str | None) -> AgentPromptContext:
    ensure_agent_market_defaults(db)
    target_agent_id = (agent_id or DEFAULT_AGENT_ID).strip() or DEFAULT_AGENT_ID
    agent = _visible_agents_query(db, user).filter(Agent.id == target_agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在或不可见")
    revision = _current_revision(db, agent)
    if not revision:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体 Prompt 版本不存在")
    return AgentPromptContext(
        agent_id=agent.id,
        revision_id=revision.id,
        name=agent.title,
        system_prompt=revision.system_prompt,
    )


def resolve_pinned_agent_for_chat(
    db: Session,
    user: User,
    agent_id: str,
    revision_id: str,
) -> AgentPromptContext:
    ensure_agent_market_defaults(db)
    agent = _visible_agents_query(db, user).filter(Agent.id == agent_id).first()
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


def _visible_agents_query(db: Session, user: User):
    query = (
        db.query(Agent)
        .join(AgentCategory, Agent.category_id == AgentCategory.id)
        .filter(Agent.enabled.is_(True), AgentCategory.enabled.is_(True))
    )
    return _apply_visible_agent_filters(query, user)


def _apply_visible_agent_filters(query, user: User):
    if user.role == UserRole.ADMIN:
        return query.filter(
            or_(Agent.visibility == "public", Agent.visibility == "admin"),
            or_(AgentCategory.visibility == "public", AgentCategory.visibility == "admin"),
        )
    return query.filter(Agent.visibility == "public", AgentCategory.visibility == "public")


def _apply_agent_search(query, search: str | None):
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


def _get_agent_or_404(db: Session, agent_id: str) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="智能体不存在")
    return agent


def _get_category_or_404(db: Session, category_id: str) -> AgentCategory:
    category = db.query(AgentCategory).filter(AgentCategory.id == category_id).first()
    if not category:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="分类不存在")
    return category


def _get_tag_or_404(db: Session, tag_id: str) -> AgentTag:
    tag = db.query(AgentTag).filter(AgentTag.id == tag_id).first()
    if not tag:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="标签不存在")
    return tag


def _get_category_or_400(db: Session, category_id: str, *, require_enabled: bool) -> AgentCategory:
    category = db.query(AgentCategory).filter(AgentCategory.id == category_id).first()
    if not category or (require_enabled and not category.enabled):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="请选择有效的智能体分类")
    return category


def _get_tags_or_400(db: Session, tag_ids: list[str], *, require_enabled: bool) -> list[AgentTag]:
    normalized_ids = [_normalize_slug(tag_id, "标签 id") for tag_id in dict.fromkeys(tag_ids)]
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


def _added_agent_ids(db: Session, user: User) -> set[str]:
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


def _agent_matches_search(db: Session, agent: Agent, search: str | None) -> bool:
    keyword = (search or "").strip().lower()
    if not keyword:
        return True
    category = db.query(AgentCategory).filter(AgentCategory.id == agent.category_id).first()
    tags = _agent_tags(db, agent.id)
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


def _agent_out(db: Session, agent: Agent, *, include_prompt: bool, added: bool = False) -> AgentOut:
    category = db.query(AgentCategory).filter(AgentCategory.id == agent.category_id).first()
    tags = _agent_tags(db, agent.id)
    revision = _current_revision(db, agent)
    category_label = category.name if category else agent.category_id
    return AgentOut(
        id=agent.id,
        slug=agent.slug,
        name=agent.title,
        title=agent.title,
        category=agent.category_id,
        category_id=agent.category_id,
        category_label=category_label,
        visibility=_visibility(agent.visibility),
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


def _category_out(category: AgentCategory) -> AgentCategoryOut:
    return AgentCategoryOut(
        id=category.id,
        name=category.name,
        description=category.description,
        visibility=_visibility(category.visibility),
        sort_order=category.sort_order,
        enabled=category.enabled,
    )


def _tag_out(tag: AgentTag) -> AgentTagOut:
    return AgentTagOut(
        id=tag.id,
        name=tag.name,
        sort_order=tag.sort_order,
        enabled=tag.enabled,
    )


def _revision_out(revision: AgentPromptRevision, *, include_prompt: bool) -> AgentPromptRevisionOut:
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


def _current_revision(db: Session, agent: Agent) -> AgentPromptRevision | None:
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


def _create_prompt_revision(
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


def _agent_tags(db: Session, agent_id: str) -> list[AgentTag]:
    return (
        db.query(AgentTag)
        .join(AgentTagLink, AgentTagLink.tag_id == AgentTag.id)
        .filter(AgentTagLink.agent_id == agent_id)
        .order_by(AgentTag.sort_order.asc(), AgentTag.name.asc())
        .all()
    )


def _replace_agent_tags(db: Session, agent_id: str, tags: list[AgentTag]) -> None:
    db.query(AgentTagLink).filter(AgentTagLink.agent_id == agent_id).delete(synchronize_session=False)
    for tag in tags:
        db.add(AgentTagLink(agent_id=agent_id, tag_id=tag.id))


def _visibility(value: str) -> AgentVisibility:
    if value in {"public", "admin"}:
        return cast(AgentVisibility, value)
    return "public"


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


def _default_agent_prompt() -> str:
    return (
        global_config.chat_system_prompt.strip()
        or "你是中影广告的互动影游创作助手，擅长把用户想法整理成剧本、分镜、角色、选择节点和可执行的下一步。"
    )
