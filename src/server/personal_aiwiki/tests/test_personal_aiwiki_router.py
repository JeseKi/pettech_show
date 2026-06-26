# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config
from src.server.personal_aiwiki import service as personal_aiwiki_service


@pytest.fixture
def fake_personal_aiwiki_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_personal_aiwiki_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path.cwd()
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
prompt = sys.argv[-1]
assert sys.argv[sys.argv.index("--dir") + 1] == str(root.parent.parent)
assert "$llm-wiki" in prompt
assert "WIKI_PATH" in prompt
workspace = Path(manifest["workspace_dir"])
wiki = workspace / "wiki"
(wiki / "concepts").mkdir(parents=True, exist_ok=True)
(wiki / "queries").mkdir(parents=True, exist_ok=True)
(workspace / "raw").mkdir(parents=True, exist_ok=True)
events = []

def write_progress(status: str, step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps({"status": status, "current_step": step, "events": events}, ensure_ascii=False),
        encoding="utf-8",
    )

events.append({"event": "开始", "step": "读取个人 Wiki", "summary": "已读取索引"})
write_progress("running", "读取个人 Wiki")
(wiki / "index.md").write_text(
    "---\\ntitle: 个人知识库\\ntype: index\\ncreated: 2026-06-26\\nupdated: 2026-06-26\\ntags: [personal-ai-wiki]\\n---\\n\\n"
    "# 个人知识库\\n\\n## 最近更新\\n\\n- [[concepts/personal-knowledge|个人知识沉淀]]\\n",
    encoding="utf-8",
)
(wiki / "log.md").write_text("# 个人 AI Wiki 日志\\n\\n- 2026-06-26 完成测试任务。\\n", encoding="utf-8")
(wiki / "SCHEMA.md").write_text("# Schema\\n", encoding="utf-8")
(wiki / "concepts" / "personal-knowledge.md").write_text(
    "---\\ntitle: 个人知识沉淀\\ntype: concept\\ncreated: 2026-06-26\\nupdated: 2026-06-26\\ntags: [wiki]\\nsources: []\\nconfidence: high\\n---\\n\\n## 结论\\n\\n个人 AI Wiki 会持续沉淀同一用户的资料和问答。\\n",
    encoding="utf-8",
)
if manifest["operation"] == "query":
    (wiki / "queries" / "workspace-question.md").write_text(
        "---\\ntitle: workspace 如何复用？\\ntype: query\\ncreated: 2026-06-26\\nupdated: 2026-06-26\\ntags: [wiki]\\nsources: []\\nconfidence: high\\n---\\n\\n## 答案\\n\\n所有任务共用同一个用户 workspace。\\n",
        encoding="utf-8",
    )
    (root / "answer.md").write_text("所有任务共用同一个用户 workspace。", encoding="utf-8")
else:
    (root / "answer.md").write_text("已更新个人 AI Wiki。", encoding="utf-8")
events.append({"event": "完成", "step": "更新 Wiki", "summary": "已更新个人 Wiki"})
events.append({"event": "完成", "step": "全部", "summary": "任务完成"})
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
    personal_aiwiki_service.reset_queue_for_tests()
    yield
    personal_aiwiki_service.reset_queue_for_tests()


def _create_user(test_db_session, username: str, role: UserRole = UserRole.USER) -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        role=role,
    )
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
        resp = test_client.get(f"/api/personal-aiwiki/jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {latest}")


def test_personal_aiwiki_requires_authentication(test_client, fake_personal_aiwiki_runtime):
    resp = test_client.get("/api/personal-aiwiki/jobs")
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_personal_aiwiki_ingest_uses_user_workspace_and_exposes_entries(
    test_client,
    test_db_session,
    fake_personal_aiwiki_runtime,
    tmp_path: Path,
):
    user = _create_user(test_db_session, "personal_aiwiki_owner")
    headers = _auth_headers(user)

    ingest_resp = test_client.post(
        "/api/personal-aiwiki/jobs",
        headers=headers,
        data={
            "operation": "ingest",
            "title": "个人资料导入",
            "input_text": "# 资料\\n\\n所有任务共用一个个人 Wiki。",
        },
    )
    assert ingest_resp.status_code == HTTPStatus.ACCEPTED, ingest_resp.text
    ingest_job = ingest_resp.json()
    assert ingest_job["operation"] == "ingest"
    assert ingest_job["title"] == "个人资料导入"
    assert ingest_job["workspace_dir"].endswith(f"users/user_{user.id}/workspace")
    assert ingest_job["files"][0]["workspace_raw_path"].startswith("raw/")

    finished_ingest = _wait_for_terminal_status(test_client, ingest_job["id"], headers)
    assert finished_ingest["status"] == "completed", finished_ingest

    workspace_root = tmp_path / "data" / "personal_aiwiki" / "users" / f"user_{user.id}" / "workspace"
    assert workspace_root.is_dir()
    assert (workspace_root / "wiki" / "concepts" / "personal-knowledge.md").is_file()

    result_resp = test_client.get(
        f"/api/personal-aiwiki/jobs/{ingest_job['id']}/result",
        headers=headers,
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["wiki_home"]["title"] == "个人知识库"
    assert any(entry["slug"] == "concepts/personal-knowledge" for entry in result["wiki_entries"])
    assert result["answer_markdown"] == "已更新个人 AI Wiki。"

    entry_resp = test_client.get(
        "/api/personal-aiwiki/entries/concepts/personal-knowledge",
        headers=headers,
    )
    assert entry_resp.status_code == HTTPStatus.OK, entry_resp.text
    entry = entry_resp.json()
    assert entry["slug"] == "concepts/personal-knowledge"
    assert entry["title"] == "个人知识沉淀"
    assert "个人 AI Wiki 会持续沉淀" in entry["markdown"]

    query_resp = test_client.post(
        "/api/personal-aiwiki/jobs",
        headers=headers,
        data={"operation": "query", "input_text": "workspace 如何复用？"},
    )
    assert query_resp.status_code == HTTPStatus.BAD_REQUEST
    assert query_resp.json()["detail"] == "个人 AI Wiki 任务目前只支持整理资料"

    workspace_resp = test_client.get("/api/personal-aiwiki/workspace", headers=headers)
    assert workspace_resp.status_code == HTTPStatus.OK, workspace_resp.text
    assert workspace_resp.json()["summary"]["wiki_entry_count"] >= 1

    list_resp = test_client.get("/api/personal-aiwiki/jobs", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    listed = list_resp.json()
    assert listed["total"] == 1
    assert listed["stats"]["ingest_count"] == 1
    assert listed["stats"]["query_count"] == 0
