# -*- coding: utf-8 -*-
"""Shared data types for agent marketplace services."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class AgentPromptContext:
    agent_id: str
    revision_id: str
    name: str
    system_prompt: str
