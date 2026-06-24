# -*- coding: utf-8 -*-
"""Service functions for admin monitoring dashboards."""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from typing import Any, Iterable
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy.orm import Session

from src.server.agent_skills.models import (
    AgentSkill,
    AgentSkillCategory,
    AgentSkillUsageEvent,
    UserAgentSkill,
)
from src.server.aiwiki.models import AiwikiJob
from src.server.auth.models import User
from src.server.auth.schemas import UserRole, UserStatus
from src.server.capability_jobs.config import CAPABILITIES
from src.server.capability_jobs.models import CapabilityJob
from src.server.chat.models import ChatMessage, ChatSession
from src.server.daily_writer.models import DailyWriterJob
from src.server.interactive_movie.models import (
    InteractiveMovieChoice,
    InteractiveMovieProject,
    InteractiveMovieRelease,
    InteractiveMovieScene,
    InteractiveMovieScriptLine,
)
from src.server.seed_matrix.models import SeedMatrixJob

from .schemas import (
    BreakdownItemOut,
    MetricCardOut,
    MonitoringDetailOut,
    MonitoringModuleOut,
    MonitoringOverviewOut,
    MonitoringRangeOut,
    TrendPointOut,
)


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
    cards = [
        _module_primary_card(module)
        for module in modules
        if module.cards
    ]
    trends: list[TrendPointOut] = []
    for module in modules:
        trends.extend(module.trends[:60])
    return MonitoringOverviewOut(
        range=window_out(window),
        cards=cards,
        modules=modules,
        trends=trends,
    )


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
        builder = builders[module_key]
        module = builder(db, window)
    return MonitoringDetailOut(**module.model_dump(), range=window_out(window))


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
    normalized_end = _as_utc(end_at) if end_at else now
    normalized_start = _as_utc(start_at) if start_at else normalized_end - timedelta(days=7)
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


def build_aiwiki_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(AiwikiJob).all()
    completed = [job for job in jobs if job.status == "completed"]

    asset_totals = Counter[str]()
    range_assets = 0
    today_assets = 0
    last_7_assets = 0
    trend_counter: Counter[str] = Counter()
    rows: list[dict[str, Any]] = []
    status_counts = Counter(str(job.status) for job in jobs)

    for job in completed:
        counts = _asset_counts(job.summary_json)
        asset_total = sum(counts.values())
        asset_totals.update(counts)
        event_time = _completed_time(job)
        if _in_range(event_time, window.start_at, window.end_at):
            range_assets += asset_total
            trend_counter[_day_key(event_time, window)] += asset_total
        if _in_range(event_time, window.today_start_at, window.end_at):
            today_assets += asset_total
        if _in_range(event_time, window.last_7_days_start_at, window.end_at):
            last_7_assets += asset_total

    for job in _latest(jobs, key=lambda item: item.created_at):
        counts = _asset_counts(job.summary_json)
        rows.append(
            {
                "id": job.id,
                "title": job.title,
                "status": job.status,
                "owner_user_id": job.owner_user_id,
                "asset_count": sum(counts.values()),
                "created_at": _iso(job.created_at),
                "finished_at": _iso(job.finished_at),
            }
        )

    total_assets = sum(asset_totals.values())
    return MonitoringModuleOut(
        key="aiwiki",
        title="数据资产",
        description="AI Wiki 已完成任务沉淀的结构化资产。",
        cards=[
            _metric("data-assets", "结构化资产累计", total_assets, range_assets, today_assets, last_7_assets, "条"),
            _metric("aiwiki-jobs", "AI Wiki 任务", len(jobs), _count_in_range(jobs, window), unit="个"),
            _metric("aiwiki-completed", "已完成任务", len(completed), _count_in_range(completed, window), unit="个"),
        ],
        trends=_trend_points(trend_counter, "数据资产新增", window),
        breakdowns={
            "asset_types": [
                BreakdownItemOut(key=key, label=ASSET_LABELS[key], value=asset_totals[key])
                for key in ASSET_LABELS
            ],
            "status": _status_breakdown(status_counts),
        },
        rows=rows,
    )


