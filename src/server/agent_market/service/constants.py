# -*- coding: utf-8 -*-
"""Constants for agent marketplace services."""

from __future__ import annotations

import re
from typing import TypeVar

from ..models import Agent, AgentCategory, AgentTag

DEFAULT_AGENT_ID = "zhongying-advertising"
DEFAULT_AGENT_REVISION_ID = "apr-zhongying-advertising-v1"
DEFAULT_AGENT_CATEGORY_ID = "staff-agents"
OWNER_AGENT_CATEGORY_ID = "owner-agents"
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$")
SortableModel = TypeVar("SortableModel", Agent, AgentCategory, AgentTag)
