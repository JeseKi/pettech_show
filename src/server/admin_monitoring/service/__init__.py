# -*- coding: utf-8 -*-
"""Service functions for admin monitoring dashboards."""

from __future__ import annotations

from .modules_domain import (
    build_agent_skills_module,
    build_chat_module,
    build_interactive_movie_module,
    build_users_module,
)
from .modules_jobs import (
    build_aiwiki_module,
    build_all_capabilities_module,
    build_capability_group_module,
    build_daily_writer_module,
    build_script_module,
    build_seed_matrix_module,
)
from .overview import build_detail, build_overview
from .types import DateWindow
from .windowing import build_window, window_out

__all__ = [
    "DateWindow",
    "build_agent_skills_module",
    "build_aiwiki_module",
    "build_all_capabilities_module",
    "build_capability_group_module",
    "build_chat_module",
    "build_daily_writer_module",
    "build_detail",
    "build_interactive_movie_module",
    "build_overview",
    "build_script_module",
    "build_seed_matrix_module",
    "build_users_module",
    "build_window",
    "window_out",
]