def build_seed_matrix_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(SeedMatrixJob).all()
    status_counts = Counter(str(job.status) for job in jobs)
    mode_counts = Counter(_seed_matrix_mode(_json_dict(job.params_json)) for job in jobs)
    trend_counter = _job_trend(jobs, window)
    completed = status_counts["completed"]
    failed = status_counts["failed"]
    total_generated = sum(_int(_json_dict(job.summary_json).get("seed_count"), 0) for job in jobs if job.status == "completed")
    return MonitoringModuleOut(
        key="seed-matrix",
        title="选题生成",
        description="标准、批量、高频和 Hook 选题矩阵生成情况。",
        cards=_job_cards("seed-matrix", "选题矩阵任务", jobs, window, total_generated, "选题生成数"),
        trends=_trend_points(trend_counter, "选题矩阵任务", window),
        breakdowns={
            "status": _status_breakdown(status_counts),
            "modes": _counter_breakdown(mode_counts),
            "success": _success_breakdown(completed, failed),
        },
        rows=_job_rows(jobs, extra=lambda job: {"mode": _seed_matrix_mode(_json_dict(job.params_json))}),
    )


def build_daily_writer_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(DailyWriterJob).all()
    status_counts = Counter(str(job.status) for job in jobs)
    mode_counts = Counter(_daily_writer_mode(_json_dict(job.params_json)) for job in jobs)
    trend_counter = _job_trend(jobs, window)
    article_count = sum(_daily_writer_article_count(job) for job in jobs if job.status == "completed")
    completed = status_counts["completed"]
    failed = status_counts["failed"]
    return MonitoringModuleOut(
        key="daily-writer",
        title="长文生成",
        description="单篇、批量和五篇套装长文生成情况。",
        cards=_job_cards("daily-writer", "长文任务", jobs, window, article_count, "长文生成数"),
        trends=_trend_points(trend_counter, "长文任务", window),
        breakdowns={
            "status": _status_breakdown(status_counts),
            "modes": _counter_breakdown(mode_counts),
            "success": _success_breakdown(completed, failed),
        },
        rows=_job_rows(jobs, extra=lambda job: {
            "mode": _daily_writer_mode(_json_dict(job.params_json)),
            "article_count": _daily_writer_article_count(job),
        }),
    )


def build_script_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    return build_capability_group_module(db, window, "script-creation", key="scripts", title="脚本创作")


