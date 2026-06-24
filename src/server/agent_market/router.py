# -*- coding: utf-8 -*-
"""Routes for agent marketplace."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, Security, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_admin, get_current_admin_writer, get_current_user
from src.server.auth.models import User
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from .schemas import (
    AgentCategoryCreateIn,
    AgentCategoryOut,
    AgentCategoryUpdateIn,
    AgentCreateIn,
    AgentOut,
    AgentPageOut,
    AgentPromptRevisionOut,
    AgentTagCreateIn,
    AgentTagOut,
    AgentTagUpdateIn,
    AgentUpdateIn,
    UserAgentOut,
    UserAgentPageOut,
)
from .service import (
    add_user_agent,
    create_admin_agent,
    create_admin_category,
    create_admin_tag,
    delete_admin_agent,
    delete_admin_category,
    delete_admin_tag,
    get_admin_agent_detail,
    get_default_agent,
    list_admin_agent_revisions,
    list_admin_agents,
    list_admin_categories,
    list_admin_tags,
    list_market_agents,
    list_market_categories,
    list_user_agents,
    remove_user_agent,
    update_admin_agent,
    update_admin_category,
    update_admin_tag,
)

router = APIRouter(prefix="/api/agent-market", tags=["Agent Market"])


@router.get(
    "/market",
    response_model=AgentPageOut,
    summary="列出智能体市场",
)
async def list_market(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_market_agents(db, current_user, category, search, page, page_size))


@router.get(
    "/categories",
    response_model=list[AgentCategoryOut],
    summary="列出智能体市场可用分类",
)
async def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_market_categories(db, current_user))


@router.get(
    "/default",
    response_model=AgentOut,
    summary="获取默认智能体",
)
async def default_agent(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: get_default_agent(db, current_user))


@router.get(
    "/my",
    response_model=UserAgentPageOut,
    summary="列出用户已添加的智能体",
)
async def list_my_agents(
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_user_agents(db, current_user, search, page, page_size))


@router.post(
    "/my/{agent_id}",
    response_model=UserAgentOut,
    status_code=status.HTTP_201_CREATED,
    summary="添加智能体到当前用户",
)
async def add_my_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: add_user_agent(db, current_user, agent_id))


@router.delete(
    "/my/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="从当前用户移除智能体",
)
async def remove_my_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    await run_in_thread(lambda: remove_user_agent(db, current_user, agent_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/categories",
    response_model=list[AgentCategoryOut],
    summary="管理员列出智能体分类",
)
async def admin_list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_categories(db))


@router.post(
    "/admin/categories",
    response_model=AgentCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员创建智能体分类",
)
async def admin_create_category(
    payload: AgentCategoryCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_category(db, payload))


@router.patch(
    "/admin/categories/{category_id}",
    response_model=AgentCategoryOut,
    summary="管理员更新智能体分类",
)
async def admin_update_category(
    category_id: str,
    payload: AgentCategoryUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_category(db, category_id, payload))


@router.delete(
    "/admin/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员删除智能体分类",
)
async def admin_delete_category(
    category_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    await run_in_thread(lambda: delete_admin_category(db, category_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/tags",
    response_model=list[AgentTagOut],
    summary="管理员列出智能体标签",
)
async def admin_list_tags(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_tags(db))


@router.post(
    "/admin/tags",
    response_model=AgentTagOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员创建智能体标签",
)
async def admin_create_tag(
    payload: AgentTagCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_tag(db, payload))


@router.patch(
    "/admin/tags/{tag_id}",
    response_model=AgentTagOut,
    summary="管理员更新智能体标签",
)
async def admin_update_tag(
    tag_id: str,
    payload: AgentTagUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_tag(db, tag_id, payload))


@router.delete(
    "/admin/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员删除智能体标签",
)
async def admin_delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    await run_in_thread(lambda: delete_admin_tag(db, tag_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/market",
    response_model=list[AgentOut],
    summary="管理员列出智能体市场索引",
)
async def admin_list_market(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_agents(db))


@router.get(
    "/admin/market/{agent_id}",
    response_model=AgentOut,
    summary="管理员获取智能体详情",
)
async def admin_get_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: get_admin_agent_detail(db, agent_id))


@router.get(
    "/admin/market/{agent_id}/revisions",
    response_model=list[AgentPromptRevisionOut],
    summary="管理员列出智能体 Prompt 版本",
)
async def admin_list_revisions(
    agent_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_agent_revisions(db, agent_id))


@router.post(
    "/admin/market",
    response_model=AgentOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员添加智能体到市场",
)
async def admin_create_agent(
    payload: AgentCreateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_agent(db, payload, current_user))


@router.patch(
    "/admin/market/{agent_id}",
    response_model=AgentOut,
    summary="管理员更新智能体",
)
async def admin_update_agent(
    agent_id: str,
    payload: AgentUpdateIn,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_agent(db, agent_id, payload, current_user))


@router.delete(
    "/admin/market/{agent_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员停用智能体",
)
async def admin_delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    await run_in_thread(lambda: delete_admin_agent(db, agent_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
