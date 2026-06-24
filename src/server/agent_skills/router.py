# -*- coding: utf-8 -*-
"""Routes for agent skill marketplace."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Response, Security, status
from sqlalchemy.orm import Session

from src.server.auth.dependencies import get_current_admin, get_current_admin_writer, get_current_user
from src.server.auth.models import User
from src.server.auth.service.scopes import SCOPE_PROFILE_READ
from src.server.dao.dao_base import run_in_thread
from src.server.database import get_db

from .schemas import (
    AgentSkillCategoryCreateIn,
    AgentSkillCategoryOut,
    AgentSkillCategoryUpdateIn,
    AgentSkillCreateIn,
    AgentSkillOut,
    AgentSkillPageOut,
    AgentSkillTagCreateIn,
    AgentSkillTagOut,
    AgentSkillTagUpdateIn,
    AgentSkillUpdateIn,
    UserAgentSkillPageOut,
    UserAgentSkillOut,
)
from .service import (
    add_user_skill,
    create_admin_category,
    create_admin_skill,
    create_admin_tag,
    delete_admin_category,
    delete_admin_skill,
    delete_admin_tag,
    get_admin_skill_detail,
    list_admin_categories,
    list_admin_skills,
    list_admin_tags,
    list_market_categories,
    list_market_skills,
    list_user_skills,
    remove_user_skill,
    update_admin_category,
    update_admin_skill,
    update_admin_tag,
)

router = APIRouter(prefix="/api/agent-skills", tags=["Agent Skills"])


@router.get(
    "/market",
    response_model=AgentSkillPageOut,
    summary="列出 Skill 市场",
)
async def list_market(
    category: str | None = Query(default=None),
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_market_skills(db, current_user, category, search, page, page_size))


@router.get(
    "/categories",
    response_model=list[AgentSkillCategoryOut],
    summary="列出 Skill 市场可用分类",
)
async def list_categories(
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_market_categories(db, current_user))


@router.get(
    "/admin/categories",
    response_model=list[AgentSkillCategoryOut],
    summary="管理员列出 Skill 分类",
)
async def admin_list_categories(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_categories(db))


@router.post(
    "/admin/categories",
    response_model=AgentSkillCategoryOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员创建 Skill 分类",
)
async def admin_create_category(
    payload: AgentSkillCategoryCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_category(db, payload))


@router.patch(
    "/admin/categories/{category_id}",
    response_model=AgentSkillCategoryOut,
    summary="管理员更新 Skill 分类",
)
async def admin_update_category(
    category_id: str,
    payload: AgentSkillCategoryUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_category(db, category_id, payload))


@router.delete(
    "/admin/categories/{category_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员删除 Skill 分类",
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
    response_model=list[AgentSkillTagOut],
    summary="管理员列出 Skill 标签",
)
async def admin_list_tags(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_tags(db))


@router.post(
    "/admin/tags",
    response_model=AgentSkillTagOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员创建 Skill 标签",
)
async def admin_create_tag(
    payload: AgentSkillTagCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_tag(db, payload))


@router.patch(
    "/admin/tags/{tag_id}",
    response_model=AgentSkillTagOut,
    summary="管理员更新 Skill 标签",
)
async def admin_update_tag(
    tag_id: str,
    payload: AgentSkillTagUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_tag(db, tag_id, payload))


@router.delete(
    "/admin/tags/{tag_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员删除 Skill 标签",
)
async def admin_delete_tag(
    tag_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    await run_in_thread(lambda: delete_admin_tag(db, tag_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/my",
    response_model=UserAgentSkillPageOut,
    summary="列出用户已添加到智能体的 Skill",
)
async def list_my_skills(
    search: str | None = Query(default=None, max_length=120),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: list_user_skills(db, current_user, search, page, page_size))


@router.post(
    "/my/{skill_id}",
    response_model=UserAgentSkillOut,
    status_code=status.HTTP_201_CREATED,
    summary="添加 Skill 到当前用户智能体",
)
async def add_my_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    return await run_in_thread(lambda: add_user_skill(db, current_user, skill_id))


@router.delete(
    "/my/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="从当前用户智能体移除 Skill",
)
async def remove_my_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    current_user: User = Security(get_current_user, scopes=[SCOPE_PROFILE_READ]),
):
    await run_in_thread(lambda: remove_user_skill(db, current_user, skill_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get(
    "/admin/market",
    response_model=list[AgentSkillOut],
    summary="管理员列出 Skill 市场索引",
)
async def admin_list_market(
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: list_admin_skills(db))


@router.get(
    "/admin/market/{skill_id}",
    response_model=AgentSkillOut,
    summary="管理员获取 Skill 详情",
)
async def admin_get_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin),
):
    return await run_in_thread(lambda: get_admin_skill_detail(db, skill_id))


@router.post(
    "/admin/market",
    response_model=AgentSkillOut,
    status_code=status.HTTP_201_CREATED,
    summary="管理员添加 Skill 到市场",
)
async def admin_create_skill(
    payload: AgentSkillCreateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: create_admin_skill(db, payload))


@router.patch(
    "/admin/market/{skill_id}",
    response_model=AgentSkillOut,
    summary="管理员更新 Skill",
)
async def admin_update_skill(
    skill_id: str,
    payload: AgentSkillUpdateIn,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    return await run_in_thread(lambda: update_admin_skill(db, skill_id, payload))


@router.delete(
    "/admin/market/{skill_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="管理员删除 Skill",
)
async def admin_delete_skill(
    skill_id: str,
    db: Session = Depends(get_db),
    _: User = Depends(get_current_admin_writer),
):
    await run_in_thread(lambda: delete_admin_skill(db, skill_id))
    return Response(status_code=status.HTTP_204_NO_CONTENT)
