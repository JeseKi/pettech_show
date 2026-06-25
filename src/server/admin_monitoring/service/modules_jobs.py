# -*- coding: utf-8 -*-
"""Monitoring modules for generated jobs and capabilities."""

from __future__ import annotations

from collections import Counter
from typing import Any

from sqlalchemy.orm import Session

from src.server.aiwiki.models import AiwikiJob
from src.server.capability_jobs.config import CAPABILITIES
from src.server.capability_jobs.models import CapabilityJob
from src.server.daily_writer.models import DailyWriterJob
from src.server.seed_matrix.models import SeedMatrixJob

from ..schemas import BreakdownItemOut, MonitoringModuleOut
from .metrics import (
    asset_counts,
    capability_group,
    capability_labels,
    capability_rows,
    counter_breakdown,
    daily_writer_article_count,
    daily_writer_mode,
    int_value,
    job_cards,
    job_rows,
    job_trend,
    json_dict,
    metric,
    seed_matrix_mode,
    status_breakdown,
    success_breakdown,
    trend_points,
)
from .types import ASSET_LABELS, CAPABILITY_GROUP_LABELS, DateWindow
from .windowing import completed_time, count_in_range, day_key, in_range, iso, latest


def build_aiwiki_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(AiwikiJob).all()
    completed = [job for job in jobs if job.status == "completed"]
    asset_totals = Counter[str]()
    range_assets = today_assets = last_7_assets = 0
    trend_counter: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    status_counts = Counter(str(job.status) for job in jobs)

    for job in completed:
        counts = asset_counts(job.summary_json)
        asset_total = sum(counts.values())
        asset_totals.update(counts)
        event_time = completed_time(job)
        if in_range(event_time, window.start_at, window.end_at):
            range_assets += asset_total
            trend_counter[day_key(event_time, window)] += asset_total
        if in_range(event_time, window.today_start_at, window.end_at):
            today_assets += asset_total
        if in_range(event_time, window.last_7_days_start_at, window.end_at):
            last_7_assets += asset_total

    for job in latest(jobs, key=lambda item: item.created_at):
        counts = asset_counts(job.summary_json)
        rows.append({
            "id": job.id,
            "title": job.title,
            "status": job.status,
            "owner_user_id": job.owner_user_id,
            "asset_count": sum(counts.values()),
            "created_at": iso(job.created_at),
            "finished_at": iso(job.finished_at),
        })

    total_assets = sum(asset_totals.values())
    return MonitoringModuleOut(
        key="aiwiki",
        title="数据资产",
        description="AI Wiki 已完成任务沉淀的结构化资产。",
        cards=[
            metric("data-assets", "结构化资产累计", total_assets, range_assets, today_assets, last_7_assets, "条"),
            metric("aiwiki-jobs", "AI Wiki 任务", len(jobs), count_in_range(jobs, window), unit="个"),
            metric("aiwiki-completed", "已完成任务", len(completed), count_in_range(completed, window), unit="个"),
        ],
        trends=trend_points(trend_counter, "数据资产新增", window),
        breakdowns={
            "asset_types": [BreakdownItemOut(key=key, label=ASSET_LABELS[key], value=asset_totals[key]) for key in ASSET_LABELS],
            "status": status_breakdown(status_counts),
        },
        rows=rows,
    )


def build_seed_matrix_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(SeedMatrixJob).all()
    status_counts = Counter(str(job.status) for job in jobs)
    mode_counts = Counter(seed_matrix_mode(json_dict(job.params_json)) for job in jobs)
    total_generated = sum(int_value(json_dict(job.summary_json).get("seed_count"), 0) for job in jobs if job.status == "completed")
    return MonitoringModuleOut(
        key="seed-matrix",
        title="选题生成",
        description="标准、批量、高频和 Hook 选题矩阵生成情况。",
        cards=job_cards("seed-matrix", "选题矩阵任务", jobs, window, total_generated, "选题生成数"),
        trends=trend_points(job_trend(jobs, window), "选题矩阵任务", window),
        breakdowns={
            "status": status_breakdown(status_counts),
            "modes": counter_breakdown(mode_counts),
            "success": success_breakdown(status_counts["completed"], status_counts["failed"]),
        },
        rows=job_rows(jobs, extra=lambda job: {"mode": seed_matrix_mode(json_dict(job.params_json))}),
    )


def build_daily_writer_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(DailyWriterJob).all()
    status_counts = Counter(str(job.status) for job in jobs)
    mode_counts = Counter(daily_writer_mode(json_dict(job.params_json)) for job in jobs)
    article_count = sum(daily_writer_article_count(job) for job in jobs if job.status == "completed")
    return MonitoringModuleOut(
        key="daily-writer",
        title="长文生成",
        description="单篇、批量和五篇套装长文生成情况。",
        cards=job_cards("daily-writer", "长文任务", jobs, window, article_count, "长文生成数"),
        trends=trend_points(job_trend(jobs, window), "长文任务", window),
        breakdowns={
            "status": status_breakdown(status_counts),
            "modes": counter_breakdown(mode_counts),
            "success": success_breakdown(status_counts["completed"], status_counts["failed"]),
        },
        rows=job_rows(jobs, extra=lambda job: {
            "mode": daily_writer_mode(json_dict(job.params_json)),
            "article_count": daily_writer_article_count(job),
        }),
    )


def build_script_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    return build_capability_group_module(db, window, "script-creation", key="scripts", title="脚本创作")


def build_all_capabilities_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(CapabilityJob).all()
    return MonitoringModuleOut(
        key="capabilities",
        title="能力任务",
        description="竞品洞察、选题策划、脚本创作的通用能力任务。",
        cards=job_cards("capabilities", "能力任务", jobs, window),
        trends=trend_points(job_trend(jobs, window), "能力任务", window),
        breakdowns={
            "groups": counter_breakdown(Counter(capability_group(job.capability_key) for job in jobs), labels=CAPABILITY_GROUP_LABELS),
            "capabilities": counter_breakdown(Counter(job.capability_key for job in jobs), labels=capability_labels()),
            "status": status_breakdown(Counter(str(job.status) for job in jobs)),
        },
        rows=capability_rows(jobs),
    )


def build_capability_group_module(
    db: Session,
    window: DateWindow,
    group: str,
    *,
    key: str | None = None,
    title: str | None = None,
) -> MonitoringModuleOut:
    selected_keys = {item.key for item in CAPABILITIES.values() if item.group == group}
    jobs = db.query(CapabilityJob).filter(CapabilityJob.capability_key.in_(selected_keys)).all() if selected_keys else []
    status_counts = Counter(str(job.status) for job in jobs)
    label = title or CAPABILITY_GROUP_LABELS.get(group, group)
    return MonitoringModuleOut(
        key=key or group,
        title=label,
        description=f"{CAPABILITY_GROUP_LABELS.get(group, group)}任务执行情况。",
        cards=job_cards(key or group, label, jobs, window),
        trends=trend_points(job_trend(jobs, window), label, window),
        breakdowns={
            "capabilities": counter_breakdown(Counter(job.capability_key for job in jobs), labels=capability_labels()),
            "status": status_breakdown(status_counts),
            "success": success_breakdown(status_counts["completed"], status_counts["failed"]),
        },
        rows=capability_rows(jobs),
    )
