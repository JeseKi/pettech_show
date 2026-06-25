# -*- coding: utf-8 -*-
"""Default agent seeding for the marketplace."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from src.server.config import global_config

from ..models import Agent, AgentCategory, AgentPromptRevision, AgentTag, AgentTagLink
from .constants import (
    DEFAULT_AGENT_CATEGORY_ID,
    DEFAULT_AGENT_ID,
    DEFAULT_AGENT_REVISION_ID,
    OWNER_AGENT_CATEGORY_ID,
)


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
    elif not agent.is_default or not agent.protected or not agent.enabled:
        agent.is_default = True
        agent.protected = True
        agent.enabled = True
        agent.updated_at = now
        changed = True

    db.flush()
    revision = db.query(AgentPromptRevision).filter(AgentPromptRevision.id == DEFAULT_AGENT_REVISION_ID).first()
    if not revision:
        db.add(AgentPromptRevision(
            id=DEFAULT_AGENT_REVISION_ID,
            agent_id=DEFAULT_AGENT_ID,
            version=1,
            system_prompt=_default_agent_prompt(),
            change_note="系统默认版本",
            active=True,
            created_by_user_id=None,
            created_at=now,
        ))
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


def _default_agent_prompt() -> str:
    return (
        global_config.chat_system_prompt.strip()
        or "你是中影广告的互动影游创作助手，擅长把用户想法整理成剧本、分镜、角色、选择节点和可执行的下一步。"
    )
