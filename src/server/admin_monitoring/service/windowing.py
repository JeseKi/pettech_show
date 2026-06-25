# -*- coding: utf-8 -*-
"""Time-window helpers for admin monitoring."""

from __future__ import annotations

from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from ..schemas import MonitoringRangeOut
from .types import DateWindow


def build_window(
    *,
    start_at: datetime | None,
    end_at: datetime | None,
    tz_name: str,
) -> DateWindow:
    try:
        selected_tz = ZoneInfo(tz_name)
    except ZoneInfoNotFoundError:
        selected_tz = ZoneInfo("Asia/Shanghai")
        tz_name = "Asia/Shanghai"

    now = datetime.now(timezone.utc)
    normalized_end = as_utc(end_at) if end_at else now
    normalized_start = as_utc(start_at) if start_at else normalized_end - timedelta(days=7)
    if normalized_start > normalized_end:
        normalized_start, normalized_end = normalized_end, normalized_start

    local_today = normalized_end.astimezone(selected_tz).date()
    today_start_local = datetime.combine(local_today, time.min, selected_tz)
    return DateWindow(
        start_at=normalized_start,
        end_at=normalized_end,
        today_start_at=today_start_local.astimezone(timezone.utc),
        last_7_days_start_at=normalized_end - timedelta(days=7),
        tz_name=tz_name,
        tz=selected_tz,
    )


def window_out(window: DateWindow) -> MonitoringRangeOut:
    return MonitoringRangeOut(
        start_at=window.start_at,
        end_at=window.end_at,
        today_start_at=window.today_start_at,
        last_7_days_start_at=window.last_7_days_start_at,
        timezone=window.tz_name,
    )


def count_in_range(items: Iterable[Any], window: DateWindow) -> int:
    return sum(1 for item in items if in_range(getattr(item, "created_at", None), window.start_at, window.end_at))


def completed_time(job: Any) -> datetime | None:
    return getattr(job, "finished_at", None) or getattr(job, "created_at", None)


def in_range(value: datetime | None, start_at: datetime, end_at: datetime) -> bool:
    if value is None:
        return False
    normalized = as_utc(value)
    return start_at <= normalized <= end_at


def as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def day_key(value: datetime | None, window: DateWindow) -> str:
    if value is None:
        return ""
    return as_utc(value).astimezone(window.tz).date().isoformat()


def date_keys(window: DateWindow) -> list[str]:
    start_date = window.start_at.astimezone(window.tz).date()
    end_date = window.end_at.astimezone(window.tz).date()
    days = max((end_date - start_date).days, 0)
    return [(start_date + timedelta(days=index)).isoformat() for index in range(days + 1)]


def latest(items: Iterable[Any], *, key: Any, limit: int = 100) -> list[Any]:
    return sorted(items, key=lambda item: key(item) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:limit]


def iso(value: datetime | None) -> str | None:
    return as_utc(value).isoformat() if value else None
