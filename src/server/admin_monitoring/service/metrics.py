# -*- coding: utf-8 -*-
"""Metric helpers for admin monitoring modules."""

from __future__ import annotations

import json
from collections import Counter
from typing import Any, Iterable

from src.server.capability_jobs.config import CAPABILITIES
from src.server.capability_jobs.models import CapabilityJob
from src.server.daily_writer.models import DailyWriterJob

from ..schemas import BreakdownItemOut, MetricCardOut, MonitoringModuleOut, TrendPointOut
from .types import ASSET_LABELS, DateWindow, STATUS_LABELS
from .windowing import count_in_range, date_keys, day_key, in_range, iso, latest


def module_primary_card(module: MonitoringModuleOut) -> MetricCardOut:
    card = module.cards[0]
    return MetricCardOut(
        **card.model_dump(exclude={"title", "description"}),
        title=module.title,
        description=card.title,
    )


def metric(
    key: str,
    title: str,
    total: int | float,
    range_value: int | float = 0,
    today_value: int | float | None = None,
    last_7_days_value: int | float | None = None,
    unit: str = "",
    *,
    extra: dict[str, Any] | None = None,
) -> MetricCardOut:
    return MetricCardOut(
        key=key,
        title=title,
        value=total,
        total=total,
        range_value=range_value,
        today_value=today_value,
        last_7_days_value=last_7_days_value,
        unit=unit,
        extra=extra or {},
    )


def job_cards(
    key: str,
    title: str,
    jobs: list[Any],
    window: DateWindow,
    generated_total: int | None = None,
    generated_title: str | None = None,
) -> list[MetricCardOut]:
    status_counts = Counter(str(job.status) for job in jobs)
    completed = status_counts["completed"]
    failed = status_counts["failed"]
    cards = [
        metric(key, title, len(jobs), count_in_range(jobs, window), unit="个"),
        MetricCardOut(key=f"{key}-completed", title="已完成", value=completed, unit="个"),
        MetricCardOut(key=f"{key}-failed", title="失败", value=failed, unit="个"),
        MetricCardOut(key=f"{key}-success-rate", title="成功率", value=round(success_rate(completed, failed) * 100, 1), unit="%"),
    ]
    if generated_total is not None and generated_title is not None:
        cards.insert(1, MetricCardOut(key=f"{key}-generated", title=generated_title, value=generated_total, unit="条"))
    return cards


def job_rows(jobs: list[Any], *, extra: Any | None = None) -> list[dict[str, Any]]:
    rows = []
    for job in latest(jobs, key=lambda item: item.created_at):
        payload = {
            "id": job.id,
            "status": job.status,
            "owner_user_id": getattr(job, "owner_user_id", None),
            "created_at": iso(job.created_at),
            "started_at": iso(getattr(job, "started_at", None)),
            "finished_at": iso(getattr(job, "finished_at", None)),
        }
        if extra:
            payload.update(extra(job))
        rows.append(payload)
    return rows


def capability_rows(jobs: list[CapabilityJob]) -> list[dict[str, Any]]:
    labels = capability_labels()
    rows = []
    for job in latest(jobs, key=lambda item: item.created_at):
        rows.append({
            "id": job.id,
            "capability_key": job.capability_key,
            "capability_label": labels.get(job.capability_key, job.capability_key),
            "group": capability_group(job.capability_key),
            "status": job.status,
            "owner_user_id": job.owner_user_id,
            "created_at": iso(job.created_at),
            "finished_at": iso(job.finished_at),
        })
    return rows


def job_trend(items: Iterable[Any], window: DateWindow) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in items:
        created_at = getattr(item, "created_at", None)
        if in_range(created_at, window.start_at, window.end_at):
            counter[day_key(created_at, window)] += 1
    return counter


def trend_points(counter: Counter[str], metric_name: str, window: DateWindow) -> list[TrendPointOut]:
    return [TrendPointOut(date=day, metric=metric_name, value=counter.get(day, 0)) for day in date_keys(window)]


def compound_trend_points(counter: Counter[str], window: DateWindow) -> list[TrendPointOut]:
    metrics = sorted({key.split("|", 1)[1] for key in counter if "|" in key})
    points: list[TrendPointOut] = []
    for day in date_keys(window):
        for metric_name in metrics:
            points.append(TrendPointOut(date=day, metric=metric_name, value=counter.get(f"{day}|{metric_name}", 0)))
    return points


def counter_breakdown(counter: Counter[Any], labels: dict[str, str] | None = None) -> list[BreakdownItemOut]:
    label_map = labels or {}
    return [
        BreakdownItemOut(key=str(key), label=label_map.get(str(key), str(key)), value=value)
        for key, value in counter.most_common()
    ]


def status_breakdown(counter: Counter[str]) -> list[BreakdownItemOut]:
    return [
        BreakdownItemOut(key=key, label=STATUS_LABELS.get(key, key), value=counter.get(key, 0))
        for key in ("queued", "running", "completed", "failed")
    ]


def success_breakdown(completed: int, failed: int) -> list[BreakdownItemOut]:
    return [
        BreakdownItemOut(key="completed", label="已完成", value=completed),
        BreakdownItemOut(key="failed", label="失败", value=failed),
        BreakdownItemOut(key="success_rate", label="成功率", value=round(success_rate(completed, failed) * 100, 1)),
    ]


def asset_counts(summary_json: str | None) -> Counter[str]:
    summary = json_dict(summary_json)
    return Counter({key: int_value(summary.get(key), 0) for key in ASSET_LABELS})


def json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def daily_writer_article_count(job: DailyWriterJob) -> int:
    summary = json_dict(job.summary_json)
    if "variant_success_count" in summary:
        return 1 + int_value(summary.get("variant_success_count"), 0)
    params = json_dict(job.params_json)
    if params.get("generate_variants"):
        return 1 + int_value(params.get("variant_count"), 0)
    return 1


def seed_matrix_mode(params: dict[str, Any]) -> str:
    hooks = params.get("hooks")
    seed_count = int_value(params.get("expected_seed_count"), 0)
    slots = int_value(params.get("slots_per_day"), 0)
    if isinstance(hooks, list) and any(str(item).strip() for item in hooks):
        return "Hook 强化矩阵"
    if seed_count >= 50:
        return "批量选题矩阵"
    if slots >= 8:
        return "高频发布矩阵"
    return "标准选题矩阵"


def daily_writer_mode(params: dict[str, Any]) -> str:
    if not params.get("generate_variants"):
        return "单篇长文"
    if int_value(params.get("variant_count"), 0) == 4:
        return "五篇长文套装"
    return "批量长文"


def capability_group(capability_key: str) -> str:
    config = CAPABILITIES.get(capability_key)
    return config.group if config else "unknown"


def capability_labels() -> dict[str, str]:
    return {key: config.nav_label for key, config in CAPABILITIES.items()}


def success_rate(completed: int, failed: int) -> float:
    denominator = completed + failed
    if denominator <= 0:
        return 0.0
    return completed / denominator


def int_value(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
