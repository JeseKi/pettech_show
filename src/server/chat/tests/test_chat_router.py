# -*- coding: utf-8 -*-
from __future__ import annotations

import json
from http import HTTPStatus
from pathlib import Path
from typing import Any

import httpx
import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.chat import service as chat_service
from src.server.config import global_config
from src.server.personal_aiwiki import service as personal_aiwiki_service


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


def _create_skill_taxonomy(test_client, admin: User):
    category_resp = test_client.post(
        "/api/agent-skills/admin/categories",
        headers=_auth_headers(admin),
        json={
            "id": "store-operations",
            "name": "门店运营",
            "description": "门店运营类 Skill",
        },
    )
    assert category_resp.status_code == HTTPStatus.CREATED, category_resp.text
    tag_resp = test_client.post(
        "/api/agent-skills/admin/tags",
        headers=_auth_headers(admin),
        json={
            "id": "store-operations",
            "name": "门店运营",
        },
    )
    assert tag_resp.status_code == HTTPStatus.CREATED, tag_resp.text


def _create_agent_taxonomy(test_client, admin: User):
    category_resp = test_client.post(
        "/api/agent-market/admin/categories",
        headers=_auth_headers(admin),
        json={
            "id": "chat-agents",
            "name": "聊天智能体",
            "description": "聊天测试用智能体",
            "visibility": "public",
        },
    )
    assert category_resp.status_code == HTTPStatus.CREATED, category_resp.text
    tag_resp = test_client.post(
        "/api/agent-market/admin/tags",
        headers=_auth_headers(admin),
        json={
            "id": "chat-agent",
            "name": "聊天",
        },
    )
    assert tag_resp.status_code == HTTPStatus.CREATED, tag_resp.text


def _create_agent(
    test_client,
    admin: User,
    *,
    agent_id: str = "pet-content-agent",
    system_prompt: str = "你是宠物内容智能体。",
    visibility: str = "public",
    category_id: str = "chat-agents",
):
    resp = test_client.post(
        "/api/agent-market/admin/market",
        headers=_auth_headers(admin),
        json={
            "id": agent_id,
            "name": "宠物内容智能体",
            "description": "处理宠物内容规划",
            "category_id": category_id,
            "tag_ids": ["chat-agent"] if category_id == "chat-agents" else [],
            "visibility": visibility,
            "system_prompt": system_prompt,
            "change_note": "测试创建",
        },
    )
    assert resp.status_code == HTTPStatus.CREATED, resp.text
    return resp.json()


def _write_personal_aiwiki_fixture(user: User) -> Path:
    workspace_root = personal_aiwiki_service.user_workspace_root(int(user.id))
    personal_aiwiki_service.ensure_workspace(workspace_root)
    wiki_root = workspace_root / "wiki"
    (wiki_root / "index.md").write_text(
        "---\ntitle: 个人知识库\ntype: index\ncreated: 2026-06-26\nupdated: 2026-06-26\ntags: [personal-ai-wiki]\n---\n\n"
        "# 个人知识库\n\n## 最近更新\n\n- [[concepts/personal-knowledge|个人知识沉淀]]\n",
        encoding="utf-8",
    )
    (wiki_root / "concepts").mkdir(parents=True, exist_ok=True)
    (wiki_root / "concepts" / "personal-knowledge.md").write_text(
        "---\ntitle: 个人知识沉淀\ntype: concept\ncreated: 2026-06-26\nupdated: 2026-06-26\ntags: [wiki]\n---\n\n"
        "# 个人知识沉淀\n\n## 结论\n\n演示阶段通过索引触发，再按需读取词条全文。\n",
        encoding="utf-8",
    )
    return workspace_root


