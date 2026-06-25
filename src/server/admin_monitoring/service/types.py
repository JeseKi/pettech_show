# -*- coding: utf-8 -*-
"""Shared types and labels for admin monitoring services."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

STATUS_LABELS = {
    "queued": "排队中",
    "running": "运行中",
    "completed": "已完成",
    "failed": "失败",
}

ASSET_LABELS = {
    "material_count": "素材",
    "wiki_entry_count": "词条",
    "search_intent_count": "关键词/搜索入口",
    "topic_count": "选题",
}

CAPABILITY_GROUP_LABELS = {
    "competitor-insights": "竞品洞察",
    "topic-planning": "选题策划",
    "script-creation": "脚本创作",
}


@dataclass(frozen=True)
class DateWindow:
    start_at: datetime
    end_at: datetime
    today_start_at: datetime
    last_7_days_start_at: datetime
    tz_name: str
    tz: ZoneInfo
