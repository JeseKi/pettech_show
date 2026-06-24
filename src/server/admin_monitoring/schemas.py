# -*- coding: utf-8 -*-
"""Schemas for admin monitoring dashboards."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class MonitoringRangeOut(BaseModel):
    start_at: datetime
    end_at: datetime
    today_start_at: datetime
    last_7_days_start_at: datetime
    timezone: str


class MetricCardOut(BaseModel):
    key: str
    title: str
    value: int | float
    total: int | float | None = None
    range_value: int | float | None = None
    today_value: int | float | None = None
    last_7_days_value: int | float | None = None
    unit: str = ""
    description: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class TrendPointOut(BaseModel):
    date: str
    metric: str
    value: int | float


class BreakdownItemOut(BaseModel):
    key: str
    label: str
    value: int | float


class MonitoringModuleOut(BaseModel):
    key: str
    title: str
    description: str | None = None
    cards: list[MetricCardOut] = Field(default_factory=list)
    trends: list[TrendPointOut] = Field(default_factory=list)
    breakdowns: dict[str, list[BreakdownItemOut]] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)


class MonitoringOverviewOut(BaseModel):
    range: MonitoringRangeOut
    cards: list[MetricCardOut] = Field(default_factory=list)
    modules: list[MonitoringModuleOut] = Field(default_factory=list)
    trends: list[TrendPointOut] = Field(default_factory=list)


class MonitoringDetailOut(MonitoringModuleOut):
    range: MonitoringRangeOut