def build_all_capabilities_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    jobs = db.query(CapabilityJob).all()
    group_counts = Counter(_capability_group(job.capability_key) for job in jobs)
    key_counts = Counter(job.capability_key for job in jobs)
    status_counts = Counter(str(job.status) for job in jobs)
    return MonitoringModuleOut(
        key="capabilities",
        title="能力任务",
        description="竞品洞察、选题策划、脚本创作的通用能力任务。",
        cards=_job_cards("capabilities", "能力任务", jobs, window),
        trends=_trend_points(_job_trend(jobs, window), "能力任务", window),
        breakdowns={
            "groups": _counter_breakdown(group_counts, labels=CAPABILITY_GROUP_LABELS),
            "capabilities": _counter_breakdown(key_counts, labels=_capability_labels()),
            "status": _status_breakdown(status_counts),
        },
        rows=_capability_rows(jobs),
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
    key_counts = Counter(job.capability_key for job in jobs)
    completed = status_counts["completed"]
    failed = status_counts["failed"]
    return MonitoringModuleOut(
        key=key or group,
        title=title or CAPABILITY_GROUP_LABELS.get(group, group),
        description=f"{CAPABILITY_GROUP_LABELS.get(group, group)}任务执行情况。",
        cards=_job_cards(key or group, title or CAPABILITY_GROUP_LABELS.get(group, group), jobs, window),
        trends=_trend_points(_job_trend(jobs, window), title or CAPABILITY_GROUP_LABELS.get(group, group), window),
        breakdowns={
            "capabilities": _counter_breakdown(key_counts, labels=_capability_labels()),
            "status": _status_breakdown(status_counts),
            "success": _success_breakdown(completed, failed),
        },
        rows=_capability_rows(jobs),
    )


def build_agent_skills_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    skills = db.query(AgentSkill).all()
    enabled_skills = [skill for skill in skills if skill.enabled]
    user_links = db.query(UserAgentSkill).all()
    events = db.query(AgentSkillUsageEvent).all()
    add_events = [event for event in events if event.action == "add"]
    remove_events = [event for event in events if event.action == "remove"]

    category_names = {
        row.id: row.name
        for row in db.query(AgentSkillCategory).all()
    }
    category_counts = Counter(category_names.get(skill.category_id, skill.category_id) for skill in enabled_skills)
    visibility_counts = Counter(skill.visibility for skill in enabled_skills)
    trend_counter: Counter[str] = Counter()
    for event in events:
        if _in_range(event.created_at, window.start_at, window.end_at):
            metric = "Skill 添加" if event.action == "add" else "Skill 移除"
            trend_counter[f"{_day_key(event.created_at, window)}|{metric}"] += 1

    rows = []
    skill_titles = {skill.id: skill.title for skill in skills}
    user_counts = Counter(link.skill_id for link in user_links if link.enabled)
    for skill_id, count in user_counts.most_common(100):
        rows.append(
            {
                "skill_id": skill_id,
                "title": skill_titles.get(skill_id, skill_id),
                "current_user_count": count,
                "add_events": sum(1 for event in add_events if event.skill_id == skill_id),
                "remove_events": sum(1 for event in remove_events if event.skill_id == skill_id),
            }
        )

    return MonitoringModuleOut(
        key="agent-skills",
        title="Skill",
        description="Skill 市场资产和用户采用/移除情况。",
        cards=[
            _metric("market-skills", "市场 Skill", len(skills), _count_in_range(skills, window), unit="条"),
            _metric("enabled-skills", "启用 Skill", len(enabled_skills), _count_in_range(enabled_skills, window), unit="条"),
            _metric("user-added-skills", "当前用户已添加", len([link for link in user_links if link.enabled]), _count_in_range(add_events, window), unit="次"),
            _metric("user-removed-skills", "用户已移除", len(remove_events), _count_in_range(remove_events, window), unit="次"),
        ],
        trends=_compound_trend_points(trend_counter, window),
        breakdowns={
            "categories": _counter_breakdown(category_counts),
            "visibility": _counter_breakdown(visibility_counts, labels={"public": "公开", "admin": "管理员可见"}),
        },
        rows=rows,
    )


def build_interactive_movie_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    projects = db.query(InteractiveMovieProject).all()
    scenes = db.query(InteractiveMovieScene).all()
    choices = db.query(InteractiveMovieChoice).all()
    lines = db.query(InteractiveMovieScriptLine).all()
    releases = db.query(InteractiveMovieRelease).all()
    trend_counter: Counter[str] = Counter()
    for project in projects:
        if _in_range(project.created_at, window.start_at, window.end_at):
            trend_counter[f"{_day_key(project.created_at, window)}|项目新增"] += 1
    for release in releases:
        if _in_range(release.created_at, window.start_at, window.end_at):
            trend_counter[f"{_day_key(release.created_at, window)}|发布"] += 1
    return MonitoringModuleOut(
        key="interactive-movie",
        title="互动电影",
        description="互动电影项目、场景、选择分支、脚本对白和发布情况。",
        cards=[
            _metric("movie-projects", "项目数", len(projects), _count_in_range(projects, window), unit="个"),
            MetricCardOut(key="movie-scenes", title="场景数", value=len(scenes), unit="个"),
            MetricCardOut(key="movie-script-lines", title="脚本对白行", value=len(lines), unit="行"),
            _metric("movie-releases", "发布数", len(releases), _count_in_range(releases, window), unit="次"),
        ],
        trends=_compound_trend_points(trend_counter, window),
        breakdowns={
            "entities": [
                BreakdownItemOut(key="projects", label="项目", value=len(projects)),
                BreakdownItemOut(key="scenes", label="场景", value=len(scenes)),
                BreakdownItemOut(key="choices", label="选择分支", value=len(choices)),
                BreakdownItemOut(key="script_lines", label="脚本对白", value=len(lines)),
                BreakdownItemOut(key="releases", label="发布", value=len(releases)),
            ],
        },
        rows=[
            {
                "id": project.id,
                "title": project.title,
                "owner_user_id": project.owner_user_id,
                "is_published": project.is_published,
                "created_at": _iso(project.created_at),
                "updated_at": _iso(project.updated_at),
            }
            for project in _latest(projects, key=lambda item: item.created_at)
        ],
    )


def build_users_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    users = db.query(User).all()
    role_counts = Counter(str(user.role.value if hasattr(user.role, "value") else user.role) for user in users)
    status_counts = Counter(str(user.status.value if hasattr(user.status, "value") else user.status) for user in users)
    active_users = [user for user in users if user.status == UserStatus.ACTIVE]
    admins = [user for user in users if user.role == UserRole.ADMIN]
    return MonitoringModuleOut(
        key="users",
        title="用户",
        description="企业用户、管理员和账号状态。",
        cards=[
            _metric("users", "用户数", len(users), _count_in_range(users, window), unit="人"),
            MetricCardOut(key="active-users", title="活跃用户", value=len(active_users), unit="人"),
            MetricCardOut(key="admins", title="管理员", value=len(admins), unit="人"),
        ],
        trends=_trend_points(_job_trend(users, window), "用户新增", window),
        breakdowns={
            "roles": _counter_breakdown(role_counts, labels={"admin": "管理员", "user": "普通用户"}),
            "status": _counter_breakdown(status_counts, labels={"active": "活跃", "inactive": "停用"}),
        },
        rows=[
            {
                "id": user.id,
                "username": user.username,
                "role": str(user.role.value if hasattr(user.role, "value") else user.role),
                "status": str(user.status.value if hasattr(user.status, "value") else user.status),
                "created_at": _iso(user.created_at),
            }
            for user in _latest(users, key=lambda item: item.created_at)
        ],
    )


def build_chat_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    sessions = db.query(ChatSession).all()
    messages = db.query(ChatMessage).all()
    role_counts = Counter(message.role for message in messages)
    trend_counter: Counter[str] = Counter()
    for session in sessions:
        if _in_range(session.created_at, window.start_at, window.end_at):
            trend_counter[f"{_day_key(session.created_at, window)}|会话新增"] += 1
    for message in messages:
        if _in_range(message.created_at, window.start_at, window.end_at):
            trend_counter[f"{_day_key(message.created_at, window)}|消息新增"] += 1
    return MonitoringModuleOut(
        key="chat",
        title="智能体聊天",
        description="智能体会话和消息使用情况。",
        cards=[
            _metric("chat-sessions", "会话数", len(sessions), _count_in_range(sessions, window), unit="个"),
            _metric("chat-messages", "消息数", len(messages), _count_in_range(messages, window), unit="条"),
        ],
        trends=_compound_trend_points(trend_counter, window),
        breakdowns={"roles": _counter_breakdown(role_counts, labels={"user": "用户", "assistant": "助手", "system": "系统"})},
        rows=[
            {
                "id": session.id,
                "title": session.title,
                "owner_user_id": session.owner_user_id,
                "created_at": _iso(session.created_at),
                "updated_at": _iso(session.updated_at),
            }
            for session in _latest(sessions, key=lambda item: item.created_at)
        ],
    )


def window_out(window: DateWindow) -> MonitoringRangeOut:
    return MonitoringRangeOut(
        start_at=window.start_at,
        end_at=window.end_at,
        today_start_at=window.today_start_at,
        last_7_days_start_at=window.last_7_days_start_at,
        timezone=window.tz_name,
    )


def _module_primary_card(module: MonitoringModuleOut) -> MetricCardOut:
    card = module.cards[0]
    return MetricCardOut(
        **card.model_dump(exclude={"title", "description"}),
        title=module.title,
        description=card.title,
    )


def _metric(
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


def _job_cards(
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
        _metric(key, title, len(jobs), _count_in_range(jobs, window), unit="个"),
        MetricCardOut(key=f"{key}-completed", title="已完成", value=completed, unit="个"),
        MetricCardOut(key=f"{key}-failed", title="失败", value=failed, unit="个"),
        MetricCardOut(
            key=f"{key}-success-rate",
            title="成功率",
            value=round(_success_rate(completed, failed) * 100, 1),
            unit="%",
        ),
    ]
    if generated_total is not None and generated_title is not None:
        cards.insert(1, MetricCardOut(key=f"{key}-generated", title=generated_title, value=generated_total, unit="条"))
    return cards


def _job_rows(jobs: list[Any], *, extra: Any | None = None) -> list[dict[str, Any]]:
    rows = []
    for job in _latest(jobs, key=lambda item: item.created_at):
        payload = {
            "id": job.id,
            "status": job.status,
            "owner_user_id": getattr(job, "owner_user_id", None),
            "created_at": _iso(job.created_at),
            "started_at": _iso(getattr(job, "started_at", None)),
            "finished_at": _iso(getattr(job, "finished_at", None)),
        }
        if extra:
            payload.update(extra(job))
        rows.append(payload)
    return rows


def _capability_rows(jobs: list[CapabilityJob]) -> list[dict[str, Any]]:
    labels = _capability_labels()
    rows = []
    for job in _latest(jobs, key=lambda item: item.created_at):
        rows.append(
            {
                "id": job.id,
                "capability_key": job.capability_key,
                "capability_label": labels.get(job.capability_key, job.capability_key),
                "group": _capability_group(job.capability_key),
                "status": job.status,
                "owner_user_id": job.owner_user_id,
                "created_at": _iso(job.created_at),
                "finished_at": _iso(job.finished_at),
            }
        )
    return rows


def _job_trend(items: Iterable[Any], window: DateWindow) -> Counter[str]:
    counter: Counter[str] = Counter()
    for item in items:
        created_at = getattr(item, "created_at", None)
        if _in_range(created_at, window.start_at, window.end_at):
            counter[_day_key(created_at, window)] += 1
    return counter


def _trend_points(counter: Counter[str], metric: str, window: DateWindow) -> list[TrendPointOut]:
    return [
        TrendPointOut(date=day, metric=metric, value=counter.get(day, 0))
        for day in _date_keys(window)
    ]


def _compound_trend_points(counter: Counter[str], window: DateWindow) -> list[TrendPointOut]:
    metrics = sorted({key.split("|", 1)[1] for key in counter if "|" in key})
    points: list[TrendPointOut] = []
    for day in _date_keys(window):
        for metric in metrics:
            points.append(TrendPointOut(date=day, metric=metric, value=counter.get(f"{day}|{metric}", 0)))
    return points


def _counter_breakdown(counter: Counter[Any], labels: dict[str, str] | None = None) -> list[BreakdownItemOut]:
    label_map = labels or {}
    return [
        BreakdownItemOut(key=str(key), label=label_map.get(str(key), str(key)), value=value)
        for key, value in counter.most_common()
    ]


def _status_breakdown(counter: Counter[str]) -> list[BreakdownItemOut]:
    return [
        BreakdownItemOut(key=key, label=STATUS_LABELS.get(key, key), value=counter.get(key, 0))
        for key in ("queued", "running", "completed", "failed")
    ]


def _success_breakdown(completed: int, failed: int) -> list[BreakdownItemOut]:
    return [
        BreakdownItemOut(key="completed", label="已完成", value=completed),
        BreakdownItemOut(key="failed", label="失败", value=failed),
        BreakdownItemOut(key="success_rate", label="成功率", value=round(_success_rate(completed, failed) * 100, 1)),
    ]


def _asset_counts(summary_json: str | None) -> Counter[str]:
    summary = _json_dict(summary_json)
    return Counter({key: _int(summary.get(key), 0) for key in ASSET_LABELS})


def _json_dict(value: str | None) -> dict[str, Any]:
    if not value:
        return {}
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _daily_writer_article_count(job: DailyWriterJob) -> int:
    summary = _json_dict(job.summary_json)
    if "variant_success_count" in summary:
        return 1 + _int(summary.get("variant_success_count"), 0)
    params = _json_dict(job.params_json)
    if params.get("generate_variants"):
        return 1 + _int(params.get("variant_count"), 0)
    return 1


def _seed_matrix_mode(params: dict[str, Any]) -> str:
    hooks = params.get("hooks")
    seed_count = _int(params.get("expected_seed_count"), 0)
    slots = _int(params.get("slots_per_day"), 0)
    if isinstance(hooks, list) and any(str(item).strip() for item in hooks):
        return "Hook 强化矩阵"
    if seed_count >= 50:
        return "批量选题矩阵"
    if slots >= 8:
        return "高频发布矩阵"
    return "标准选题矩阵"


def _daily_writer_mode(params: dict[str, Any]) -> str:
    if not params.get("generate_variants"):
        return "单篇长文"
    if _int(params.get("variant_count"), 0) == 4:
        return "五篇长文套装"
    return "批量长文"


def _capability_group(capability_key: str) -> str:
    config = CAPABILITIES.get(capability_key)
    return config.group if config else "unknown"


def _capability_labels() -> dict[str, str]:
    return {key: config.nav_label for key, config in CAPABILITIES.items()}


def _count_in_range(items: Iterable[Any], window: DateWindow) -> int:
    return sum(1 for item in items if _in_range(getattr(item, "created_at", None), window.start_at, window.end_at))


def _completed_time(job: Any) -> datetime | None:
    return getattr(job, "finished_at", None) or getattr(job, "created_at", None)


def _in_range(value: datetime | None, start_at: datetime, end_at: datetime) -> bool:
    if value is None:
        return False
    normalized = _as_utc(value)
    return start_at <= normalized <= end_at


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _day_key(value: datetime | None, window: DateWindow) -> str:
    if value is None:
        return ""
    return _as_utc(value).astimezone(window.tz).date().isoformat()


def _date_keys(window: DateWindow) -> list[str]:
    start_date = window.start_at.astimezone(window.tz).date()
    end_date = window.end_at.astimezone(window.tz).date()
    days = max((end_date - start_date).days, 0)
    return [(start_date + timedelta(days=index)).isoformat() for index in range(days + 1)]


def _latest(items: Iterable[Any], *, key: Any, limit: int = 100) -> list[Any]:
    return sorted(items, key=lambda item: key(item) or datetime.min.replace(tzinfo=timezone.utc), reverse=True)[:limit]


def _success_rate(completed: int, failed: int) -> float:
    denominator = completed + failed
    if denominator <= 0:
        return 0.0
    return completed / denominator


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _iso(value: datetime | None) -> str | None:
    return _as_utc(value).isoformat() if value else None
