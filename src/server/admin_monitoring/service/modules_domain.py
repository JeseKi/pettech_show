# -*- coding: utf-8 -*-
"""Monitoring modules for domain entities."""

from __future__ import annotations

from collections import Counter

from sqlalchemy.orm import Session

from src.server.agent_skills.models import AgentSkill, AgentSkillCategory, AgentSkillUsageEvent, UserAgentSkill
from src.server.auth.models import User
from src.server.auth.schemas import UserRole, UserStatus
from src.server.chat.models import ChatMessage, ChatSession
from src.server.interactive_movie.models import (
    InteractiveMovieChoice,
    InteractiveMovieProject,
    InteractiveMovieRelease,
    InteractiveMovieScene,
    InteractiveMovieScriptLine,
)

from ..schemas import BreakdownItemOut, MetricCardOut, MonitoringModuleOut
from .metrics import compound_trend_points, counter_breakdown, job_trend, metric, trend_points
from .types import DateWindow
from .windowing import count_in_range, day_key, in_range, iso, latest


def build_agent_skills_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    skills = db.query(AgentSkill).all()
    enabled_skills = [skill for skill in skills if skill.enabled]
    user_links = db.query(UserAgentSkill).all()
    events = db.query(AgentSkillUsageEvent).all()
    add_events = [event for event in events if event.action == "add"]
    remove_events = [event for event in events if event.action == "remove"]
    category_names = {row.id: row.name for row in db.query(AgentSkillCategory).all()}
    category_counts = Counter(category_names.get(skill.category_id, skill.category_id) for skill in enabled_skills)
    visibility_counts = Counter(skill.visibility for skill in enabled_skills)
    trend_counter: Counter[str] = Counter()
    for event in events:
        if in_range(event.created_at, window.start_at, window.end_at):
            event_metric = "Skill 添加" if event.action == "add" else "Skill 移除"
            trend_counter[f"{day_key(event.created_at, window)}|{event_metric}"] += 1

    skill_titles = {skill.id: skill.title for skill in skills}
    user_counts = Counter(link.skill_id for link in user_links if link.enabled)
    rows = [
        {
            "skill_id": skill_id,
            "title": skill_titles.get(skill_id, skill_id),
            "current_user_count": count,
            "add_events": sum(1 for event in add_events if event.skill_id == skill_id),
            "remove_events": sum(1 for event in remove_events if event.skill_id == skill_id),
        }
        for skill_id, count in user_counts.most_common(100)
    ]
    return MonitoringModuleOut(
        key="agent-skills",
        title="Skill",
        description="Skill 市场资产和用户采用/移除情况。",
        cards=[
            metric("market-skills", "市场 Skill", len(skills), count_in_range(skills, window), unit="条"),
            metric("enabled-skills", "启用 Skill", len(enabled_skills), count_in_range(enabled_skills, window), unit="条"),
            metric("user-added-skills", "当前用户已添加", len([link for link in user_links if link.enabled]), count_in_range(add_events, window), unit="次"),
            metric("user-removed-skills", "用户已移除", len(remove_events), count_in_range(remove_events, window), unit="次"),
        ],
        trends=compound_trend_points(trend_counter, window),
        breakdowns={
            "categories": counter_breakdown(category_counts),
            "visibility": counter_breakdown(visibility_counts, labels={"public": "公开", "admin": "管理员可见"}),
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
        if in_range(project.created_at, window.start_at, window.end_at):
            trend_counter[f"{day_key(project.created_at, window)}|项目新增"] += 1
    for release in releases:
        if in_range(release.created_at, window.start_at, window.end_at):
            trend_counter[f"{day_key(release.created_at, window)}|发布"] += 1
    return MonitoringModuleOut(
        key="interactive-movie",
        title="互动电影",
        description="互动电影项目、场景、选择分支、脚本对白和发布情况。",
        cards=[
            metric("movie-projects", "项目数", len(projects), count_in_range(projects, window), unit="个"),
            MetricCardOut(key="movie-scenes", title="场景数", value=len(scenes), unit="个"),
            MetricCardOut(key="movie-script-lines", title="脚本对白行", value=len(lines), unit="行"),
            metric("movie-releases", "发布数", len(releases), count_in_range(releases, window), unit="次"),
        ],
        trends=compound_trend_points(trend_counter, window),
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
                "created_at": iso(project.created_at),
                "updated_at": iso(project.updated_at),
            }
            for project in latest(projects, key=lambda item: item.created_at)
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
            metric("users", "用户数", len(users), count_in_range(users, window), unit="人"),
            MetricCardOut(key="active-users", title="活跃用户", value=len(active_users), unit="人"),
            MetricCardOut(key="admins", title="管理员", value=len(admins), unit="人"),
        ],
        trends=trend_points(job_trend(users, window), "用户新增", window),
        breakdowns={
            "roles": counter_breakdown(role_counts, labels={"admin": "管理员", "user": "普通用户"}),
            "status": counter_breakdown(status_counts, labels={"active": "活跃", "inactive": "停用"}),
        },
        rows=[
            {
                "id": user.id,
                "username": user.username,
                "role": str(user.role.value if hasattr(user.role, "value") else user.role),
                "status": str(user.status.value if hasattr(user.status, "value") else user.status),
                "created_at": iso(user.created_at),
            }
            for user in latest(users, key=lambda item: item.created_at)
        ],
    )


def build_chat_module(db: Session, window: DateWindow) -> MonitoringModuleOut:
    sessions = db.query(ChatSession).all()
    messages = db.query(ChatMessage).all()
    role_counts = Counter(message.role for message in messages)
    trend_counter: Counter[str] = Counter()
    for session in sessions:
        if in_range(session.created_at, window.start_at, window.end_at):
            trend_counter[f"{day_key(session.created_at, window)}|会话新增"] += 1
    for message in messages:
        if in_range(message.created_at, window.start_at, window.end_at):
            trend_counter[f"{day_key(message.created_at, window)}|消息新增"] += 1
    return MonitoringModuleOut(
        key="chat",
        title="智能体聊天",
        description="智能体会话和消息使用情况。",
        cards=[
            metric("chat-sessions", "会话数", len(sessions), count_in_range(sessions, window), unit="个"),
            metric("chat-messages", "消息数", len(messages), count_in_range(messages, window), unit="条"),
        ],
        trends=compound_trend_points(trend_counter, window),
        breakdowns={"roles": counter_breakdown(role_counts, labels={"user": "用户", "assistant": "助手", "system": "系统"})},
        rows=[
            {
                "id": session.id,
                "title": session.title,
                "owner_user_id": session.owner_user_id,
                "created_at": iso(session.created_at),
                "updated_at": iso(session.updated_at),
            }
            for session in latest(sessions, key=lambda item: item.created_at)
        ],
    )
