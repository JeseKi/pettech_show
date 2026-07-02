# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import sys
import time
import zipfile
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.config import global_config
from src.server.daily_writer.models import DailyWriterJob
from src.server.social_cards.queue_state import reset_queue_for_tests


@pytest.fixture
def fake_social_card_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_social_card_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

root = Path.cwd()
prompt = " ".join(sys.argv)

def prompt_int(key: str, default: int) -> int:
    match = re.search(rf"{key}:\\s*(\\d+)", prompt)
    return int(match.group(1)) if match else default

def read_existing_events() -> list[object]:
    progress_path = root / "progress.json"
    if not progress_path.exists():
        return []
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    events = progress.get("events")
    return list(events) if isinstance(events, list) else []

def write_progress(status: str, current_step: str) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

assert (root / "source" / "main.md").is_file()
assert (root / "source" / "metadata.json").is_file()
assert (root / "tools" / "render_social_deck.mjs").is_file()
post_count = prompt_int("post_count", 1)
cards_per_post = prompt_int("cards_per_post", 3)
events = read_existing_events()
events.append({"event": "开始", "step": "小红书图文卡", "summary": "开始生成图文卡"})
write_progress("running", "正在生成小红书图文卡")

for post_index in range(1, post_count + 1):
    if post_index == 1:
        xhs_dir = root / "xhs_guizang"
    else:
        xhs_dir = root / "xhs_guizang_variants" / f"variant-{post_index - 1:02d}"
    output_dir = xhs_dir / "output"
    output_dir.mkdir(parents=True, exist_ok=True)
    images = []
    markdown_lines = [f"# 图文卡片 {post_index}", ""]
    for index in range(1, cards_per_post + 1):
        image_path = output_dir / f"xhs-{index:02d}.png"
        image_path.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + bytes([post_index, index]))
        images.append({"id": f"xhs-{index:02d}", "file": f"output/xhs-{index:02d}.png"})
        markdown_lines.append(f"![xhs-{index:02d}](output/xhs-{index:02d}.png)")
        markdown_lines.append("")
    (xhs_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    (xhs_dir / "plan.md").write_text(f"# 图文计划 {post_index}\\n", encoding="utf-8")
    (xhs_dir / "manifest.json").write_text(
        json.dumps({"pages": cards_per_post, "uploaded_images": images}, ensure_ascii=False),
        encoding="utf-8",
    )
    (xhs_dir / "main.md").write_text("\\n".join(markdown_lines), encoding="utf-8")

events.append({"event": "完成", "step": "小红书图文卡", "summary": f"已生成 {post_count} 篇图文"})
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
    skill_dir = tmp_path / ".agents" / "skills" / "guizang-social-card-skill"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# fake guizang skill\n", encoding="utf-8")
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


def _create_daily_writer_source(
    test_db_session,
    root: Path,
    user: User,
    *,
    status: str = "completed",
) -> DailyWriterJob:
    job_id = f"20260620120000_{user.id:08x}_daily_writer"
    workdir = root / "data" / job_id
    article_dir = workdir / "main" / "260620" / "260620_1"
    article_dir.mkdir(parents=True)
    (article_dir / "main.md").write_text(
        "AI Wiki 真正有价值的地方，是把选题变成可复用资产。\\n\\n"
        "小红书图文卡需要把这篇主稿压缩成连续的视觉论点。\\n",
        encoding="utf-8",
    )
    (article_dir / "metadata.json").write_text(
        json.dumps(
            {
                "input_mode": "filesystem",
                "output_id": "260620_1",
                "topic": "AI Wiki 选题资产化",
                "pain_point": "运营者缺少稳定选题来源",
                "solution": "把素材沉淀成 wiki 和矩阵",
                "hook": "从找灵感到用资产",
                "article": {
                    "role": "main",
                    "file": "main.md",
                    "title": "AI Wiki 让公众号选题进入资产化阶段",
                    "summary": "解释 AI Wiki 如何把选题生产从临时整理变成资产复用。",
                    "tags": ["产品介绍"],
                    "search_intents": [],
                    "materials_used": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    source_progress = {
        "status": "completed",
        "current_step": "任务完成",
        "events": [{"event": "完成", "step": "全部", "summary": "任务完成"}],
    }
    (workdir / "progress.json").write_text(
        json.dumps(source_progress, ensure_ascii=False),
        encoding="utf-8",
    )
    job = DailyWriterJob(
        id=job_id,
        owner_user_id=user.id,
        source_seed_matrix_job_id=f"20260620110000_{user.id:08x}_seed_matrix",
        source_aiwiki_job_id=f"20260620100000_{user.id:08x}_aiwiki",
        seed_id="S001",
        status=status,
        message="source",
        workdir=workdir.as_posix(),
        row_json=json.dumps({"topic": "AI Wiki 选题资产化"}, ensure_ascii=False),
        params_json=json.dumps({"generate_variants": False}, ensure_ascii=False),
        article_path="main/260620/260620_1/main.md",
        metadata_path="main/260620/260620_1/metadata.json",
        summary_json=json.dumps({"title": "AI Wiki 让公众号选题进入资产化阶段"}, ensure_ascii=False),
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
        resp = test_client.get(f"/api/social-cards/jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"} or latest["log_tail"][-1:] == ["HERE IS A E"]:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"social card job did not finish: {latest}")


def test_create_social_card_job_and_download_result(
    test_client, test_db_session, fake_social_card_runtime: Path
):
    user = _create_user(test_db_session, "social_card_owner")
    source = _create_daily_writer_source(test_db_session, fake_social_card_runtime, user)
    source_progress_before = (
        Path(source.workdir) / "progress.json"
    ).read_text(encoding="utf-8")
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/social-cards/jobs",
        headers=headers,
        json={
            "source_daily_writer_job_id": source.id,
            "post_count": 2,
            "cards_per_post": 3,
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["source_daily_writer_job_id"] == source.id
    assert created["params"]["post_count"] == 2
    assert created["params"]["cards_per_post"] == 3
    assert created["title"] is None
    update_resp = test_client.patch(
        f"/api/social-cards/jobs/{created['id']}",
        headers=headers,
        json={"title": "小红书图文任务"},
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text
    assert update_resp.json()["title"] == "小红书图文任务"
    list_resp = test_client.get("/api/social-cards/jobs", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    assert list_resp.json()["items"][0]["title"] == "小红书图文任务"
    assert (
        fake_social_card_runtime
        / "data"
        / created["id"]
        / "tools"
        / "render_social_deck.mjs"
    ).is_file()

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["post_count"] == 2
    assert finished["summary"]["cards_per_post"] == 3
    assert finished["summary"]["image_count"] == 6
    assert (Path(source.workdir) / "progress.json").read_text(encoding="utf-8") == source_progress_before

    result_resp = test_client.get(
        f"/api/social-cards/jobs/{created['id']}/result",
        headers=headers,
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert len(result["posts"]) == 2
    assert len(result["posts"][0]["images"]) == 3
    assert len(result["posts"][1]["images"]) == 3
    assert len(result["images"]) == 6
    assert result["images"][0]["url"] == (
        f"/api/social-cards/jobs/{created['id']}/images/post_01_card_01"
    )
    assert "social-card-image:post_01_card_01" in result["markdown"]
    assert "social-card-image:post_02_card_01" in result["markdown"]
    assert "output/xhs-01.png" not in result["markdown"]

    image_resp = test_client.get(
        f"/api/social-cards/jobs/{created['id']}/images/post_02_card_01",
        headers=headers,
    )
    assert image_resp.status_code == HTTPStatus.OK, image_resp.text
    assert image_resp.headers["content-type"] == "image/png"
    assert image_resp.content.startswith(b"\x89PNG")

    other_user = _create_user(test_db_session, "social_card_other")
    other_resp = test_client.get(
        f"/api/social-cards/jobs/{created['id']}/images/post_01_card_01",
        headers=_auth_headers(other_user),
    )
    assert other_resp.status_code == HTTPStatus.NOT_FOUND

    list_resp = test_client.get(
        f"/api/social-cards/jobs?source_daily_writer_job_id={source.id}",
        headers=headers,
    )
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    assert list_resp.json()["total"] == 1

    download_resp = test_client.get(
        f"/api/social-cards/jobs/{created['id']}/download",
        headers=headers,
    )
    assert download_resp.status_code == HTTPStatus.OK, download_resp.text
    zip_path = fake_social_card_runtime / "social-card-download.zip"
    zip_path.write_bytes(download_resp.content)
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "xhs_guizang/main.md" in names
    assert "xhs_guizang/output/xhs-01.png" in names
    assert "xhs_guizang_variants/variant-01/main.md" in names
    assert "xhs_guizang_variants/variant-01/output/xhs-01.png" in names

    delete_resp = test_client.delete(
        f"/api/social-cards/jobs/{created['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert not (fake_social_card_runtime / "data" / created["id"]).exists()


def test_rejects_unfinished_or_inaccessible_source(
    test_client, test_db_session, fake_social_card_runtime: Path
):
    user = _create_user(test_db_session, "social_card_pending")
    source = _create_daily_writer_source(
        test_db_session,
        fake_social_card_runtime,
        user,
        status="running",
    )
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/social-cards/jobs",
        headers=headers,
        json={"source_daily_writer_job_id": source.id, "card_count": 3},
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "已完成" in resp.json()["detail"]

    other_user = _create_user(test_db_session, "social_card_no_access")
    other_resp = test_client.post(
        "/api/social-cards/jobs",
        headers=_auth_headers(other_user),
        json={"source_daily_writer_job_id": source.id, "card_count": 3},
    )
    assert other_resp.status_code == HTTPStatus.NOT_FOUND


def test_rejects_social_card_count_above_limit(
    test_client, test_db_session, fake_social_card_runtime: Path
):
    user = _create_user(test_db_session, "social_card_limit")
    source = _create_daily_writer_source(test_db_session, fake_social_card_runtime, user)
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/social-cards/jobs",
        headers=headers,
        json={"source_daily_writer_job_id": source.id, "card_count": 10},
    )

    assert resp.status_code == HTTPStatus.UNPROCESSABLE_ENTITY


def test_reports_incomplete_progress_when_opencode_exits_early(
    test_client,
    test_db_session,
    fake_social_card_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    incomplete_opencode = fake_social_card_runtime / "fake_incomplete_opencode.py"
    incomplete_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
progress_path = root / "progress.json"
progress = json.loads(progress_path.read_text(encoding="utf-8"))
events = progress.get("events")
if not isinstance(events, list):
    events = []
events.append({"event": "开始", "step": "创建图文文件", "summary": "开始写入图文文件"})
progress_path.write_text(
    json.dumps(
        {"status": "running", "current_step": "创建图文文件", "events": events},
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
        f"{sys.executable} {incomplete_opencode}",
    )
    user = _create_user(test_db_session, "social_card_incomplete")
    source = _create_daily_writer_source(test_db_session, fake_social_card_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/social-cards/jobs",
        headers=headers,
        json={
            "source_daily_writer_job_id": source.id,
            "post_count": 1,
            "cards_per_post": 3,
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "running", finished
    assert finished["message"] == "OpenCode 正在生成小红书图文卡"
    assert finished["log_tail"][-1] == "HERE IS A E"

    progress = json.loads(
        (
            fake_social_card_runtime
            / "data"
            / created["id"]
            / "progress.json"
        ).read_text(encoding="utf-8")
    )
    assert progress["status"] == "running"
    assert progress["current_step"] == "创建图文文件"


def test_repairs_incomplete_generation_with_second_tmux_run(
    test_client,
    test_db_session,
    fake_social_card_runtime: Path,
    monkeypatch: pytest.MonkeyPatch,
):
    retry_opencode = fake_social_card_runtime / "fake_retry_social_card_opencode.py"
    retry_opencode.write_text(
        """
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

root = Path.cwd()
if len(sys.argv) >= 3 and sys.argv[1:3] == ["session", "list"]:
    print(json.dumps([
        {
            "id": "ses_test_social_card_repair",
            "title": "Xiaohongshu social card generation",
            "directory": str(root),
            "created": int(time.time() * 1000),
            "updated": int(time.time() * 1000),
        }
    ]))
    raise SystemExit(0)

prompt = " ".join(sys.argv)
attempt_path = root / ".retry-attempt"
argv_log_path = root / ".retry-argv.jsonl"
progress_path = root / "progress.json"
with argv_log_path.open("a", encoding="utf-8") as argv_log:
    argv_log.write(json.dumps(sys.argv, ensure_ascii=False) + "\\n")

def prompt_int(key: str, default: int) -> int:
    match = re.search(rf"{key}:\\s*(\\d+)", prompt)
    return int(match.group(1)) if match else default

def read_events() -> list[object]:
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    events = progress.get("events")
    return list(events) if isinstance(events, list) else []

def write_progress(status: str, current_step: str, events: list[object]) -> None:
    progress_path.write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

cards_per_post = prompt_int("cards_per_post", 3)
events = read_events()
if not attempt_path.exists():
    attempt_path.write_text("1", encoding="utf-8")
    deck = root / "xhs_guizang"
    deck.mkdir(parents=True, exist_ok=True)
    (deck / "output").mkdir(exist_ok=True)
    (deck / "index.html").write_text("<html></html>", encoding="utf-8")
    (deck / "plan.md").write_text("# plan\\n", encoding="utf-8")
    (deck / "manifest.json").write_text(
        json.dumps(
            {
                "total_card_count": cards_per_post,
                "cards": [
                    {"index": index, "file": f"output/xhs-{index + 1:02d}.png"}
                    for index in range(cards_per_post)
                ],
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    (deck / "main.md").write_text("# main\\n", encoding="utf-8")
    events.append({"event": "开始", "step": "生成图文目录", "summary": "写入图文目录但未渲染"})
    write_progress("running", "生成图文目录", events)
    raise SystemExit(0)

deck = root / "xhs_guizang"
output = deck / "output"
output.mkdir(parents=True, exist_ok=True)
main_lines = ["# repaired", ""]
for index in range(1, cards_per_post + 1):
    image_path = output / f"xhs-{index:02d}.png"
    image_path.write_bytes(b"\\x89PNG\\r\\n\\x1a\\n" + bytes([index]))
    main_lines.append(f"![xhs-{index:02d}](output/xhs-{index:02d}.png)")
    main_lines.append("")
(deck / "main.md").write_text("\\n".join(main_lines), encoding="utf-8")
events.append({"event": "开始", "step": "继续渲染图文卡", "summary": "补齐缺失 PNG"})
events.append({"event": "完成", "step": "继续渲染图文卡", "summary": "已补齐缺失 PNG"})
events.append({"event": "完成", "step": "全部", "summary": "任务完成"})
write_progress("completed", "任务完成", events)
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr(
        global_config,
        "aiwiki_opencode_command",
        f"{sys.executable} {retry_opencode}",
    )
    user = _create_user(test_db_session, "social_card_repair")
    source = _create_daily_writer_source(test_db_session, fake_social_card_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/social-cards/jobs",
        headers=headers,
        json={
            "source_daily_writer_job_id": source.id,
            "post_count": 1,
            "cards_per_post": 3,
        },
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["image_count"] == 3

    progress = json.loads(
        (
            fake_social_card_runtime
            / "data"
            / created["id"]
            / "progress.json"
        ).read_text(encoding="utf-8")
    )
    assert progress["status"] == "completed"
    assert any(event["step"] == "恢复 OpenCode" for event in progress["events"])
    assert (
        fake_social_card_runtime
        / "data"
        / created["id"]
        / ".session"
    ).read_text(encoding="utf-8").strip() == "ses_test_social_card_repair"
    argv_lines = (
        fake_social_card_runtime
        / "data"
        / created["id"]
        / ".retry-argv.jsonl"
    ).read_text(encoding="utf-8").splitlines()
    resumed_argv = [json.loads(line) for line in argv_lines if "--session" in json.loads(line)]
    assert resumed_argv
    assert resumed_argv[0][-1] == "继续"

    log_text = (
        fake_social_card_runtime
        / "data"
        / created["id"]
        / "logs"
        / "opencode.log"
    ).read_text(encoding="utf-8")
    assert "Xiaohongshu social card generation resume" in log_text
