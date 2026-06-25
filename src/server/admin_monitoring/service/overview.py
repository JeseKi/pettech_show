# -*- coding: utf-8 -*-
"""Overview and detail entry points for admin monitoring."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from ..schemas import MonitoringDetailOut, MonitoringOverviewOut, TrendPointOut
from .metrics import module_primary_card
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
from .windowing import build_window, window_out


def build_overview(
    db: Session,
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    tz: str,
) -> MonitoringOverviewOut:
    window = build_window(start_at=start_at, end_at=end_at, tz_name=tz)
    modules = [
        build_aiwiki_module(db, window),
        build_seed_matrix_module(db, window),
        build_daily_writer_module(db, window),
        build_script_module(db, window),
        build_capability_group_module(db, window, "competitor-insights"),
        build_capability_group_module(db, window, "topic-planning"),
        build_agent_skills_module(db, window),
        build_interactive_movie_module(db, window),
        build_users_module(db, window),
        build_chat_module(db, window),
    ]
    cards = [module_primary_card(module) for module in modules if module.cards]
    trends: list[TrendPointOut] = []
    for module in modules:
        trends.extend(module.trends[:60])
    return MonitoringOverviewOut(range=window_out(window), cards=cards, modules=modules, trends=trends)


def build_detail(
    db: Session,
    *,
    module_key: str,
    start_at: datetime | None,
    end_at: datetime | None,
    tz: str,
) -> MonitoringDetailOut:
    window = build_window(start_at=start_at, end_at=end_at, tz_name=tz)
    builders = {
        "aiwiki": build_aiwiki_module,
        "seed-matrix": build_seed_matrix_module,
        "daily-writer": build_daily_writer_module,
        "scripts": build_script_module,
        "agent-skills": build_agent_skills_module,
        "interactive-movie": build_interactive_movie_module,
        "users": build_users_module,
        "chat": build_chat_module,
    }
    if module_key == "capabilities":
        module = build_all_capabilities_module(db, window)
    else:
        module = builders[module_key](db, window)
    return MonitoringDetailOut(**module.model_dump(), range=window_out(window))
