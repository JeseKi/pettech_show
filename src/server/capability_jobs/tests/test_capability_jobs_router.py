# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import time
import zipfile
from http import HTTPStatus
from io import BytesIO
from pathlib import Path

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.capability_jobs.queue_state import reset_queue_for_tests
from src.server.config import global_config


@pytest.fixture
def fake_capability_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_capability_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

root = Path.cwd()
prompt = sys.argv[-1]
config_path = Path(os.environ["OPENCODE_CONFIG"])
assert config_path == root / "config.json"
assert json.loads(config_path.read_text(encoding="utf-8"))["provider"]["killm"]["models"]["gpt-5.5"]["name"] == "GPT 5.5"
assert "output/result.md" in prompt
assert "output/result.json" in prompt
assert "Demo" in prompt
inputs = json.loads((root / "input" / "inputs.json").read_text(encoding="utf-8"))
events = []

def write_progress(status: str, current_step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

events.append({"event": "started", "step": "analysis", "summary": "开始分析输入"})
write_progress("running", "正在分析输入")
output_dir = root / "output"
output_dir.mkdir(parents=True, exist_ok=True)
if "$zhongying-topic-planner" in prompt:
    assert ".agents/skills/zhongying-topic-planner/scripts/validate_result.py" in prompt
    assert (root / ".agents" / "skills" / "zhongying-topic-planner" / "SKILL.md").is_file()
    (output_dir / "result.md").write_text("# 痛点选题池\\n\\n已生成选题池。\\n", encoding="utf-8")
    if inputs.get("identity") == "BAD_JSON":
        (output_dir / "result.json").write_text(
            '{"title": "痛点选题池", "capability_key": "pain-point-topics", "topics": [{"title": "一例"坏 JSON"标题"}]}',
            encoding="utf-8",
        )
    else:
        (output_dir / "result.json").write_text(
            json.dumps(
                {
                    "title": "痛点选题池",
                    "capability_key": "pain-point-topics",
                    "summary": {"topic_count": 1},
                    "sections": [{"title": "选题结论", "items": ["围绕真实痛点生成"]}],
                    "topics": [
                        {
                            "title": "猫咪呕吐后哪些情况必须就医",
                            "category": "症状判断",
                            "total_score": 58,
                            "recommended_hook": "猫吐一次不一定要慌，但这 4 个信号别等",
                        }
                    ],
                    "next_actions": ["选择一个选题进入脚本创作"],
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
elif "$zhongying-script-creator" in prompt:
    assert ".agents/skills/zhongying-script-creator/scripts/validate_result.py" in prompt
    assert (root / ".agents" / "skills" / "zhongying-script-creator" / "SKILL.md").is_file()
    (output_dir / "result.md").write_text("# 脚本母版生成\\n\\n已生成可拍摄脚本。\\n", encoding="utf-8")
    (output_dir / "result.json").write_text(
        json.dumps(
            {
                "title": "脚本母版生成",
                "capability_key": "script-master-draft",
                "summary": {"duration": "60-90 秒"},
                "sections": [{"title": "脚本结构", "items": ["开头", "正文", "结尾"]}],
                "scenes": [
                    {
                        "scene": "开头",
                        "visual": "医生正面口播",
                        "voiceover": "猫吐一次不一定要慌，但出现这些信号别等。",
                        "duration": "8s",
                    }
                ],
                "next_actions": ["按场景拍摄并补充门店素材"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
else:
    (output_dir / "result.md").write_text(
        "# 竞品链接诊断\\n\\n"
        "已经完成内容打法、可借鉴模板和下一步动作整理。\\n",
        encoding="utf-8",
    )
    (output_dir / "result.json").write_text(
        json.dumps(
            {
                "title": "竞品链接诊断",
                "capability_key": "competitor-link-diagnosis",
                "summary": {"primary_input": inputs.get("competitor_links", "")},
                "sections": [{"title": "诊断结论", "items": ["内容结构清晰"]}],
                "next_actions": ["选择一个选题进入脚本创作"],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
events.append({"event": "completed", "step": "analysis", "summary": "已输出报告"})
events.append({"event": "completed", "step": "all", "summary": "任务完成"})
write_progress("completed", "任务完成")
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(global_config, "project_root", tmp_path)
    monkeypatch.setattr(
        global_config,
        "aiwiki_opencode_command",
        f"{sys.executable} {fake_opencode}",
    )
    monkeypatch.setattr(global_config, "aiwiki_task_timeout_seconds", 30)
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps(
            {
                "provider": {
                    "killm": {
                        "models": {
                            "gpt-5.5": {
                                "name": "GPT 5.5",
                            }
                        }
                    }
                }
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    reset_queue_for_tests()
    yield tmp_path
    reset_queue_for_tests()


def _create_user(test_db_session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com")
    user.set_password("Password123")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = auth_service.create_access_token(
        {"sub": user.username, "tv": user.token_version}
    )
    return {"Authorization": f"Bearer {token}"}


def _wait_for_terminal_status(test_client, job_id: str, headers: dict[str, str]) -> dict:
    deadline = time.time() + 5
    latest = None
    while time.time() < deadline:
        resp = test_client.get(f"/api/capability-jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {latest}")


def test_list_capabilities_has_split_entries_without_demo(test_client):
    resp = test_client.get("/api/capability-jobs/capabilities")
    assert resp.status_code == HTTPStatus.OK, resp.text
    capabilities = resp.json()
    assert len(capabilities) == 22
    assert {item["group"] for item in capabilities} == {
        "competitor-insights",
        "topic-planning",
        "script-creation",
    }
    assert not any("Demo" in item["title"] or "Demo" in item["nav_label"] for item in capabilities)


def test_create_capability_job_and_get_result(
    test_client, test_db_session, fake_capability_runtime
):
    user = _create_user(test_db_session, "capability_owner")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={
            "capability_key": "competitor-link-diagnosis",
            "inputs": {
                "competitor_links": "https://example.com/a",
                "identity": "宠物医院",
            },
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["status"] == "queued"
    assert created["owner_user_id"] == user.id
    assert created["inputs"]["identity"] == "宠物医院"

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["title"] == "竞品链接诊断"
    assert finished["progress"]["status"] == "completed"

    result_resp = test_client.get(
        f"/api/capability-jobs/{created['id']}/result",
        headers=headers,
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["markdown"].startswith("# 竞品链接诊断")
    assert result["data"]["capability_key"] == "competitor-link-diagnosis"
    assert result["summary"]["primary_input"] == "https://example.com/a"

    list_resp = test_client.get(
        "/api/capability-jobs?capability_key=competitor-link-diagnosis",
        headers=headers,
    )
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    assert list_resp.json()["items"][0]["id"] == created["id"]

    zip_resp = test_client.get(
        f"/api/capability-jobs/{created['id']}/download",
        headers=headers,
    )
    assert zip_resp.status_code == HTTPStatus.OK, zip_resp.text
    with zipfile.ZipFile(BytesIO(zip_resp.content)) as archive:
        assert set(archive.namelist()) == {"output/result.md", "output/result.json"}


def test_topic_capability_uses_skill_and_validator(
    test_client, test_db_session, fake_capability_runtime
):
    user = _create_user(test_db_session, "capability_topic")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={
            "capability_key": "pain-point-topics",
            "inputs": {
                "competitor_json": "{}",
                "identity": "宠物医院",
            },
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)
    assert finished["status"] == "completed", finished
    assert any("zhongying-topic-planner" in line for line in finished["log_tail"])
    assert any("OK topic planning output" in line for line in finished["log_tail"])

    result_resp = test_client.get(
        f"/api/capability-jobs/{create_resp.json()['id']}/result",
        headers=headers,
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["data"]["topics"][0]["recommended_hook"]


def test_topic_capability_fails_when_validator_rejects_bad_json(
    test_client, test_db_session, fake_capability_runtime
):
    user = _create_user(test_db_session, "capability_topic_bad")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={
            "capability_key": "pain-point-topics",
            "inputs": {
                "competitor_json": "{}",
                "identity": "BAD_JSON",
            },
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)
    assert finished["status"] == "failed", finished
    assert finished["progress"]["status"] == "failure"
    assert finished["progress"]["events"][-1]["event"] == "失败"
    assert "能力结果校验失败" in finished["message"]
    assert "invalid JSON" in finished["message"]


def test_script_capability_uses_skill_and_validator(
    test_client, test_db_session, fake_capability_runtime
):
    user = _create_user(test_db_session, "capability_script")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={
            "capability_key": "script-master-draft",
            "inputs": {
                "topic_json": "{}",
            },
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)
    assert finished["status"] == "completed", finished
    assert any("zhongying-script-creator" in line for line in finished["log_tail"])
    assert any("OK script creation output" in line for line in finished["log_tail"])


def test_create_capability_job_validates_key_and_required_inputs(
    test_client, test_db_session, fake_capability_runtime
):
    user = _create_user(test_db_session, "capability_validation")
    headers = _auth_headers(user)

    unknown_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={"capability_key": "missing", "inputs": {}},
    )
    assert unknown_resp.status_code == HTTPStatus.BAD_REQUEST

    missing_input_resp = test_client.post(
        "/api/capability-jobs",
        headers=headers,
        json={"capability_key": "competitor-link-diagnosis", "inputs": {}},
    )
    assert missing_input_resp.status_code == HTTPStatus.BAD_REQUEST
    assert "竞品链接" in missing_input_resp.json()["detail"]


def test_capability_job_is_owner_scoped(
    test_client, test_db_session, fake_capability_runtime
):
    owner = _create_user(test_db_session, "capability_owner_scope")
    other = _create_user(test_db_session, "capability_other_scope")
    owner_headers = _auth_headers(owner)
    other_headers = _auth_headers(other)

    create_resp = test_client.post(
        "/api/capability-jobs",
        headers=owner_headers,
        json={
            "capability_key": "competitor-link-diagnosis",
            "inputs": {
                "competitor_links": "https://example.com/a",
                "identity": "宠物医院",
            },
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    job_id = create_resp.json()["id"]

    blocked_resp = test_client.get(f"/api/capability-jobs/{job_id}", headers=other_headers)
    assert blocked_resp.status_code == HTTPStatus.NOT_FOUND
