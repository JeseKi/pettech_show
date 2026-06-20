# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.aiwiki.models import AiwikiJob
from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.config import global_config
from src.server.daily_writer.queue_state import reset_queue_for_tests
from src.server.seed_matrix.models import SeedMatrixJob


@pytest.fixture
def fake_daily_writer_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_daily_writer_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path.cwd()
prompt = sys.argv[-1]
if "wechat-main-variant-batch-rewriter" in prompt:
    events = []

    def write_progress(status: str, current_step: str) -> None:
        (root / "progress.json").write_text(
            json.dumps(
                {"status": status, "current_step": current_step, "events": events},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )

    events.append({"event": "started", "step": "variants", "summary": "开始生成变体"})
    write_progress("running", "正在生成变体")
    variants_dir = root / "main" / "260620" / "260620_1" / "variants"
    variants_dir.mkdir(parents=True, exist_ok=True)
    for index in range(1, 6):
        run_dir = variants_dir / f"angle-{index}"
        output_dir = run_dir / "output"
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "others.md").write_text(
            f"这是第 {index} 篇结构不同的长文变体。\\n\\n它保留同一个痛点和方案，但换了叙事路径。\\n",
            encoding="utf-8",
        )
        (output_dir / "metadata.json").write_text(
            json.dumps(
                {
                    "input_mode": "filesystem",
                    "output_id": "260620_1",
                    "audience_label": f"角度 {index}",
                    "article": {
                        "role": "variant",
                        "file": "others.md",
                        "title": f"长文变体 {index}",
                        "summary": "结构不同的长文变体。",
                        "tags": ["产品介绍"],
                        "search_intents": [],
                        "based_on_output_id": "260620_1",
                        "source_main_file": "main/260620/260620_1/main.md",
                    },
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
    (variants_dir / "manifest.json").write_text(json.dumps({"count": 5}, ensure_ascii=False), encoding="utf-8")
    (variants_dir / "angle_plan.json").write_text(json.dumps([], ensure_ascii=False), encoding="utf-8")
    events.append({"event": "completed", "step": "variants", "summary": "已生成 5 篇变体"})
    events.append({"event": "completed", "step": "all", "summary": "任务完成"})
    write_progress("completed", "任务完成")
    raise SystemExit(0)

assert (root / "input" / "selected_seed_row.json").is_file()
assert (root / "material" / "260620" / "sample.json").is_file()
assert (root / "raw" / "260620" / "sample.md").is_file()
assert (root / "wiki" / "index.md").is_file()
row = json.loads((root / "input" / "selected_seed_row.json").read_text(encoding="utf-8"))
events = []

def write_progress(status: str, current_step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

events.append({"event": "started", "step": "draft", "summary": "开始生成长文"})
write_progress("running", "正在生成长文")
output = root / "main" / "260620" / "260620_1"
output.mkdir(parents=True, exist_ok=True)
(output / "main.md").write_text(
    "AI Wiki 真正有价值的地方，不只是把文章存起来。\\n\\n"
    "当选题、痛点和解决方案能被稳定复用，公众号生产会从临时找灵感变成资产驱动。\\n",
    encoding="utf-8",
)
(output / "metadata.json").write_text(
    json.dumps(
        {
            "input_mode": "filesystem",
            "output_id": "260620_1",
            "topic": row["topic"],
            "pain_point": row["pain_point"],
            "solution": row["solution"],
            "hook": row["hook"],
            "article": {
                "role": "main",
                "file": "main.md",
                "title": "AI Wiki 让公众号选题进入资产化阶段",
                "summary": "解释 AI Wiki 如何把选题生产从临时整理变成资产复用。",
                "tags": ["产品介绍", "AI Wiki"],
                "search_intents": [],
                "materials_used": [
                    {
                        "metadata_file": "material/260620/sample.json",
                        "raw_file": "raw/260620/sample.md",
                        "title": "AI Wiki 文章",
                    }
                ],
            },
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
events.append({"event": "completed", "step": "draft", "summary": "已生成长文"})
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
    for skill_name in (
        "wechat-daily-writer",
        "wechat-main-variant-batch-rewriter",
        "wechat-main-variant-rewriter",
    ):
        skill_dir = tmp_path / ".agents" / "skills" / skill_name
        skill_dir.mkdir(parents=True)
        (skill_dir / "SKILL.md").write_text(f"# fake {skill_name} skill\n", encoding="utf-8")
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


def _create_source_jobs(
    test_db_session,
    root: Path,
    user: User,
    *,
    matrix_status: str = "completed",
) -> tuple[AiwikiJob, SeedMatrixJob]:
    aiwiki_id = f"20260620100000_{user.id:08x}_aiwiki"
    aiwiki_workdir = root / "data" / aiwiki_id
    raw_dir = aiwiki_workdir / "raw" / "260620"
    material_dir = aiwiki_workdir / "material" / "260620"
    wiki_dir = aiwiki_workdir / "wiki"
    raw_dir.mkdir(parents=True)
    material_dir.mkdir(parents=True)
    wiki_dir.mkdir(parents=True)
    (raw_dir / "sample.md").write_text("# AI Wiki source\n", encoding="utf-8")
    (material_dir / "sample.json").write_text(
        json.dumps({"元数据": {"标题": "AI Wiki 文章"}}, ensure_ascii=False),
        encoding="utf-8",
    )
    (wiki_dir / "index.md").write_text("# WeChat Topic Wiki\n", encoding="utf-8")
    (aiwiki_workdir / "manifest.json").write_text(
        json.dumps(
            {
                "id": aiwiki_id,
                "owner_user_id": user.id,
                "status": "completed",
                "message": "source",
                "workdir": aiwiki_workdir.as_posix(),
                "raw_date": "260620",
                "files": [{"filename": "source.md", "size_bytes": 10, "raw_path": "raw/260620/sample.md"}],
                "created_at": datetime.now(timezone.utc).isoformat(),
                "started_at": None,
                "finished_at": datetime.now(timezone.utc).isoformat(),
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    aiwiki = AiwikiJob(
        id=aiwiki_id,
        owner_user_id=user.id,
        status="completed",
        message="source",
        workdir=aiwiki_workdir.as_posix(),
        raw_date="260620",
        files_json="[]",
        summary_json=json.dumps({"material_count": 1}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(aiwiki)

    matrix_id = f"20260620101000_{user.id:08x}_seed_matrix"
    matrix_workdir = root / "data" / matrix_id
    csv_path = matrix_workdir / "seed_matrix" / "seed_matrix.csv"
    csv_path.parent.mkdir(parents=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=[
                "seed_id",
                "topic",
                "pain_point",
                "solution",
                "hook",
                "primary_account_type",
                "expected_article_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "seed_id": "S001",
                "topic": "AI Wiki 选题资产化",
                "pain_point": "运营者缺少稳定选题来源",
                "solution": "把素材沉淀成 wiki 和矩阵",
                "hook": "从找灵感到用资产",
                "primary_account_type": "教程号",
                "expected_article_count": "1",
            }
        )
    matrix = SeedMatrixJob(
        id=matrix_id,
        owner_user_id=user.id,
        source_aiwiki_job_id=aiwiki_id,
        status=matrix_status,
        message="matrix",
        workdir=matrix_workdir.as_posix(),
        params_json="{}",
        result_csv_path="seed_matrix/seed_matrix.csv",
        summary_json=json.dumps({"seed_count": 1}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc) if matrix_status == "completed" else None,
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(matrix)
    test_db_session.commit()
    test_db_session.refresh(aiwiki)
    test_db_session.refresh(matrix)
    return aiwiki, matrix


def _wait_for_terminal_status(test_client, job_id: str, headers: dict[str, str]) -> dict:
    deadline = time.time() + 5
    latest = None
    while time.time() < deadline:
        resp = test_client.get(f"/api/daily-writer/jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed", "partial_failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"daily writer job did not finish: {latest}")


def test_create_daily_writer_job_and_download_result(
    test_client, test_db_session, fake_daily_writer_runtime: Path
):
    user = _create_user(test_db_session, "daily_writer_owner")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={"source_seed_matrix_job_id": matrix.id, "seed_id": "S001"},
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["status"] == "queued"
    assert created["source_seed_matrix_job_id"] == matrix.id
    assert created["row"]["topic"] == "AI Wiki 选题资产化"

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["output_id"] == "260620_1"
    assert finished["summary"]["material_count"] == 1

    result_resp = test_client.get(
        f"/api/daily-writer/jobs/{created['id']}/result", headers=headers
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert "资产驱动" in result["markdown"]
    assert result["metadata"]["topic"] == "AI Wiki 选题资产化"

    download_resp = test_client.get(
        f"/api/daily-writer/jobs/{created['id']}/download", headers=headers
    )
    assert download_resp.status_code == HTTPStatus.OK, download_resp.text
    assert download_resp.headers["content-type"] == "application/zip"

    delete_resp = test_client.delete(
        f"/api/daily-writer/jobs/{created['id']}", headers=headers
    )
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert not (fake_daily_writer_runtime / "data" / created["id"]).exists()


def test_create_daily_writer_job_with_variants(
    test_client, test_db_session, fake_daily_writer_runtime: Path
):
    user = _create_user(test_db_session, "daily_writer_variants")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={
            "source_seed_matrix_job_id": matrix.id,
            "seed_id": "S001",
            "generate_variants": True,
            "variant_count": 5,
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["variant_requested_count"] == 5
    assert finished["summary"]["variant_success_count"] == 5
    assert finished["summary"]["variant_status"] == "completed"

    result_resp = test_client.get(
        f"/api/daily-writer/jobs/{create_resp.json()['id']}/result", headers=headers
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert len(result["variants"]) == 5
    assert result["variants"][0]["angle"] == "角度 1"

    download_resp = test_client.get(
        f"/api/daily-writer/jobs/{create_resp.json()['id']}/download", headers=headers
    )
    assert download_resp.status_code == HTTPStatus.OK, download_resp.text
    zip_path = fake_daily_writer_runtime / "download.zip"
    zip_path.write_bytes(download_resp.content)
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "main.md" in names
    assert "metadata.json" in names
    assert "variants/angle-1/output/others.md" in names


def test_rejects_variant_count_above_api_limit(
    test_client, test_db_session, fake_daily_writer_runtime: Path
):
    user = _create_user(test_db_session, "daily_writer_variant_limit")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={
            "source_seed_matrix_job_id": matrix.id,
            "seed_id": "S001",
            "generate_variants": True,
            "variant_count": 6,
        },
    )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_variant_failure_marks_job_partial_failed(
    test_client,
    test_db_session,
    fake_daily_writer_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    failing_opencode = fake_daily_writer_runtime / "failing_variant_opencode.py"
    failing_opencode.write_text(
        """
from __future__ import annotations

import json
import sys
from pathlib import Path

root = Path.cwd()
prompt = sys.argv[-1]
if "wechat-main-variant-batch-rewriter" in prompt:
    (root / "progress.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "current_step": "变体生成失败",
                "events": [{"event": "failed", "step": "variants", "summary": "模拟失败"}],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    raise SystemExit(2)

events = [{"event": "started", "step": "draft", "summary": "开始生成长文"}]
output = root / "main" / "260620" / "260620_1"
output.mkdir(parents=True, exist_ok=True)
(output / "main.md").write_text("长文正文。\\n", encoding="utf-8")
(output / "metadata.json").write_text(
    json.dumps(
        {
            "input_mode": "filesystem",
            "output_id": "260620_1",
            "topic": "AI Wiki",
            "pain_point": "",
            "solution": "",
            "hook": "",
            "article": {"role": "main", "file": "main.md", "title": "标题", "summary": "", "tags": ["产品介绍"], "search_intents": [], "materials_used": []},
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
events.append({"event": "completed", "step": "all", "summary": "任务完成"})
(root / "progress.json").write_text(
    json.dumps({"status": "completed", "current_step": "任务完成", "events": events}, ensure_ascii=False),
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
    reset_queue_for_tests()
    user = _create_user(test_db_session, "daily_writer_variant_failed")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={
            "source_seed_matrix_job_id": matrix.id,
            "seed_id": "S001",
            "generate_variants": True,
            "variant_count": 5,
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)

    assert finished["status"] == "partial_failed"
    assert finished["summary"]["variant_status"] == "failed"
    assert "变体生成失败" in finished["message"]

    result_resp = test_client.get(
        f"/api/daily-writer/jobs/{create_resp.json()['id']}/result", headers=headers
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    assert result_resp.json()["markdown"] == "长文正文。\n"


def test_rejects_missing_seed_id(
    test_client, test_db_session, fake_daily_writer_runtime: Path
):
    user = _create_user(test_db_session, "daily_writer_missing_seed")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={"source_seed_matrix_job_id": matrix.id, "seed_id": "S404"},
    )

    assert resp.status_code == HTTPStatus.NOT_FOUND
    assert "S404" in resp.json()["detail"]


def test_rejects_unfinished_seed_matrix(
    test_client, test_db_session, fake_daily_writer_runtime: Path
):
    user = _create_user(test_db_session, "daily_writer_pending")
    _, matrix = _create_source_jobs(
        test_db_session,
        fake_daily_writer_runtime,
        user,
        matrix_status="running",
    )
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={"source_seed_matrix_job_id": matrix.id, "seed_id": "S001"},
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "已完成" in resp.json()["detail"]


def test_fails_when_generated_article_contains_image(
    test_client,
    test_db_session,
    fake_daily_writer_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    bad_opencode = fake_daily_writer_runtime / "bad_daily_writer_opencode.py"
    bad_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
events = [{"event": "started", "step": "draft", "summary": "开始生成长文"}]
output = root / "main" / "260620" / "260620_1"
output.mkdir(parents=True, exist_ok=True)
(output / "main.md").write_text("正文\\n\\n![cover](cover.png)\\n", encoding="utf-8")
(output / "metadata.json").write_text(
    json.dumps(
        {
            "input_mode": "filesystem",
            "output_id": "260620_1",
            "topic": "AI Wiki",
            "pain_point": "",
            "solution": "",
            "hook": "",
            "article": {"role": "main", "file": "main.md", "title": "标题", "summary": "", "tags": ["产品介绍"], "search_intents": [], "materials_used": []},
        },
        ensure_ascii=False,
    ),
    encoding="utf-8",
)
events.append({"event": "completed", "step": "all", "summary": "任务完成"})
(root / "progress.json").write_text(
    json.dumps({"status": "completed", "current_step": "任务完成", "events": events}, ensure_ascii=False),
    encoding="utf-8",
)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        global_config,
        "aiwiki_opencode_command",
        f"{sys.executable} {bad_opencode}",
    )
    reset_queue_for_tests()
    user = _create_user(test_db_session, "daily_writer_bad_image")
    _, matrix = _create_source_jobs(test_db_session, fake_daily_writer_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/daily-writer/jobs",
        headers=headers,
        json={"source_seed_matrix_job_id": matrix.id, "seed_id": "S001"},
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    finished = _wait_for_terminal_status(test_client, create_resp.json()["id"], headers)

    assert finished["status"] == "failed"
    assert "图片" in finished["message"]
