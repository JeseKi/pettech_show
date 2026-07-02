# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import shutil
import sys
import time
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.aiwiki.models import AiwikiJob
from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.config import global_config
from src.server.opencode.reconciler import reconcile_active_opencode_jobs
from src.server.seed_matrix.models import SeedMatrixJob
from src.server.seed_matrix.queue_state import reset_queue_for_tests

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.fixture
def fake_seed_matrix_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_seed_matrix_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import csv
import json
from pathlib import Path

root = Path.cwd()
events = []

def write_progress(status: str, current_step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

events.append({"event": "started", "step": "matrix", "summary": "开始生成选题矩阵"})
write_progress("running", "正在生成选题矩阵")
output = root / "seed_matrix" / "seed_matrix.csv"
output.parent.mkdir(parents=True, exist_ok=True)
with output.open("w", encoding="utf-8-sig", newline="") as f:
    writer = csv.DictWriter(
        f,
        fieldnames=[
            "day",
            "slot",
            "seed_id",
            "content_pool",
            "topic",
            "pain_point",
            "solution",
            "hook",
            "mother_topic_prompt",
            "variant_ids_to_generate",
            "expected_article_count",
            "primary_account_type",
            "backup_account_types",
            "hook_package",
            "primary_hook_ids",
            "cta_strategy",
            "publishing_note",
        ],
    )
    writer.writeheader()
    writer.writerow(
        {
            "day": "D01",
            "slot": "1",
            "seed_id": "S001",
            "content_pool": "AI Wiki",
            "topic": "如何用 AI Wiki 沉淀选题资产",
            "pain_point": "运营者缺少稳定选题来源",
            "solution": "把素材拆成可复用词条",
            "hook": "中性钩子：引导收藏",
            "mother_topic_prompt": "围绕 AI Wiki 写一篇公众号文章",
            "variant_ids_to_generate": "V01|V02",
            "expected_article_count": "2",
            "primary_account_type": "教程号",
            "backup_account_types": "趋势号|案例号",
            "hook_package": "",
            "primary_hook_ids": "",
            "cta_strategy": "先给出步骤，再承接收藏",
            "publishing_note": "标题和开头必须变化",
        }
    )
events.append({"event": "completed", "step": "matrix", "summary": "已生成 1 条 seed"})
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
    skill_dir = tmp_path / ".agents" / "skills" / "wechat-seed-matrix-builder"
    (skill_dir / "scripts").mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# fake skill\n", encoding="utf-8")
    shutil.copyfile(
        PROJECT_ROOT / ".agents" / "skills" / "wechat-seed-matrix-builder" / "scripts" / "validate_seed_matrix.py",
        skill_dir / "scripts" / "validate_seed_matrix.py",
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


def _create_source_aiwiki_job(
    test_db_session,
    root: Path,
    user: User,
    *,
    status: str = "completed",
) -> AiwikiJob:
    job_id = f"20260620090000_{user.id:08x}_aiwiki"
    workdir = root / "data" / job_id
    material_dir = workdir / "material" / "260620"
    wiki_dir = workdir / "wiki"
    material_dir.mkdir(parents=True)
    wiki_dir.mkdir(parents=True)
    (material_dir / "sample.json").write_text(
        json.dumps(
            {
                "元数据": {"标题": "AI Wiki 文章"},
                "选题": ["如何用 AI Wiki 沉淀选题资产"],
                "总结": {
                    "核心痛点": "缺少稳定选题来源",
                    "核心热点": "AI 内容流水线",
                    "核心解决方案": "结构化内容资产",
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (wiki_dir / "index.md").write_text("# WeChat Topic Wiki\n", encoding="utf-8")
    (workdir / "manifest.json").write_text(
        json.dumps(
            {
                "id": job_id,
                "owner_user_id": user.id,
                "status": status,
                "message": "source",
                "workdir": workdir.as_posix(),
                "raw_date": "260620",
                "files": [{"filename": "source.md", "size_bytes": 10, "raw_path": "raw/260620/source.md"}],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "finished_at": datetime.now(timezone.utc).isoformat() if status == "completed" else None,
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    job = AiwikiJob(
        id=job_id,
        owner_user_id=user.id,
        status=status,
        message="source",
        workdir=workdir.as_posix(),
        raw_date="260620",
        files_json=json.dumps(
            [{"filename": "source.md", "size_bytes": 10, "raw_path": "raw/260620/source.md"}],
            ensure_ascii=False,
        ),
        summary_json=json.dumps({"material_count": 1, "topic_count": 1}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc) if status == "completed" else None,
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


def _wait_for_terminal_status(test_client, job_id: str, headers: dict[str, str]) -> dict:
    deadline = time.time() + 5
    latest = None
    while time.time() < deadline:
        resp = test_client.get(f"/api/seed-matrices/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"} or latest["log_tail"][-1:] == ["HERE IS A E"]:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"seed matrix job did not finish: {latest}")


def test_create_seed_matrix_job_and_download_result(
    test_client, test_db_session, fake_seed_matrix_runtime: Path
):
    user = _create_user(test_db_session, "seed_matrix_owner")
    source = _create_source_aiwiki_job(test_db_session, fake_seed_matrix_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/seed-matrices",
        headers=headers,
        json={
            "source_aiwiki_job_id": source.id,
            "expected_seed_count": 10,
            "slots_per_day": 3,
            "hooks": ["收藏本文\n关注账号", "回复「清单」领取资料"],
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["status"] == "queued"
    assert created["source_aiwiki_job_id"] == source.id
    assert created["title"] is None

    update_resp = test_client.patch(
        f"/api/seed-matrices/{created['id']}",
        headers=headers,
        json={"title": "本周选题策略"},
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text
    assert update_resp.json()["title"] == "本周选题策略"

    list_resp = test_client.get("/api/seed-matrices", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    assert list_resp.json()["items"][0]["title"] == "本周选题策略"

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["seed_count"] == 1
    assert finished["summary"]["expected_article_total"] == 2

    result_resp = test_client.get(
        f"/api/seed-matrices/{created['id']}/result", headers=headers
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert result["rows"][0]["seed_id"] == "S001"
    assert result["rows"][0]["topic"] == "如何用 AI Wiki 沉淀选题资产"

    download_resp = test_client.get(
        f"/api/seed-matrices/{created['id']}/download", headers=headers
    )
    assert download_resp.status_code == HTTPStatus.OK, download_resp.text
    assert b"S001" in download_resp.content

    delete_resp = test_client.delete(
        f"/api/seed-matrices/{created['id']}", headers=headers
    )
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert not (fake_seed_matrix_runtime / "data" / created["id"]).exists()

    missing_resp = test_client.get(
        f"/api/seed-matrices/{created['id']}/result", headers=headers
    )
    assert missing_resp.status_code == HTTPStatus.NOT_FOUND


def test_failed_seed_matrix_job_uses_agent_failure_report(
    test_client,
    test_db_session,
    fake_seed_matrix_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    failing_opencode = fake_seed_matrix_runtime / "fake_seed_matrix_failure.py"
    failing_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
report = root / "failure_report.md"
report.write_text(
    '''
# 选题矩阵生成失败报告

## 失败步骤
检查当前目录资产

## 失败原因
material 目录缺少 260620 JSON 文件。

## 已检查的输入资产
- material/260620
- wiki/index.md

## 已执行的命令或校验
尚未进入 CSV 校验。

## 关键错误信息
material/260620 下没有可用 JSON 文件。

## 建议处理方式
补充 material JSON 后重新运行任务。

## 相关文件路径
- material/260620
'''.strip(),
    encoding="utf-8",
)
events = [
    {
        "event": "开始",
        "step": "检查当前目录资产",
        "summary": "检查当前目录内的 material、wiki、脚本和输出目录",
    },
    {
        "event": "失败",
        "step": "检查当前目录资产",
        "summary": "material 目录缺少 260620 JSON 文件；失败报告：failure_report.md",
    },
]
(root / "progress.json").write_text(
    json.dumps(
        {
            "status": "failure",
            "current_step": "检查当前目录资产",
            "events": events,
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
        f"{sys.executable} {failing_opencode}",
    )

    user = _create_user(test_db_session, "seed_matrix_failure_owner")
    source = _create_source_aiwiki_job(test_db_session, fake_seed_matrix_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/seed-matrices",
        headers=headers,
        json={"source_aiwiki_job_id": source.id},
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "running", finished
    assert finished["message"] == "OpenCode 正在生成选题矩阵"
    assert finished["log_tail"][-1] == "HERE IS A E"

    progress_path = fake_seed_matrix_runtime / "data" / created["id"] / "progress.json"
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    assert progress["status"] == "failure"
    assert progress["events"][-1]["event"] == "失败"
    assert "material 目录缺少 260620 JSON 文件" in progress["events"][-1]["summary"]
    assert "failure_report.md" in progress["events"][-1]["summary"]
    assert "未写入任务完成标记" not in progress["events"][-1]["summary"]
    report_path = fake_seed_matrix_runtime / "data" / created["id"] / "failure_report.md"
    assert report_path.is_file()
    report_text = report_path.read_text(encoding="utf-8")
    assert "选题矩阵生成失败报告" in report_text
    assert "material 目录缺少 260620 JSON 文件" in report_text


def test_reconciler_completes_running_seed_matrix_from_progress_and_result(
    test_db_session,
    fake_seed_matrix_runtime: Path,
):
    user = _create_user(test_db_session, "seed_matrix_reconciler_done")
    source = _create_source_aiwiki_job(test_db_session, fake_seed_matrix_runtime, user)
    job_id = "20260702010101_aaaaaaaa_seed_matrix"
    workdir = _create_reconciler_seed_workdir(fake_seed_matrix_runtime, job_id)
    _write_seed_matrix_csv(workdir / "seed_matrix" / "seed_matrix.csv")
    test_db_session.add(
        SeedMatrixJob(
            id=job_id,
            owner_user_id=user.id,
            source_aiwiki_job_id=source.id,
            status="running",
            message="OpenCode 正在生成选题矩阵",
            workdir=workdir.as_posix(),
            params_json="{}",
            summary_json="{}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    test_db_session.commit()

    assert reconcile_active_opencode_jobs(test_db_session) == 1
    job = test_db_session.get(SeedMatrixJob, job_id)
    assert job is not None
    assert job.status == "completed"
    assert job.result_csv_path == "seed_matrix/seed_matrix.csv"


def test_reconciler_keeps_running_when_completed_progress_has_no_seed_result(
    test_db_session,
    fake_seed_matrix_runtime: Path,
):
    user = _create_user(test_db_session, "seed_matrix_reconciler_missing")
    source = _create_source_aiwiki_job(test_db_session, fake_seed_matrix_runtime, user)
    job_id = "20260702010102_bbbbbbbb_seed_matrix"
    workdir = _create_reconciler_seed_workdir(fake_seed_matrix_runtime, job_id)
    test_db_session.add(
        SeedMatrixJob(
            id=job_id,
            owner_user_id=user.id,
            source_aiwiki_job_id=source.id,
            status="running",
            message="OpenCode 正在生成选题矩阵",
            workdir=workdir.as_posix(),
            params_json="{}",
            summary_json="{}",
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
    )
    test_db_session.commit()

    assert reconcile_active_opencode_jobs(test_db_session) == 0
    job = test_db_session.get(SeedMatrixJob, job_id)
    assert job is not None
    assert job.status == "running"
    assert (workdir / "logs" / "opencode.log").read_text(encoding="utf-8").splitlines()[-1] == "HERE IS A E"


def _create_reconciler_seed_workdir(root: Path, job_id: str) -> Path:
    workdir = root / "data" / job_id
    (workdir / "logs").mkdir(parents=True, exist_ok=True)
    (workdir / "progress.json").write_text(
        json.dumps(
            {
                "status": "completed",
                "current_step": "任务完成",
                "events": [
                    {"event": "完成", "step": "全部", "summary": "任务完成"},
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    return workdir


def _write_seed_matrix_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "day",
                "slot",
                "seed_id",
                "content_pool",
                "topic",
                "pain_point",
                "solution",
                "hook",
                "mother_topic_prompt",
                "variant_ids_to_generate",
                "expected_article_count",
                "primary_account_type",
                "backup_account_types",
                "hook_package",
                "primary_hook_ids",
                "cta_strategy",
                "publishing_note",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "day": "D01",
                "slot": "1",
                "seed_id": "S001",
                "content_pool": "AI Wiki",
                "topic": "如何沉淀选题资产",
                "pain_point": "选题不稳定",
                "solution": "复用 wiki 资产",
                "hook": "查看策略",
                "mother_topic_prompt": "写成方法论",
                "variant_ids_to_generate": "",
                "expected_article_count": "1",
                "primary_account_type": "公众号",
                "backup_account_types": "",
                "hook_package": "",
                "primary_hook_ids": "",
                "cta_strategy": "",
                "publishing_note": "",
            }
        )


def test_rejects_unfinished_aiwiki_source(
    test_client, test_db_session, fake_seed_matrix_runtime: Path
):
    user = _create_user(test_db_session, "seed_matrix_pending")
    source = _create_source_aiwiki_job(
        test_db_session, fake_seed_matrix_runtime, user, status="running"
    )
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/seed-matrices",
        headers=headers,
        json={"source_aiwiki_job_id": source.id},
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "已完成" in resp.json()["detail"]