def test_chat_completion_requires_authentication(test_client):
    resp = test_client.post(
        "/api/chat/completions",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_chat_stream_requires_authentication(test_client):
    resp = test_client.post(
        "/api/chat/completions/stream",
        json={"messages": [{"role": "user", "content": "你好"}]},
    )

    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_chat_completion_proxies_openai_compatible_response(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = _create_user(test_db_session, "chat_owner")
    captured: dict[str, Any] = {}

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_api_base_url", "https://llm.example.com/v1")
    monkeypatch.setattr(global_config, "chat_model", "test-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_post_chat_completion(_config, payload: dict[str, Any]) -> dict[str, Any]:
        captured["payload"] = payload
        return {
            "id": "chatcmpl-test",
            "model": payload["model"],
            "choices": [
                {
                    "message": {
                        "role": "assistant",
                        "content": "这是后端代理返回的回复",
                    }
                }
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 8,
                "total_tokens": 18,
            },
        }

    monkeypatch.setattr(chat_service, "_post_chat_completion", fake_post_chat_completion)

    resp = test_client.post(
        "/api/chat/completions",
        headers=_auth_headers(user),
        json={
            "messages": [{"role": "user", "content": "帮我做互动影游"}],
            "temperature": 0.4,
            "max_tokens": 500,
        },
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    payload = resp.json()
    assert payload["id"] == "chatcmpl-test"
    assert payload["model"] == "test-model"
    assert payload["role"] == "assistant"
    assert payload["content"] == "这是后端代理返回的回复"
    assert payload["usage"]["total_tokens"] == 18
    assert captured["payload"]["temperature"] == 0.4
    assert captured["payload"]["max_tokens"] == 500
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "帮我做互动影游"},
    ]


def test_chat_stream_proxies_openai_compatible_events(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = _create_user(test_db_session, "chat_stream_owner")
    captured: dict[str, Any] = {}

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "stream-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_stream_chat_events(_config, payload: dict[str, Any]):
        captured["payload"] = payload
        yield "delta", {"content": "流"}
        yield "delta", {"content": "式回复"}
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    resp = test_client.post(
        "/api/chat/completions/stream",
        headers=_auth_headers(user),
        json={"messages": [{"role": "user", "content": "帮我流式生成"}]},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert resp.headers["content-type"].startswith("text/event-stream")
    assert 'event: delta\ndata: {"content": "流"}' in resp.text
    assert 'event: delta\ndata: {"content": "式回复"}' in resp.text
    assert "event: done" in resp.text
    assert captured["payload"]["model"] == "stream-model"
    assert captured["payload"]["stream"] is True
    assert captured["payload"]["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "帮我流式生成"},
    ]


def test_persistent_chat_stream_stores_server_messages_and_uses_server_history(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = _create_user(test_db_session, "chat_persistent_owner")
    headers = _auth_headers(user)
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "persistent-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_stream_chat_events(_config, payload: dict[str, Any]):
        captured_payloads.append(payload)
        yield "delta", {"content": "服务端"}
        yield "delta", {"content": "回复"}
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    first_resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"content": "第一条消息"},
    )
    assert first_resp.status_code == HTTPStatus.OK, first_resp.text
    assert first_resp.headers["content-type"].startswith("text/event-stream")
    assert "event: session" in first_resp.text
    assert 'event: delta\ndata: {"content": "服务端"}' in first_resp.text
    assert 'event: delta\ndata: {"content": "回复"}' in first_resp.text
    assert "event: done" in first_resp.text

    sessions_resp = test_client.get("/api/chat/sessions", headers=headers)
    assert sessions_resp.status_code == HTTPStatus.OK, sessions_resp.text
    sessions = sessions_resp.json()
    assert len(sessions) == 1
    session_id = sessions[0]["id"]
    assert sessions[0]["title"] == "第一条消息"
    assert sessions[0]["message_count"] == 2

    messages_resp = test_client.get(f"/api/chat/sessions/{session_id}/messages", headers=headers)
    assert messages_resp.status_code == HTTPStatus.OK, messages_resp.text
    assert [(item["role"], item["content"]) for item in messages_resp.json()] == [
        ("user", "第一条消息"),
        ("assistant", "服务端回复"),
    ]
    assert captured_payloads[0]["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "第一条消息"},
    ]

    second_resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"session_id": session_id, "content": "第二条消息"},
    )
    assert second_resp.status_code == HTTPStatus.OK, second_resp.text
    assert captured_payloads[1]["messages"] == [
        {"role": "system", "content": "系统提示"},
        {"role": "user", "content": "第一条消息"},
        {"role": "assistant", "content": "服务端回复"},
        {"role": "user", "content": "第二条消息"},
    ]

    rename_resp = test_client.patch(
        f"/api/chat/sessions/{session_id}",
        headers=headers,
        json={"title": "重命名会话"},
    )
    assert rename_resp.status_code == HTTPStatus.OK, rename_resp.text
    assert rename_resp.json()["title"] == "重命名会话"

    delete_resp = test_client.delete(f"/api/chat/sessions/{session_id}", headers=headers)
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert test_client.get("/api/chat/sessions", headers=headers).json() == []


def test_persistent_chat_injects_personal_aiwiki_index_as_user_context(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(global_config, "project_root", tmp_path)
    user = _create_user(test_db_session, "chat_personal_aiwiki_owner")
    headers = _auth_headers(user)
    _write_personal_aiwiki_fixture(user)
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "personal-aiwiki-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_post_chat_completion(_config, payload: dict[str, Any]) -> dict[str, Any]:
        captured_payloads.append(payload)
        return {
            "id": "chatcmpl-personal-aiwiki",
            "model": payload["model"],
            "choices": [{"message": {"role": "assistant", "content": "已根据个人知识库索引回答"}}],
        }

    monkeypatch.setattr(chat_service, "_post_chat_completion", fake_post_chat_completion)

    resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"content": "$知识库 个人知识库里有什么？"},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert 'event: delta\ndata: {"content": "已根据个人知识库索引回答"}' in resp.text
    payload = captured_payloads[0]
    assert payload["tools"][0]["function"]["name"] == chat_service.PERSONAL_AIWIKI_TOOL_NAME
    assert payload["messages"][-2] == {"role": "user", "content": "$知识库 个人知识库里有什么？"}
    assert payload["messages"][-1]["role"] == "user"
    assert "【个人 AI Wiki 最新索引】" in payload["messages"][-1]["content"]
    assert "concepts/personal-knowledge" in payload["messages"][-1]["content"]

    sessions = test_client.get("/api/chat/sessions", headers=headers).json()
    messages_resp = test_client.get(f"/api/chat/sessions/{sessions[0]['id']}/messages", headers=headers)
    assert [(item["role"], item["content"]) for item in messages_resp.json()] == [
        ("user", "$知识库 个人知识库里有什么？"),
        ("assistant", "已根据个人知识库索引回答"),
    ]


def test_chat_completion_personal_aiwiki_tool_reads_entry_page(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
):
    monkeypatch.setattr(global_config, "project_root", tmp_path)
    user = _create_user(test_db_session, "chat_personal_aiwiki_tool_owner")
    headers = _auth_headers(user)
    _write_personal_aiwiki_fixture(user)
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "personal-aiwiki-tool-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_post_chat_completion(_config, payload: dict[str, Any]) -> dict[str, Any]:
        captured_payloads.append(payload)
        if len(captured_payloads) == 1:
            return {
                "id": "chatcmpl-tool-plan",
                "model": payload["model"],
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": "",
                            "tool_calls": [
                                {
                                    "id": "call_entry_1",
                                    "type": "function",
                                    "function": {
                                        "name": chat_service.PERSONAL_AIWIKI_TOOL_NAME,
                                        "arguments": json.dumps({"page": "concepts/personal-knowledge"}, ensure_ascii=False),
                                    },
                                }
                            ],
                        }
                    }
                ],
            }
        return {
            "id": "chatcmpl-tool-final",
            "model": payload["model"],
            "choices": [{"message": {"role": "assistant", "content": "词条全文已经读取。"}}],
        }

    monkeypatch.setattr(chat_service, "_post_chat_completion", fake_post_chat_completion)

    resp = test_client.post(
        "/api/chat/completions",
        headers=headers,
        json={"messages": [{"role": "user", "content": "$知识库 读取个人知识沉淀词条"}]},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert resp.json()["content"] == "词条全文已经读取。"
    assert "tools" in captured_payloads[0]
    assert "tools" not in captured_payloads[1]
    tool_message = next(message for message in captured_payloads[1]["messages"] if message["role"] == "tool")
    assert tool_message["tool_call_id"] == "call_entry_1"
    tool_payload = json.loads(tool_message["content"])
    assert tool_payload["slug"] == "concepts/personal-knowledge"
    assert "演示阶段通过索引触发" in tool_payload["markdown"]


def test_persistent_chat_injects_only_added_mentioned_skill(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    monkeypatch.setattr(global_config, "project_root", str(tmp_path))
    admin = _create_user(test_db_session, "chat_skill_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "chat_skill_owner")
    headers = _auth_headers(user)
    _create_skill_taxonomy(test_client, admin)
    create_resp = test_client.post(
        "/api/agent-skills/admin/market",
        headers=_auth_headers(admin),
        json={
            "id": "pet-review-reply",
            "name": "宠物客户评价回复",
            "description": "客服处理评价和差评",
            "category_id": "store-operations",
            "tag_ids": ["store-operations"],
            "visibility": "public",
            "skill_markdown": "# 宠物客户评价回复\n\n请生成专业回复。",
        },
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    other_resp = test_client.post(
        "/api/agent-skills/admin/market",
        headers=_auth_headers(admin),
        json={
            "id": "pet-sales-script",
            "name": "到店转化话术",
            "description": "销售转化和私域成交",
            "category_id": "store-operations",
            "tag_ids": ["store-operations"],
            "visibility": "public",
            "skill_markdown": "# 到店转化话术\n\n请生成销售话术。",
        },
    )
    assert other_resp.status_code == HTTPStatus.CREATED, other_resp.text
    add_resp = test_client.post("/api/agent-skills/my/pet-review-reply", headers=headers)
    assert add_resp.status_code == HTTPStatus.CREATED, add_resp.text
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "skill-model")
    monkeypatch.setattr(global_config, "chat_system_prompt", "系统提示")

    async def fake_stream_chat_events(_config, payload: dict[str, Any]):
        captured_payloads.append(payload)
        yield "delta", {"content": "已应用技能"}
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"content": "@pet-review-reply @pet-sales-script 帮我回复这条差评"},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    system_content = captured_payloads[0]["messages"][0]["content"]
    assert "系统提示" in system_content
    assert "# 宠物客户评价回复" in system_content
    assert "# 到店转化话术" not in system_content


def test_persistent_chat_pins_agent_prompt_revision(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    admin = _create_user(test_db_session, "chat_agent_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "chat_agent_user")
    headers = _auth_headers(user)
    _create_agent_taxonomy(test_client, admin)
    _create_agent(
        test_client,
        admin,
        agent_id="pet-content-agent",
        system_prompt="版本一：你是宠物内容智能体。",
    )
    captured_payloads: list[dict[str, Any]] = []

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "agent-model")

    async def fake_stream_chat_events(_config, payload: dict[str, Any]):
        captured_payloads.append(payload)
        yield "delta", {"content": "已按 Agent 回复"}
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    first_resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"agent_id": "pet-content-agent", "content": "第一条"},
    )
    assert first_resp.status_code == HTTPStatus.OK, first_resp.text
    sessions = test_client.get("/api/chat/sessions", headers=headers).json()
    session_id = sessions[0]["id"]
    assert sessions[0]["agent_id"] == "pet-content-agent"
    assert captured_payloads[0]["messages"][0]["content"] == "版本一：你是宠物内容智能体。"

    update_resp = test_client.patch(
        "/api/agent-market/admin/market/pet-content-agent",
        headers=_auth_headers(admin),
        json={
            "system_prompt": "版本二：你是宠物内容智能体，必须输出执行清单。",
            "change_note": "更新 Prompt",
        },
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text

    second_resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"session_id": session_id, "agent_id": "pet-content-agent", "content": "第二条"},
    )
    assert second_resp.status_code == HTTPStatus.OK, second_resp.text
    assert captured_payloads[1]["messages"][0]["content"] == "版本一：你是宠物内容智能体。"

    third_resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=headers,
        json={"agent_id": "pet-content-agent", "content": "新会话"},
    )
    assert third_resp.status_code == HTTPStatus.OK, third_resp.text
    assert captured_payloads[2]["messages"][0]["content"] == "版本二：你是宠物内容智能体，必须输出执行清单。"


