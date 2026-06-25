# -*- coding: utf-8 -*-
"""Service layer for versioned agent marketplace."""

from __future__ import annotations

from .admin import (
    create_admin_agent,
    create_admin_category,
    create_admin_tag,
    delete_admin_agent,
    delete_admin_category,
    delete_admin_tag,
    get_admin_agent_detail,
    list_admin_agent_revisions,
    list_admin_agents,
    list_admin_categories,
    list_admin_tags,
    update_admin_agent,
    update_admin_category,
    update_admin_tag,
)
from .chat import agent_label_for_session, resolve_agent_for_new_chat, resolve_pinned_agent_for_chat
from .defaults import ensure_agent_market_defaults
from .market import (
    add_user_agent,
    get_default_agent,
    list_market_agents,
    list_market_categories,
    list_user_agents,
    remove_user_agent,
)
from .types import AgentPromptContext

__all__ = [
    "AgentPromptContext",
    "add_user_agent",
    "agent_label_for_session",
    "create_admin_agent",
    "create_admin_category",
    "create_admin_tag",
    "delete_admin_agent",
    "delete_admin_category",
    "delete_admin_tag",
    "ensure_agent_market_defaults",
    "get_admin_agent_detail",
    "get_default_agent",
    "list_admin_agent_revisions",
    "list_admin_agents",
    "list_admin_categories",
    "list_admin_tags",
    "list_market_agents",
    "list_market_categories",
    "list_user_agents",
    "remove_user_agent",
    "resolve_agent_for_new_chat",
    "resolve_pinned_agent_for_chat",
    "update_admin_agent",
    "update_admin_category",
    "update_admin_tag",
]
