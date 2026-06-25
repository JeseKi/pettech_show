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
from src.server.social_cards.models import SocialCardJob
from src.server.social_card_videos.queue_state import reset_queue_for_tests


@pytest.fixture
def fake_social_card_video_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    fake_opencode = tmp_path / "fake_social_card_video_opencode.py"
    fake_opencode.write_text(
        """
from __future__ import annotations

import json
from pathlib import Path

root = Path.cwd()
config = json.loads((root / "video-config.json").read_text(encoding="utf-8"))

def jobs_from_config() -> list[dict]:
    if "jobs" in config:
        defaults = config.get("defaults") or {}
        return [{**defaults, **job} for job in config["jobs"]]
    return [config]

def read_events() -> list[object]:
    progress_path = root / "progress.json"
    if not progress_path.exists():
        return []
    progress = json.loads(progress_path.read_text(encoding="utf-8"))
    events = progress.get("events")
    return list(events) if isinstance(events, list) else []

def write_progress(status: str, current_step: str, events: list[object]) -> None:
    (root / "progress.json").write_text(
        json.dumps(
            {"status": status, "current_step": current_step, "events": events},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

assert (root / ".agents" / "skills" / "xhs-slideshow-video-maker" / "SKILL.md").is_file()
events = read_events()
events.append({"event": "开始", "step": "轮播视频", "summary": "开始生成视频"})
write_progress("running", "轮播视频", events)

for job in jobs_from_config():
    image_dir = root / job["image_dir"]
    assert image_dir.is_dir()
    assert list(image_dir.glob("*.png"))
    if job.get("bgm_source"):
        assert job["bgm_source"] == "uploads/bgm.mp3"
        assert float(job["bgm_start"]) == 12.5
        assert (root / job["bgm_source"]).is_file()
    output_dir = root / job["output_dir"]
    video_dir = output_dir / "video"
    video_dir.mkdir(parents=True, exist_ok=True)
    (video_dir / "slideshow.mp4").write_bytes(b"fake mp4 " + job["label"].encode("utf-8"))
    (output_dir / "video.md").write_text(
        f"# {job['label']} 视频\\n\\n[本地视频：slideshow.mp4](video/slideshow.mp4)\\n",
        encoding="utf-8",
    )

events.append({"event": "完成", "step": "轮播视频", "summary": "已生成视频"})
events.append({"event": "完成", "step": "全部", "summary": "任务完成"})
write_progress("completed", "任务完成", events)
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
    skill_dir = tmp_path / ".agents" / "skills" / "xhs-slideshow-video-maker"
    skill_dir.mkdir(parents=True)
    (skill_dir / "SKILL.md").write_text("# fake video skill\n", encoding="utf-8")
    (skill_dir / "scripts").mkdir()
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


def _create_social_card_source(
    test_db_session,
    root: Path,
    user: User,
    *,
    status: str = "completed",
) -> SocialCardJob:
    job_id = f"20260625120000_{user.id:08x}_social_cards"
    workdir = root / "data" / job_id
    for deck in (
        workdir / "xhs_guizang",
        workdir / "xhs_guizang_variants" / "variant-01",
    ):
        output = deck / "output"
        output.mkdir(parents=True)
        for index in range(1, 3):
            (output / f"xhs-{index:02d}.png").write_bytes(b"\x89PNG\r\n\x1a\n")
        (deck / "main.md").write_text("# 图文\n", encoding="utf-8")
        (deck / "manifest.json").write_text(
            json.dumps(
                {"uploaded_images": [{"file": f"output/xhs-{index:02d}.png"} for index in range(1, 3)]},
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        (deck / "index.html").write_text("<html></html>", encoding="utf-8")
    job = SocialCardJob(
        id=job_id,
        owner_user_id=user.id,
        source_daily_writer_job_id=f"20260625110000_{user.id:08x}_daily_writer",
        status=status,
        message="source cards",
        workdir=workdir.as_posix(),
        params_json=json.dumps({"post_count": 2, "cards_per_post": 2}, ensure_ascii=False),
        summary_json=json.dumps({"post_count": 2, "image_count": 4}, ensure_ascii=False),
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
        resp = test_client.get(f"/api/social-card-videos/jobs/{job_id}", headers=headers)
        assert resp.status_code == HTTPStatus.OK, resp.text
        latest = resp.json()
        if latest["status"] in {"completed", "failed"}:
            return latest
        time.sleep(0.05)
    raise AssertionError(f"social card video job did not finish: {latest}")


def test_create_social_card_video_job_with_bgm_and_download_result(
    test_client, test_db_session, fake_social_card_video_runtime: Path
):
    user = _create_user(test_db_session, "social_card_video_owner")
    source = _create_social_card_source(test_db_session, fake_social_card_video_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/social-card-videos/jobs",
        headers=headers,
        data={
            "source_social_card_job_id": source.id,
            "title": "药食同源轻创业",
            "voice_text": "普通人也能看懂的小红书轮播视频。",
            "bgm_start": "12.5",
        },
        files={"bgm_file": ("bgm.mp3", b"fake audio", "audio/mpeg")},
    )
    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["source_social_card_job_id"] == source.id
    assert created["title"] == "药食同源轻创业"
    assert created["params"]["has_bgm"] is True
    assert created["params"]["bgm_start"] == 12.5

    update_resp = test_client.patch(
        f"/api/social-card-videos/jobs/{created['id']}",
        headers=headers,
        json={"title": "轮播视频分发任务"},
    )
    assert update_resp.status_code == HTTPStatus.OK, update_resp.text
    assert update_resp.json()["title"] == "轮播视频分发任务"
    list_resp = test_client.get("/api/social-card-videos/jobs", headers=headers)
    assert list_resp.status_code == HTTPStatus.OK, list_resp.text
    assert list_resp.json()["items"][0]["title"] == "轮播视频分发任务"

    config = json.loads(
        (
            fake_social_card_video_runtime
            / "data"
            / created["id"]
            / "video-config.json"
        ).read_text(encoding="utf-8")
    )
    assert config["defaults"]["bgm_source"] == "uploads/bgm.mp3"
    assert config["defaults"]["bgm_start"] == 12.5
    assert len(config["jobs"]) == 2

    finished = _wait_for_terminal_status(test_client, created["id"], headers)
    assert finished["status"] == "completed", finished
    assert finished["summary"]["video_count"] == 2

    result_resp = test_client.get(
        f"/api/social-card-videos/jobs/{created['id']}/result",
        headers=headers,
    )
    assert result_resp.status_code == HTTPStatus.OK, result_resp.text
    result = result_resp.json()
    assert [video["key"] for video in result["videos"]] == ["post_01", "post_02"]
    assert "social-card-video:post_01" in result["markdown"]

    video_resp = test_client.get(
        f"/api/social-card-videos/jobs/{created['id']}/videos/post_02",
        headers=headers,
    )
    assert video_resp.status_code == HTTPStatus.OK, video_resp.text
    assert video_resp.headers["content-type"] == "video/mp4"
    assert video_resp.content.startswith(b"fake mp4")

    other_user = _create_user(test_db_session, "social_card_video_other")
    other_resp = test_client.get(
        f"/api/social-card-videos/jobs/{created['id']}/videos/post_01",
        headers=_auth_headers(other_user),
    )
    assert other_resp.status_code == HTTPStatus.NOT_FOUND

    download_resp = test_client.get(
        f"/api/social-card-videos/jobs/{created['id']}/download",
        headers=headers,
    )
    assert download_resp.status_code == HTTPStatus.OK, download_resp.text
    zip_path = fake_social_card_video_runtime / "video-download.zip"
    zip_path.write_bytes(download_resp.content)
    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "source/xhs_guizang/video/slideshow.mp4" in names
    assert "source/xhs_guizang/video.md" in names
    assert "source/xhs_guizang_variants/variant-01/video/slideshow.mp4" in names

    delete_resp = test_client.delete(
        f"/api/social-card-videos/jobs/{created['id']}",
        headers=headers,
    )
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert not (fake_social_card_video_runtime / "data" / created["id"]).exists()


def test_rejects_unfinished_or_inaccessible_social_card_source(
    test_client, test_db_session, fake_social_card_video_runtime: Path
):
    user = _create_user(test_db_session, "social_card_video_pending")
    source = _create_social_card_source(
        test_db_session,
        fake_social_card_video_runtime,
        user,
        status="running",
    )
    headers = _auth_headers(user)

    resp = test_client.post(
        "/api/social-card-videos/jobs",
        headers=headers,
        data={
            "source_social_card_job_id": source.id,
            "title": "标题",
            "voice_text": "配音文案",
            "bgm_start": "0",
        },
    )
    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "已完成" in resp.json()["detail"]

    other_user = _create_user(test_db_session, "social_card_video_no_access")
    other_resp = test_client.post(
        "/api/social-card-videos/jobs",
        headers=_auth_headers(other_user),
        data={
            "source_social_card_job_id": source.id,
            "title": "标题",
            "voice_text": "配音文案",
            "bgm_start": "0",
        },
    )
    assert other_resp.status_code == HTTPStatus.NOT_FOUND


def test_allows_missing_voice_text_for_agent_generation(
    test_client, test_db_session, fake_social_card_video_runtime: Path
):
    user = _create_user(test_db_session, "social_card_video_auto_voice")
    source = _create_social_card_source(test_db_session, fake_social_card_video_runtime, user)
    headers = _auth_headers(user)

    create_resp = test_client.post(
        "/api/social-card-videos/jobs",
        headers=headers,
        data={
            "source_social_card_job_id": source.id,
            "title": "自动生成配音文案",
            "bgm_start": "62",
        },
    )

    assert create_resp.status_code == HTTPStatus.ACCEPTED, create_resp.text
    created = create_resp.json()
    assert created["params"]["voice_text"] == ""
    assert created["params"]["bgm_start"] == 62
    config = json.loads(
        (
            fake_social_card_video_runtime
            / "data"
            / created["id"]
            / "video-config.json"
        ).read_text(encoding="utf-8")
    )
    assert config["defaults"]["voice_text"] == ""
