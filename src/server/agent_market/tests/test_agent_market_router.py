# -*- coding: utf-8 -*-
from __future__ import annotations

from http import HTTPStatus

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole


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


def _create_category(
    test_client,
    admin: User,
    *,
    category_id: str = "store-agents",
    name: str = "门店智能体",
    visibility: str = "public",
):
    resp = test_client.post(
        "/api/agent-market/admin/categories",
        headers=_auth_headers(admin),
        json={
            "id": category_id,
            "name": name,
            "description": f"{name}分类",
            "visibility": visibility,
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def _create_tag(test_client, admin: User, *, tag_id: str = "store", name: str = "门店"):
    resp = test_client.post(
        "/api/agent-market/admin/tags",
        headers=_auth_headers(admin),
        json={"id": tag_id, "name": name},
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def _create_agent(
    test_client,
    admin: User,
    *,
    agent_id: str,
    name: str,
    description: str,
    system_prompt: str,
    category_id: str = "store-agents",
    tag_ids: list[str] | None = None,
    visibility: str = "public",
):
    resp = test_client.post(
        "/api/agent-market/admin/market",
        headers=_auth_headers(admin),
        json={
            "id": agent_id,
            "name": name,
            "description": description,
            "category_id": category_id,
            "tag_ids": ["store"] if tag_ids is None else tag_ids,
            "visibility": visibility,
            "system_prompt": system_prompt,
            "change_note": "测试创建",
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def test_default_agent_is_seeded_and_public(test_client, test_db_session):
    user = _create_user(test_db_session, "agent_default_user")

    resp = test_client.get("/api/agent-market/default", headers=_auth_headers(user))

    assert resp.status_code == HTTPStatus.OK, resp.text
    payload = resp.json()
    assert payload["id"] == "zhongying-advertising"
    assert payload["name"] == "中影广告智能体"
    assert payload["is_default"] is True
    assert payload["protected"] is True
    assert payload["added"] is True
    assert payload["system_prompt"] is None

    my_resp = test_client.get("/api/agent-market/my", headers=_auth_headers(user))
    assert my_resp.status_code == HTTPStatus.OK, my_resp.text
    my_payload = my_resp.json()
    assert my_payload["total"] == 1
    assert my_payload["items"][0]["id"] == "zhongying-advertising"
    assert my_payload["items"][0]["added"] is True


def test_market_hides_admin_agents_for_regular_user(test_client, test_db_session):
    admin = _create_user(test_db_session, "agent_visibility_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "agent_visibility_user")
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    _create_category(test_client, admin, category_id="owner-agents-test", name="老板经营", visibility="admin")
    _create_agent(
        test_client,
        admin,
        agent_id="pet-frontdesk",
        name="宠物前台智能体",
        description="处理门店咨询",
        system_prompt="你是宠物前台。",
    )
    _create_agent(
        test_client,
        admin,
        agent_id="owner-business",
        name="老板经营智能体",
        description="处理经营分析",
        system_prompt="你是老板经营顾问。",
        category_id="owner-agents-test",
        tag_ids=[],
        visibility="admin",
    )

    user_resp = test_client.get("/api/agent-market/market", headers=_auth_headers(user))
    admin_resp = test_client.get("/api/agent-market/market", headers=_auth_headers(admin))

    assert user_resp.status_code == HTTPStatus.OK, user_resp.text
    assert admin_resp.status_code == HTTPStatus.OK, admin_resp.text
    user_ids = {item["id"] for item in user_resp.json()["items"]}
    admin_ids = {item["id"] for item in admin_resp.json()["items"]}
    assert "pet-frontdesk" in user_ids
    assert "owner-business" not in user_ids
    assert "owner-business" in admin_ids


def test_user_can_add_and_remove_visible_agent(test_client, test_db_session):
    admin = _create_user(test_db_session, "agent_add_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "agent_add_user")
    headers = _auth_headers(user)
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    _create_agent(
        test_client,
        admin,
        agent_id="pet-frontdesk-agent",
        name="宠物前台智能体",
        description="处理门店咨询",
        system_prompt="你是宠物前台。",
    )

    market_resp = test_client.get("/api/agent-market/market", headers=headers)
    assert market_resp.status_code == HTTPStatus.OK, market_resp.text
    market_items = {item["id"]: item for item in market_resp.json()["items"]}
    assert market_items["zhongying-advertising"]["added"] is True
    assert market_items["pet-frontdesk-agent"]["added"] is False

    add_resp = test_client.post("/api/agent-market/my/pet-frontdesk-agent", headers=headers)
    assert add_resp.status_code == HTTPStatus.CREATED, add_resp.text
    assert add_resp.json()["added"] is True

    my_resp = test_client.get("/api/agent-market/my", headers=headers)
    assert my_resp.status_code == HTTPStatus.OK, my_resp.text
    assert [item["id"] for item in my_resp.json()["items"]] == ["zhongying-advertising", "pet-frontdesk-agent"]

    remove_resp = test_client.delete("/api/agent-market/my/pet-frontdesk-agent", headers=headers)
    assert remove_resp.status_code == HTTPStatus.NO_CONTENT, remove_resp.text
    assert [item["id"] for item in test_client.get("/api/agent-market/my", headers=headers).json()["items"]] == [
        "zhongying-advertising"
    ]

    remove_default_resp = test_client.delete("/api/agent-market/my/zhongying-advertising", headers=headers)
    assert remove_default_resp.status_code == HTTPStatus.BAD_REQUEST


def test_regular_user_cannot_add_admin_only_agent(test_client, test_db_session):
    admin = _create_user(test_db_session, "agent_add_hidden_admin", role=UserRole.ADMIN)
    employee = _create_user(test_db_session, "agent_add_hidden_user")
    _create_category(test_client, admin, category_id="owner-hidden-agents", name="老板经营", visibility="admin")
    _create_agent(
        test_client,
        admin,
        agent_id="owner-private-agent",
        name="老板经营智能体",
        description="处理经营分析",
        system_prompt="你是老板经营顾问。",
        category_id="owner-hidden-agents",
        tag_ids=[],
        visibility="admin",
    )

    resp = test_client.post("/api/agent-market/my/owner-private-agent", headers=_auth_headers(employee))

    assert resp.status_code == HTTPStatus.NOT_FOUND


def test_admin_crud_agent_creates_prompt_revisions_and_soft_deletes(test_client, test_db_session):
    admin = _create_user(test_db_session, "agent_crud_admin", role=UserRole.ADMIN)
    headers = _auth_headers(admin)
    _create_category(test_client, admin)
    _create_tag(test_client, admin)
    created = _create_agent(
        test_client,
        admin,
        agent_id="pet-content-director",
        name="宠物内容总监",
        description="规划宠物企业内容",
        system_prompt="版本一：做内容规划。",
    )
    assert created["current_version"] == 1

    detail_resp = test_client.get("/api/agent-market/admin/market/pet-content-director", headers=headers)
    assert detail_resp.status_code == HTTPStatus.OK, detail_resp.text
    assert detail_resp.json()["system_prompt"] == "版本一：做内容规划。"

    update_resp = test_client.patch(
        "/api/agent-market/admin/market/pet-content-director",
        headers=headers,
        json={
            "system_prompt": "版本二：做内容规划，并输出执行清单。",
            "change_note": "加入执行清单",
        },
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text
    assert update_resp.json()["current_version"] == 2

    revisions_resp = test_client.get(
        "/api/agent-market/admin/market/pet-content-director/revisions",
        headers=headers,
    )
    assert revisions_resp.status_code == HTTPStatus.OK, revisions_resp.text
    revisions = revisions_resp.json()
    assert [item["version"] for item in revisions] == [2, 1]
    assert revisions[0]["active"] is True
    assert revisions[0]["system_prompt"] == "版本二：做内容规划，并输出执行清单。"

    delete_resp = test_client.delete("/api/agent-market/admin/market/pet-content-director", headers=headers)
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    market_resp = test_client.get("/api/agent-market/market", headers=headers)
    assert "pet-content-director" not in {item["id"] for item in market_resp.json()["items"]}


def test_default_agent_cannot_be_deleted_or_disabled(test_client, test_db_session):
    admin = _create_user(test_db_session, "agent_default_admin", role=UserRole.ADMIN)
    headers = _auth_headers(admin)
    default_resp = test_client.get("/api/agent-market/default", headers=headers)
    assert default_resp.status_code == HTTPStatus.OK, default_resp.text

    disable_resp = test_client.patch(
        "/api/agent-market/admin/market/zhongying-advertising",
        headers=headers,
        json={"enabled": False},
    )
    delete_resp = test_client.delete("/api/agent-market/admin/market/zhongying-advertising", headers=headers)

    assert disable_resp.status_code == HTTPStatus.BAD_REQUEST
    assert delete_resp.status_code == HTTPStatus.BAD_REQUEST
