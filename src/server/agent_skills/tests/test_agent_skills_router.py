# -*- coding: utf-8 -*-
from __future__ import annotations

from http import HTTPStatus

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config


def _create_user(test_db_session, username: str, *, role: UserRole = UserRole.USER) -> User:
    user = User(username=username, email=f"{username}@example.com", role=role)
    user.set_password("Password123")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = auth_service.create_access_token(
        {
            "sub": user.username,
            "scope": auth_service.get_user_scopes(user),
            "tv": user.token_version,
        }
    )
    return {"Authorization": f"Bearer {token}"}


def _create_category(test_client, admin: User, *, category_id: str = "store-operations", name: str = "门店运营"):
    resp = test_client.post(
        "/api/agent-skills/admin/categories",
        headers=_auth_headers(admin),
        json={
            "id": category_id,
            "name": name,
            "description": f"{name}分类",
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def _create_tag(test_client, admin: User, *, tag_id: str = "store-operations", name: str = "门店运营"):
    resp = test_client.post(
        "/api/agent-skills/admin/tags",
        headers=_auth_headers(admin),
        json={
            "id": tag_id,
            "name": name,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def _create_skill(
    test_client,
    admin: User,
    *,
    skill_id: str,
    name: str,
    description: str,
    body: str,
    category_id: str = "store-operations",
    tag_ids: list[str] | None = None,
    visibility: str = "public",
):
    resp = test_client.post(
        "/api/agent-skills/admin/market",
        headers=_auth_headers(admin),
        json={
            "id": skill_id,
            "name": name,
            "description": description,
            "category_id": category_id,
            "tag_ids": tag_ids or ["store-operations"],
            "visibility": visibility,
            "skill_markdown": body,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


@pytest.fixture
def isolated_skill_market(tmp_path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(global_config, "project_root", str(tmp_path))
    return tmp_path / "data" / "skill_market"


def test_admin_create_writes_skill_files_and_index(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_admin", role=UserRole.ADMIN)
    _create_category(test_client, admin)
    _create_tag(test_client, admin)

    payload = _create_skill(
        test_client,
        admin,
        skill_id="pet-review-reply",
        name="宠物客户评价回复",
        description="客服处理评价和差评",
        body="# 宠物客户评价回复\n\n请生成专业回复。",
    )

    assert payload["id"] == "pet-review-reply"
    assert payload["category"] == "store-operations"
    assert payload["category_label"] == "门店运营"
    assert payload["tags"] == ["门店运营"]
    assert (isolated_skill_market / "pet-review-reply" / "SKILL.md").read_text(encoding="utf-8").startswith("# 宠物客户评价回复")
    metadata = isolated_skill_market / "pet-review-reply" / "agents" / "openai.yaml"
    assert metadata.is_file()
    metadata_text = metadata.read_text(encoding="utf-8")
    assert 'id: "pet-review-reply"' in metadata_text
    assert 'category: "store-operations"' in metadata_text
    assert 'visibility: "public"' in metadata_text


def test_market_hides_admin_skills_for_regular_user(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_owner_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "skill_employee")
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    _create_skill(
        test_client,
        admin,
        skill_id="pet-review-reply",
        name="宠物客户评价回复",
        description="客服处理评价和差评",
        body="# 客服 Skill\n\n处理评价。",
    )
    _create_skill(
        test_client,
        admin,
        skill_id="owner-business-dashboard",
        name="老板经营日报",
        description="老板查看经营利润和团队管理",
        body="# 老板经营日报\n\n分析利润。",
        visibility="admin",
    )

    resp = test_client.get("/api/agent-skills/market", headers=_auth_headers(user))

    assert resp.status_code == HTTPStatus.OK, resp.text
    payload = resp.json()
    skills = payload["items"]
    assert payload["total"] == 1
    assert [item["id"] for item in skills] == ["pet-review-reply"]
    assert all(item["visibility"] == "public" for item in skills)


def test_market_shows_admin_skills_for_admin_user(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_admin_owner", role=UserRole.ADMIN)
    _create_category(test_client, admin, category_id="owner-management", name="老板经营")
    _create_tag(test_client, admin, tag_id="owner-management", name="老板经营")
    _create_skill(
        test_client,
        admin,
        skill_id="owner-business-dashboard",
        name="老板经营日报",
        description="老板查看经营利润和团队管理",
        body="# 老板经营日报\n\n分析利润。",
        category_id="owner-management",
        tag_ids=["owner-management"],
        visibility="admin",
    )

    resp = test_client.get("/api/agent-skills/market", headers=_auth_headers(admin))

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert resp.json()["items"][0]["category"] == "owner-management"
    assert resp.json()["items"][0]["visibility"] == "admin"


def test_user_can_add_and_remove_visible_skill(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_admin_add", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "skill_manager")
    headers = _auth_headers(user)
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    _create_skill(
        test_client,
        admin,
        skill_id="pet-review-reply",
        name="宠物客户评价回复",
        description="客服处理评价和差评",
        body="# 客服 Skill\n\n处理评价。",
    )

    add_resp = test_client.post("/api/agent-skills/my/pet-review-reply", headers=headers)

    assert add_resp.status_code == HTTPStatus.CREATED, add_resp.text
    assert add_resp.json()["id"] == "pet-review-reply"
    assert add_resp.json()["added"] is True

    my_resp = test_client.get("/api/agent-skills/my", headers=headers)
    assert my_resp.status_code == HTTPStatus.OK, my_resp.text
    assert [item["id"] for item in my_resp.json()["items"]] == ["pet-review-reply"]

    remove_resp = test_client.delete("/api/agent-skills/my/pet-review-reply", headers=headers)
    assert remove_resp.status_code == HTTPStatus.NO_CONTENT, remove_resp.text
    assert test_client.get("/api/agent-skills/my", headers=headers).json()["items"] == []


def test_regular_user_cannot_add_admin_only_skill(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_admin_block", role=UserRole.ADMIN)
    employee = _create_user(test_db_session, "skill_employee_blocked")
    _create_category(test_client, admin, category_id="owner-management", name="老板经营")
    _create_tag(test_client, admin, tag_id="owner-management", name="老板经营")
    _create_skill(
        test_client,
        admin,
        skill_id="owner-business-dashboard",
        name="老板经营日报",
        description="老板查看经营利润和团队管理",
        body="# 老板经营日报\n\n分析利润。",
        category_id="owner-management",
        tag_ids=["owner-management"],
        visibility="admin",
    )

    resp = test_client.post(
        "/api/agent-skills/my/owner-business-dashboard",
        headers=_auth_headers(employee),
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_market_and_my_skills_support_search_and_pagination(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_admin_paged", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "skill_user_paged")
    headers = _auth_headers(user)
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    _create_skill(
        test_client,
        admin,
        skill_id="pet-review-reply",
        name="宠物客户评价回复",
        description="客服处理评价和差评",
        body="# 客服 Skill\n\n处理评价。",
    )
    _create_skill(
        test_client,
        admin,
        skill_id="pet-sales-script",
        name="到店转化话术",
        description="销售转化和私域成交",
        body="# 销售 Skill\n\n处理转化。",
    )
    _create_skill(
        test_client,
        admin,
        skill_id="pet-content-plan",
        name="小红书内容选题",
        description="内容增长和选题",
        body="# 内容 Skill\n\n处理选题。",
    )

    page_resp = test_client.get("/api/agent-skills/market?page=1&page_size=2", headers=headers)
    assert page_resp.status_code == HTTPStatus.OK, page_resp.text
    page_payload = page_resp.json()
    assert page_payload["total"] == 3
    assert page_payload["page"] == 1
    assert page_payload["page_size"] == 2
    assert len(page_payload["items"]) == 2

    search_resp = test_client.get("/api/agent-skills/market?search=销售", headers=headers)
    assert search_resp.status_code == HTTPStatus.OK, search_resp.text
    assert [item["id"] for item in search_resp.json()["items"]] == ["pet-sales-script"]

    category_resp = test_client.get("/api/agent-skills/categories", headers=headers)
    assert category_resp.status_code == HTTPStatus.OK, category_resp.text
    assert [item["id"] for item in category_resp.json()] == ["store-operations"]

    for skill_id in ("pet-review-reply", "pet-sales-script", "pet-content-plan"):
        add_resp = test_client.post(f"/api/agent-skills/my/{skill_id}", headers=headers)
        assert add_resp.status_code == HTTPStatus.CREATED, add_resp.text

    my_resp = test_client.get("/api/agent-skills/my?search=评价&page=1&page_size=20", headers=headers)
    assert my_resp.status_code == HTTPStatus.OK, my_resp.text
    my_payload = my_resp.json()
    assert my_payload["total"] == 1
    assert [item["id"] for item in my_payload["items"]] == ["pet-review-reply"]


def test_admin_can_crud_categories_and_tags(test_client, test_db_session, isolated_skill_market):
    admin = _create_user(test_db_session, "skill_taxonomy_admin", role=UserRole.ADMIN)
    headers = _auth_headers(admin)

    category = _create_category(test_client, admin, category_id="service", name="客户服务")
    tag = _create_tag(test_client, admin, tag_id="bad-review", name="差评处理")

    assert category["name"] == "客户服务"
    assert tag["name"] == "差评处理"

    update_category = test_client.patch(
        "/api/agent-skills/admin/categories/service",
        headers=headers,
        json={"name": "客服服务", "description": "客服类 Skill", "enabled": True},
    )
    assert update_category.status_code == HTTPStatus.OK, update_category.text
    assert update_category.json()["name"] == "客服服务"

    update_tag = test_client.patch(
        "/api/agent-skills/admin/tags/bad-review",
        headers=headers,
        json={"name": "评价处理", "enabled": True},
    )
    assert update_tag.status_code == HTTPStatus.OK, update_tag.text
    assert update_tag.json()["name"] == "评价处理"

    delete_tag = test_client.delete("/api/agent-skills/admin/tags/bad-review", headers=headers)
    assert delete_tag.status_code == HTTPStatus.NO_CONTENT, delete_tag.text

    delete_category = test_client.delete("/api/agent-skills/admin/categories/service", headers=headers)
    assert delete_category.status_code == HTTPStatus.NO_CONTENT, delete_category.text
