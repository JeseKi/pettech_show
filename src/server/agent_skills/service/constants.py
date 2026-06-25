# -*- coding: utf-8 -*-
"""Constants for agent skill marketplace services."""

from __future__ import annotations

import re
from typing import TypeVar

from ..models import AgentSkill, AgentSkillCategory, AgentSkillTag

MENTION_PATTERN = re.compile(r"(?<![\w-])@([A-Za-z0-9][A-Za-z0-9_-]{1,60})")
SLUG_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{1,60}$")
SortableModel = TypeVar("SortableModel", AgentSkill, AgentSkillCategory, AgentSkillTag)
