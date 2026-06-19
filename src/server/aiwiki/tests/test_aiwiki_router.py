# -*- coding: utf-8 -*-
from __future__ import annotations

import sys
import time
import json
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.aiwiki import service
from src.server.config import global_config


@pytest.fixture
def fake_aiwiki_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
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
(wiki_root / "index.md").write_text("# WeChat Topic Wiki\\n", encoding="utf-8")
(wiki_root / "hotspots" / "ai-content-pipeline.md").write_text(
    "---\\ntitle: AI 内容流水线\\ntype: hotspot\\nstatus: active\\ntags: [ai-wiki]\\n---\\n\\n## 发生了什么\\n\\nAI 内容流水线进入实用阶段。\\n",
    encoding="utf-8",
)
(wiki_root / "topics" / "ai-wiki-topic-assets.md").write_text(
    "---\\ntitle: 公众号运营者如何用 AI Wiki 沉淀选题资产？\\ntype: topic\\nstatus: idea\\ntags: [ai-wiki]\\n---\\n\\n## 核心判断\\n\\n用 [[hotspots/ai-content-pipeline]] 承接自动化内容生产。\\n",
    encoding="utf-8",
)
events.append({"event": "completed", "step": "wiki", "summary": "已生成 wiki 索引和词条"})
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
    service.reset_queue_for_tests()
    yield
    service.reset_queue_for_tests()


def _wait_for_terminal_status(test_client, job_id: str) -> dict:
    deadline = time.time() + 5
    latest = None
    while time.time() < deadline:
        resp = test_client.get(f"/api/aiwiki/jobs/{job_id}")
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"job did not finish: {latest}")


def test_create_aiwiki_job_and_get_result(test_client, fake_aiwiki_runtime):
    create_resp = test_client.post(
        "/api/aiwiki/jobs",
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
    assert created["files"][0]["raw_path"].endswith("_1_sample.md")
    assert created["progress"]["status"] == "queued"
    assert created["progress"]["current_step"] == "任务排队中"

    finished = _wait_for_terminal_status(test_client, created["id"])
    assert finished["status"] == "completed", finished
    assert finished["progress"]["status"] == "completed"
    assert finished["progress"]["events"][-1]["summary"] == "任务完成"
    assert any("fake_opencode.py" in line for line in finished["log_tail"])

    result_resp = test_client.get(f"/api/aiwiki/jobs/{created['id']}/result")
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["summary"]["material_count"] == 1
    assert result["materials"][0]["title"] == "AI 写作工具对标文章"
    assert result["search_intents"][0]["关键词"] == "AI Wiki 怎么做"
    assert result["topics"][0]["title"] == "公众号运营者如何用 AI Wiki 沉淀选题资产？"
    assert "AI Wiki 怎么做" in result["highlight_terms"]

    list_resp = test_client.get("/api/aiwiki/jobs")
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    listed = list_resp.json()
    assert listed["total"] >= 1
    assert listed["items"][0]["id"] == created["id"]
    assert listed["items"][0]["status"] == "completed"


def test_rejects_unsupported_upload_type(test_client, fake_aiwiki_runtime):
    resp = test_client.post(
        "/api/aiwiki/jobs",
        files=[("files", ("sample.pdf", b"%PDF", "application/pdf"))],
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "不支持" in resp.json()["detail"]


def test_result_requires_completed_job(test_client, fake_aiwiki_runtime):
    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        files=[("files", ("sample.txt", b"plain text", "text/plain"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text

    job_id = create_resp.json()["id"]
    first_result = test_client.get(f"/api/aiwiki/jobs/{job_id}/result")
    if first_result.status_code == HTTPStatus.CONFLICT:
        assert first_result.json()["detail"] == "任务尚未完成"
    else:
        assert first_result.status_code == HTTPStatus.OK, first_result.text


def test_job_fails_without_progress_completion_marker(
    test_client,
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
    service.reset_queue_for_tests()

    create_resp = test_client.post(
        "/api/aiwiki/jobs",
        files=[("files", ("sample.md", b"# Sample", "text/markdown"))],
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text

    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"])
    assert finished["status"] == "failed"
    assert "progress.json" in finished["message"]


def test_sync_job_records_backfills_existing_manifest(
    test_db_session, fake_aiwiki_runtime, tmp_path: Path
):
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

    service.sync_job_records(test_db_session)

    listed = service.list_jobs(test_db_session, limit=10, offset=0)
    assert any(item.id == job_id for item in listed.items)