def test_regular_user_cannot_select_admin_only_agent_for_chat(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    admin = _create_user(test_db_session, "chat_owner_agent_admin", role=UserRole.ADMIN)
    user = _create_user(test_db_session, "chat_owner_agent_user")
    owner_category_resp = test_client.post(
        "/api/agent-market/admin/categories",
        headers=_auth_headers(admin),
        json={
            "id": "owner-chat-agents",
            "name": "老板聊天",
            "description": "老板专属",
            "visibility": "admin",
        },
    )
    assert owner_category_resp.status_code == HTTPStatus.CREATED, owner_category_resp.text
    _create_agent(
        test_client,
        admin,
        agent_id="owner-chat-agent",
        system_prompt="你是老板经营智能体。",
        visibility="admin",
        category_id="owner-chat-agents",
    )

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "agent-model")

    async def fake_stream_chat_events(_config, _payload: dict[str, Any]):
        yield "delta", {"content": "不应执行"}
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    resp = test_client.post(
        "/api/chat/sessions/stream",
        headers=_auth_headers(user),
        json={"agent_id": "owner-chat-agent", "content": "经营分析"},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert "event: error" in resp.text
    assert "智能体不存在或不可见" in resp.text


def test_chat_stream_returns_sse_error_for_unread_upstream_status(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = _create_user(test_db_session, "chat_stream_404")

    monkeypatch.setattr(global_config, "chat_api_key", "test-key")
    monkeypatch.setattr(global_config, "chat_model", "stream-model")

    async def fake_stream_chat_events(_config, _payload: dict[str, Any]):
        request = httpx.Request("POST", "https://llm.example.com/v1/chat/completions")
        response = httpx.Response(
            HTTPStatus.NOT_FOUND,
            request=request,
            stream=httpx.ByteStream(b'{"error":{"message":"missing route"}}'),
        )
        raise httpx.HTTPStatusError(
            "upstream returned 404",
            request=request,
            response=response,
        )
        yield "done", {}

    monkeypatch.setattr(chat_service, "_stream_chat_events", fake_stream_chat_events)

    resp = test_client.post(
        "/api/chat/completions/stream",
        headers=_auth_headers(user),
        json={"messages": [{"role": "user", "content": "测试 404"}]},
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    assert "event: error" in resp.text
    assert "Chat API 上游错误：HTTP 404" in resp.text


def test_chat_completion_requires_api_key(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
):
    user = _create_user(test_db_session, "chat_no_key")
    monkeypatch.setattr(global_config, "chat_api_key", "")

    resp = test_client.post(
        "/api/chat/completions",
        headers=_auth_headers(user),
        json={"messages": [{"role": "user", "content": "你好"}]},
    )

    assert resp.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert resp.json()["detail"] == "Chat API 未配置：请设置 CHAT_API_KEY"
