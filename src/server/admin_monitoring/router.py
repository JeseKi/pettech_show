# -*- coding: utf-8 -*-
"""Admin monitoring routes."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_admin
from src.server.auth.models import User
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from . import service
from .schemas import MonitoringDetailOut, MonitoringOverviewOut


router = APIRouter(prefix="/api/admin/monitoring", tags=["管理员监控"])


async def _detail(
    module_key: str,
    start_at: datetime | None,
    end_at: datetime | None,
    tz: str,
    db: Session,
) -> MonitoringDetailOut:
    return await run_in_thread(
        lambda: service.build_detail(
            db,
            module_key=module_key,
            start_at=start_at,
            end_at=end_at,
            tz=tz,
        )
    )


@router.get("/overview", response_model=MonitoringOverviewOut, summary="管理员监控总览")
async def overview(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(
        lambda: service.build_overview(db, start_at=start_at, end_at=end_at, tz=tz)
    )


@router.get("/aiwiki", response_model=MonitoringDetailOut, summary="数据资产监控详情")
async def aiwiki_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("aiwiki", start_at, end_at, tz, db)


@router.get("/seed-matrix", response_model=MonitoringDetailOut, summary="选题生成监控详情")
async def seed_matrix_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("seed-matrix", start_at, end_at, tz, db)


@router.get("/daily-writer", response_model=MonitoringDetailOut, summary="长文生成监控详情")
async def daily_writer_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("daily-writer", start_at, end_at, tz, db)


@router.get("/scripts", response_model=MonitoringDetailOut, summary="脚本创作监控详情")
async def scripts_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("scripts", start_at, end_at, tz, db)


@router.get("/capabilities", response_model=MonitoringDetailOut, summary="能力任务监控详情")
async def capabilities_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("capabilities", start_at, end_at, tz, db)


@router.get("/agent-skills", response_model=MonitoringDetailOut, summary="Skill 监控详情")
async def agent_skills_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("agent-skills", start_at, end_at, tz, db)


@router.get("/interactive-movie", response_model=MonitoringDetailOut, summary="互动电影监控详情")
async def interactive_movie_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("interactive-movie", start_at, end_at, tz, db)


@router.get("/users", response_model=MonitoringDetailOut, summary="用户监控详情")
async def users_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("users", start_at, end_at, tz, db)


@router.get("/chat", response_model=MonitoringDetailOut, summary="智能体聊天监控详情")
async def chat_detail(
    start_at: Annotated[datetime | None, Query()] = None,
    end_at: Annotated[datetime | None, Query()] = None,
    tz: Annotated[str, Query(max_length=80)] = "Asia/Shanghai",
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await _detail("chat", start_at, end_at, tz, db)
