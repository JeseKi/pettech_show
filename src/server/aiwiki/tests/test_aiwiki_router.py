# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
import json
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.aiwiki import service as aiwiki_service
from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config


@pytest.fixture
def fake_aiwiki_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
import os
from pathlib import Path

root = Path.cwd()
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
config_path = Path(os.environ["OPENCODE_CONFIG"])
assert config_path.name == "config.json"
assert config_path.read_text(encoding="utf-8").strip() == '{"model":"test/model"}'
date = manifest["raw_date"]
events = []

def write_progress(status: str, current_step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

events.append({"event": "started", "step": "raw", "summary": "正在分析 raw 输入"})
write_progress("running", "正在分析 raw 输入")
material_dir = root / "material" / date
wiki_root = root / "wiki"
material_dir.mkdir(parents=True, exist_ok=True)
(wiki_root / "hotspots").mkdir(parents=True, exist_ok=True)
(wiki_root / "pain-points").mkdir(parents=True, exist_ok=True)
(wiki_root / "solutions").mkdir(parents=True, exist_ok=True)
(wiki_root / "topics").mkdir(parents=True, exist_ok=True)
(wiki_root / "search-intents").mkdir(parents=True, exist_ok=True)

material = {
    "元数据": {
        "标题": "AI 写作工具对标文章",
        "字数": "120",
        "分类": ["AI写作"],
        "标签": ["AI Wiki"],
        "raw文件路径": f"raw/{date}/{date}_1_sample.md",
    },
    "文章定位": "面向公众号运营者的对标文章拆解素材。",
    "痛点": [{"痛点": "运营者缺少稳定选题来源", "说明": "热点和痛点没有沉淀。"}],
    "蹭到的热点": [{"热点": "AI 内容流水线", "说明": "自动化内容生产进入实用阶段。"}],
    "解决方案": [{"方案": "AI Wiki 资产沉淀", "说明": "把素材拆成可复用词条。"}],
    "选题": ["公众号运营者如何用 AI Wiki 沉淀选题资产？"],
    "搜索入口": [
        {
            "意图类型": "教程型",
            "关键词": "AI Wiki 怎么做",
            "搜索意图": "用户想搭建可复用内容资产库。",
            "适合文章角度": "从上传对标文章到生成选题资产。",
            "标题使用建议": "建议完整保留",
            "优先级": "高",
            "来源依据": "由原文的 AI Wiki 主题延伸。",
        }
    ],
    "总结": {
        "核心痛点": "缺少可复用选题资产",
        "核心热点": "AI 内容流水线",
        "核心解决方案": "AI Wiki 资产沉淀",
    },
}
(material_dir / f"{date}_1_sample.json").write_text(json.dumps(material, ensure_ascii=False), encoding="utf-8")
events.append({"event": "completed", "step": "material", "summary": "已生成 1 份生文材料"})
write_progress("running", "正在生成 wiki")
(wiki_root / "index.md").write_text(
    "# WeChat Topic Wiki\\n\\n"
    "> 更新时间：2026-06-19\\n"
    "> 素材来源：raw/260619/ → material/260619/\\n\\n"
    "## 活跃热点\\n\\n"
    "| 热点 | 状态 |\\n"
    "| --- | --- |\\n"
    "| [[hotspots/ai-content-pipeline\\\\|AI 内容流水线]] | active |\\n\\n"
    "## 选题（按状态分类）\\n\\n"
    "### 💡 待写作 (idea)\\n\\n"
    "- [[topics/ai-wiki-topic-assets|公众号运营者如何用 AI Wiki 沉淀选题资产？]]\\n",
    encoding="utf-8",
)
(wiki_root / "hotspots" / "ai-content-pipeline.md").write_text(
    "---\\ntitle: AI 内容流水线\\ntype: hotspot\\nstatus: active\\ncreated: 2026-06-19\\nupdated: 2026-06-19\\ntags: [ai-wiki]\\n---\\n\\n## 发生了什么\\n\\nAI 内容流水线进入实用阶段。\\n",
    encoding="utf-8",
)
(wiki_root / "topics" / "ai-wiki-topic-assets.md").write_text(
    "---\\ntitle: 公众号运营者如何用 AI Wiki 沉淀选题资产？\\ntype: topic\\nstatus: idea\\ncreated: 2026-06-19\\nupdated: 2026-06-19\\ntags: [ai-wiki]\\n---\\n\\n## 核心判断\\n\\n用 [[hotspots/ai-content-pipeline]] 承接自动化内容生产。\\n",
    encoding="utf-8",
)
events.append({"event": "completed", "step": "wiki", "summary": "已生成 wiki 索引和词条"})
events.append({"event": "completed", "step": "all", "summary": "任务完成"})
write_progress("completed", "任务完成")
""".strip(),
        encoding="utf-8",
    )
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "config.json").write_text('{"model":"test/model"}', encoding="utf-8")
    monkeypatch.setattr(global_config, "project_root", tmp_path)
    monkeypatch.setattr(
        global_config,
        "aiwiki_opencode_command",
        f"{sys.executable} {fake_opencode}",
    )
    monkeypatch.setattr(global_config, "aiwiki_task_timeout_seconds", 30)
    aiwiki_service.reset_queue_for_tests()
    yield
    aiwiki_service.reset_queue_for_tests()


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
        resp = test_client.get(f"/api/aiwiki/jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {latest}")


def test_aiwiki_requires_authentication(test_client, fake_aiwiki_runtime):
    resp = test_client.get("/api/aiwiki/jobs")
    assert resp.status_code == HTTPStatus.UNAUTHORIZED


def test_create_aiwiki_job_and_get_result(
    test_client, test_db_session, fake_aiwiki_runtime
):
    user = _create_user(test_db_session, "aiwiki_owner")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=headers,
        files=[
            (
                "files",
                ("sample.md", b"# Sample\\n\\nAI Wiki source", "text/markdown"),
            )
        ],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["status"] == "queued"
    assert created["owner_user_id"] == user.id
    assert created["owner_username"] == user.username
    assert created["files"][0]["raw_path"].endswith("_1_sample.md")
    assert created["progress"]["status"] == "queued"
    assert created["progress"]["current_step"] == "任务排队中"

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["progress"]["status"] == "completed"
    assert finished["progress"]["events"][-1]["summary"] == "任务完成"
    assert any("fake_opencode.py" in line for line in finished["log_tail"])

    result_resp = test_client.get(
        f"/api/aiwiki/jobs/{created['id']}/result", headers=headers
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["summary"]["material_count"] == 1
    assert result["materials"][0]["title"] == "AI 写作工具对标文章"
    assert result["search_intents"][0]["关键词"] == "AI Wiki 怎么做"
    assert result["topics"][0]["title"] == "公众号运营者如何用 AI Wiki 沉淀选题资产？"
    assert "AI Wiki 怎么做" in result["highlight_terms"]
    assert result["wiki_home"]["title"] == "WeChat Topic Wiki"
    assert result["wiki_home"]["path"] == "wiki/index.md"
    assert "素材来源" not in result["wiki_home"]["body_markdown"]
    assert "选题（按状态分类）" not in result["wiki_home"]["body_markdown"]
    assert "## 选题" in result["wiki_home"]["body_markdown"]
    assert "待写作 (idea)" not in result["wiki_home"]["body_markdown"]
    assert "hotspots/ai-content-pipeline" in result["wiki_home"]["references"]
    assert "wiki/index.md" not in {entry["path"] for entry in result["wiki_entries"]}
    hotspot = next(
        entry for entry in result["wiki_entries"] if entry["slug"] == "hotspots/ai-content-pipeline"
    )
    assert hotspot["created"] == "2026-06-19"
    assert hotspot["updated"] == "2026-06-19"
    assert hotspot["body_markdown"].startswith("## 发生了什么")
    assert hotspot["excerpt"] == "AI 内容流水线进入实用阶段。"
    topic = next(
        entry for entry in result["wiki_entries"] if entry["slug"] == "topics/ai-wiki-topic-assets"
    )
    assert topic["reference_links"][0]["title"] == "AI 内容流水线"

    list_resp = test_client.get("/api/aiwiki/jobs", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    listed = list_resp.json()
    assert listed["total"] >= 1
    assert listed["items"][0]["id"] == created["id"]
    assert listed["items"][0]["status"] == "completed"


def test_aiwiki_jobs_are_scoped_to_owner_and_visible_to_admin(
    test_client, test_db_session, fake_aiwiki_runtime
):
    owner = _create_user(test_db_session, "aiwiki_owner_scope")
    other = _create_user(test_db_session, "aiwiki_other_scope")
    admin = _create_user(test_db_session, "aiwiki_admin_scope", UserRole.ADMIN)
    owner_headers = _auth_headers(owner)
    other_headers = _auth_headers(other)
    admin_headers = _auth_headers(admin)

    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=owner_headers,
        files=[("files", ("sample.md", b"# Sample", "text/markdown"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    job_id = create_resp.json()["id"]

    other_detail = test_client.get(f"/api/aiwiki/jobs/{job_id}", headers=other_headers)
    assert other_detail.status_code == HTTPStatus.NOT_FOUND

    other_list = test_client.get("/api/aiwiki/jobs", headers=other_headers)
    assert other_list.status_code == HTTPStatus.OK, other_list.text
    assert all(item["id"] != job_id for item in other_list.json()["items"])

    admin_detail = test_client.get(f"/api/aiwiki/jobs/{job_id}", headers=admin_headers)
    assert admin_detail.status_code == HTTPStatus.OK, admin_detail.text
    assert admin_detail.json()["owner_username"] == owner.username


def test_rejects_unsupported_upload_type(
    test_client, test_db_session, fake_aiwiki_runtime
):
    headers = _auth_headers(_create_user(test_db_session, "aiwiki_upload_type"))
    resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=headers,
        files=[("files", ("sample.pdf", b"%PDF", "application/pdf"))],
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "不支持" in resp.json()["detail"]


def test_delete_completed_aiwiki_job(
    test_client, test_db_session, fake_aiwiki_runtime, tmp_path: Path
):
    user = _create_user(test_db_session, "aiwiki_delete")
    headers = _auth_headers(user)
    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=headers,
        files=[("files", ("sample.md", b"# Sample", "text/markdown"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    job_id = create_resp.json()["id"]
    finished = _wait_for_terminal_status(test_client, job_id, headers)
    assert finished["status"] == "completed"

    delete_resp = test_client.delete(f"/api/aiwiki/jobs/{job_id}", headers=headers)
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert not (tmp_path / "data" / job_id).exists()

    detail_resp = test_client.get(f"/api/aiwiki/jobs/{job_id}", headers=headers)
    assert detail_resp.status_code == HTTPStatus.NOT_FOUND


def test_result_requires_completed_job(test_client, test_db_session, fake_aiwiki_runtime):
    headers = _auth_headers(_create_user(test_db_session, "aiwiki_pending"))
    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=headers,
        files=[("files", ("sample.txt", b"plain text", "text/plain"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text

    job_id = create_resp.json()["id"]
    first_result = test_client.get(f"/api/aiwiki/jobs/{job_id}/result", headers=headers)
    if first_result.status_code == HTTPStatus.CONFLICT:
        assert first_result.json()["detail"] == "任务尚未完成"
    else:
        assert first_result.status_code == HTTPStatus.OK, first_result.text


def test_job_fails_without_progress_completion_marker(
    test_client,
    test_db_session,
    fake_aiwiki_runtime,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_incomplete_opencode = tmp_path / "fake_incomplete_opencode.py"
    fake_incomplete_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
(root / "progress.json").write_text(
    json.dumps(
        {
            "status": "running",
            "current_step": "已生成结果但未写完成标记",
            "events": [
                {"event": "started", "step": "raw", "summary": "开始分析 raw 输入"},
                {"event": "completed", "step": "material", "summary": "已生成 material"},
            ],
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        global_config,
        "aiwiki_opencode_command",
        f"{sys.executable} {fake_incomplete_opencode}",
    )
    aiwiki_service.reset_queue_for_tests()
    headers = _auth_headers(_create_user(test_db_session, "aiwiki_failed"))

    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        headers=headers,
        files=[("files", ("sample.md", b"# Sample", "text/markdown"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text

    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)
    assert finished["status"] == "failed"
    assert "progress.json" in finished["message"]


def test_sync_job_records_backfills_existing_manifest(
    test_db_session, fake_aiwiki_runtime, tmp_path: Path
):
    admin = _create_user(test_db_session, "admin", UserRole.ADMIN)
    job_id = "20260619090000_aaaaaaaa_aiwiki"
    workdir = tmp_path / "data" / job_id
    workdir.mkdir(parents=True)
    (workdir / "progress.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "current_step": "任务完成",
                "events": [
                    {"event": "started", "step": "recover", "summary": "已恢复任务"},
                    {"event": "completed", "step": "all", "summary": "任务完成"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    manifest = {
        "id": job_id,
        "status": "completed",
        "message": "old task",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "started_at": None,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "workdir": workdir.as_posix(),
        "files": [
            {
                "filename": "old.md",
                "size_bytes": 12,
                "raw_path": "raw/260619/old.md",
            }
        ],
        "raw_date": "260619",
        "summary": {"material_count": 1},
    }
    (workdir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )

    aiwiki_service.sync_job_records(test_db_session)

    listed = aiwiki_service.list_jobs(
        test_db_session, limit=10, offset=0, current_user=admin
    )
    assert any(item.id == job_id for item in listed.items)
    assert all(item.owner_user_id == admin.id for item in listed.items)
