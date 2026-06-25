# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import asyncio
from datetime import datetime, timezone
from http import HTTPStatus
from pathlib import Path

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.auth.schemas import UserRole
from src.server.config import global_config
from src.server.daily_writer.models import DailyWriterJob
from src.server.distribution import service as distribution_service
from src.server.distribution.service import remote as distribution_remote
from src.server.social_card_videos.models import SocialCardVideoJob
from src.server.social_cards.models import SocialCardJob


def _create_admin(test_db_session, username: str = "distribution_admin") -> User:
    user = User(
        username=username,
        email=f"{username}@example.com",
        role=UserRole.ADMIN,
    )
    user.set_password("Password123")
    test_db_session.add(user)
    test_db_session.commit()
    test_db_session.refresh(user)
    return user


def _auth_headers(user: User) -> dict[str, str]:
    token = auth_service.create_access_token(
        {"sub": user.username, "scope": auth_service.get_user_scopes(user), "tv": user.token_version}
    )
    return {"Authorization": f"Bearer {token}"}


def _remote_directory() -> tuple[list[dict], dict]:
    accounts = [
        {
            "id": 10,
            "name": "运营 A",
            "accounts": [
                {
                    "id": 101,
                    "project_ids": [1],
                    "theme_id": 11,
                    "platform": "公众号",
                    "account_name": "文章号",
                    "publication_type": "article",
                    "is_active": True,
                },
                {
                    "id": 102,
                    "project_ids": [1],
                    "theme_id": 11,
                    "platform": "小红书",
                    "account_name": "图文号",
                    "publication_type": "image_text",
                    "is_active": True,
                },
                {
                    "id": 103,
                    "project_ids": [1],
                    "theme_id": 11,
                    "platform": "视频号",
                    "account_name": "视频号",
                    "publication_type": "video",
                    "is_active": True,
                },
            ],
        }
    ]
    project_themes = {
        "projects": [{"id": 1, "name": "宠物科技", "code": "pet", "theme_ids": [11]}],
        "themes": [{"id": 11, "name": "增长", "project_ids": [1]}],
    }
    return accounts, project_themes


def _create_daily_writer_job(test_db_session, root: Path, user: User) -> DailyWriterJob:
    job_id = "20260625120000_00000001_daily_writer"
    workdir = root / "data" / job_id
    article_dir = workdir / "main" / "260625" / "260625_pet_growth"
    upload_dir = article_dir / "artwork" / "upload_ready"
    upload_dir.mkdir(parents=True)
    (article_dir / "main.md").write_text("# 主稿标题\n\n正文\n", encoding="utf-8")
    (article_dir / "metadata.json").write_text(
        json.dumps(
            {
                "output_id": "260625_pet_growth",
                "topic": "宠物增长",
                "pain_point": "复购低",
                "solution": "内容种草",
                "hook": "先解决信任",
                "article": {
                    "role": "main",
                    "file": "main.md",
                    "title": "宠物增长主稿",
                    "summary": "主稿摘要",
                    "tags": ["宠物"],
                    "search_intents": [{"role": "primary", "keyword": "宠物增长"}],
                    "materials_used": [],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    image = upload_dir / "cover-21x9.jpg"
    image.write_bytes(b"\xff\xd8\xff\xd9")
    (upload_dir / "manifest.json").write_text(
        json.dumps(
            {
                "images": [
                    {
                        "source": "main/260625/260625_pet_growth/artwork/cover/images/cover.png",
                        "upload_path": image.relative_to(workdir).as_posix(),
                    }
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    variants_dir = article_dir / "variants" / "angle-1" / "output"
    variants_dir.mkdir(parents=True)
    (variants_dir / "others.md").write_text("# 变体标题\n\n变体正文\n", encoding="utf-8")
    (variants_dir / "metadata.json").write_text(
        json.dumps(
            {
                "output_id": "260625_pet_growth_v1",
                "audience_label": "变体角度",
                "article": {
                    "role": "variant",
                    "file": "others.md",
                    "title": "宠物增长变体",
                    "summary": "变体摘要",
                    "tags": ["宠物"],
                    "search_intents": [{"keyword": "宠物内容"}],
                },
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    job = DailyWriterJob(
        id=job_id,
        owner_user_id=user.id,
        source_seed_matrix_job_id="seed-job",
        source_aiwiki_job_id="aiwiki-job",
        seed_id="S001",
        status="completed",
        message="done",
        workdir=workdir.as_posix(),
        row_json="{}",
        params_json=json.dumps({"generate_variants": True}, ensure_ascii=False),
        article_path="main/260625/260625_pet_growth/main.md",
        metadata_path="main/260625/260625_pet_growth/metadata.json",
        summary_json="{}",
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


def _create_social_card_job(test_db_session, root: Path, user: User) -> SocialCardJob:
    job_id = "20260625130000_00000001_social_cards"
    workdir = root / "data" / job_id
    xhs_dir = workdir / "xhs_guizang"
    output_dir = xhs_dir / "output"
    output_dir.mkdir(parents=True)
    image = output_dir / "xhs-01.png"
    image.write_bytes(b"\x89PNG\r\n\x1a\n")
    (xhs_dir / "main.md").write_text(
        "# 图文标题\n\n![card](social-card-image:card_01)\n",
        encoding="utf-8",
    )
    (xhs_dir / "manifest.json").write_text(
        json.dumps({"uploaded_images": [{"file": "output/xhs-01.png"}]}, ensure_ascii=False),
        encoding="utf-8",
    )
    (xhs_dir / "index.html").write_text("<html></html>", encoding="utf-8")
    job = SocialCardJob(
        id=job_id,
        owner_user_id=user.id,
        source_daily_writer_job_id="daily-job",
        status="completed",
        message="done",
        workdir=workdir.as_posix(),
        params_json=json.dumps({"post_count": 1, "cards_per_post": 1}, ensure_ascii=False),
        summary_json="{}",
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


def _create_social_card_video_job(test_db_session, root: Path, user: User) -> SocialCardVideoJob:
    source_job = _create_social_card_job(test_db_session, root, user)
    job_id = "20260625140000_00000001_social_card_videos"
    workdir = root / "data" / job_id
    video_dir = workdir / "source" / "xhs_guizang" / "video"
    video_dir.mkdir(parents=True)
    (video_dir / "slideshow.mp4").write_bytes(b"fake mp4 video")
    (video_dir.parent / "video.md").write_text(
        "# 轮播视频\n\n[本地视频：slideshow.mp4](video/slideshow.mp4)\n",
        encoding="utf-8",
    )
    job = SocialCardVideoJob(
        id=job_id,
        owner_user_id=user.id,
        source_social_card_job_id=source_job.id,
        status="completed",
        message="done",
        workdir=workdir.as_posix(),
        params_json=json.dumps({"title": "宠物增长轮播视频"}, ensure_ascii=False),
        summary_json=json.dumps({"video_count": 1}, ensure_ascii=False),
        created_at=datetime.now(timezone.utc),
        finished_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    test_db_session.add(job)
    test_db_session.commit()
    test_db_session.refresh(job)
    return job


@pytest.fixture
def distribution_runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(global_config, "project_root", tmp_path)
    monkeypatch.setattr(global_config, "info_distribution_base_url", "https://distribution.example.test")
    monkeypatch.setattr(global_config, "info_distribution_api_key", "adv1_test")
    monkeypatch.setattr(global_config, "info_distribution_public_asset_base_url", "https://pettech.example.test")
    return tmp_path


def test_remote_directory_requires_config(test_client, test_db_session, monkeypatch: pytest.MonkeyPatch):
    admin = _create_admin(test_db_session, "distribution_config_admin")
    monkeypatch.setattr(global_config, "info_distribution_base_url", "")
    monkeypatch.setattr(global_config, "info_distribution_api_key", "")

    resp = test_client.get("/api/distribution/remote-directory", headers=_auth_headers(admin))

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert "INFO_DISTRIBUTION_BASE_URL" in resp.json()["detail"]


def test_fetch_remote_directory_sends_api_key(monkeypatch: pytest.MonkeyPatch):
    requests: list[dict] = []

    class FakeResponse:
        def __init__(self, data):
            self._data = data
            self.text = json.dumps(data)

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def get(self, url, headers):
            requests.append({"url": url, "headers": headers})
            if url.endswith("/accounts"):
                return FakeResponse([])
            return FakeResponse({"projects": [], "themes": []})

    monkeypatch.setattr(global_config, "info_distribution_base_url", "https://distribution.example.test")
    monkeypatch.setattr(global_config, "info_distribution_api_key", "adv1_secret")
    monkeypatch.setattr(distribution_remote.httpx, "AsyncClient", FakeAsyncClient)

    accounts, project_themes = asyncio.run(distribution_remote.fetch_remote_directory())

    assert accounts == []
    assert project_themes == {"projects": [], "themes": []}
    assert [request["headers"]["X-API-Key"] for request in requests] == ["adv1_secret", "adv1_secret"]


def test_daily_writer_plan_replaces_artwork_urls(
    test_client, test_db_session, distribution_runtime: Path, monkeypatch: pytest.MonkeyPatch
):
    admin = _create_admin(test_db_session, "distribution_daily_admin")
    job = _create_daily_writer_job(test_db_session, distribution_runtime, admin)

    async def fake_directory():
        return _remote_directory()

    monkeypatch.setattr(distribution_service, "fetch_remote_directory", fake_directory)

    resp = test_client.post(
        "/api/distribution/uploads/plan",
        headers=_auth_headers(admin),
        json={
            "source_type": "daily_writer",
            "source_job_id": job.id,
            "project_id": 1,
            "theme_id": 11,
            "scheduled_date": "2026-06-26",
            "per_account_count": 1,
        },
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    plan = resp.json()
    assert plan["upload_type"] == "article"
    assert plan["item_count"] == 1
    markdown = plan["batches"][0]["items"][0]["markdown_content"]
    assert "https://pettech.example.test/api/distribution/assets/daily-writer-artwork" in markdown
    assert "daily-writer-artwork:" not in markdown
    assert plan["batches"][0]["items"][0]["metadata"]["upload_context"]["source_job_id"] == job.id


def test_social_card_plan_replaces_image_urls(
    test_client, test_db_session, distribution_runtime: Path, monkeypatch: pytest.MonkeyPatch
):
    admin = _create_admin(test_db_session, "distribution_social_admin")
    job = _create_social_card_job(test_db_session, distribution_runtime, admin)

    async def fake_directory():
        return _remote_directory()

    monkeypatch.setattr(distribution_service, "fetch_remote_directory", fake_directory)

    resp = test_client.post(
        "/api/distribution/uploads/plan",
        headers=_auth_headers(admin),
        json={
            "source_type": "social_cards",
            "source_job_id": job.id,
            "project_id": 1,
            "theme_id": 11,
            "scheduled_date": "2026-06-26",
            "per_account_count": 1,
        },
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    plan = resp.json()
    assert plan["upload_type"] == "image_text"
    markdown = plan["batches"][0]["items"][0]["markdown_content"]
    assert "https://pettech.example.test/api/distribution/assets/social-card-image" in markdown
    assert "social-card-image:" not in markdown


def test_social_card_video_plan_exposes_signed_video_url(
    test_client, test_db_session, distribution_runtime: Path, monkeypatch: pytest.MonkeyPatch
):
    admin = _create_admin(test_db_session, "distribution_video_admin")
    job = _create_social_card_video_job(test_db_session, distribution_runtime, admin)

    async def fake_directory():
        return _remote_directory()

    monkeypatch.setattr(distribution_service, "fetch_remote_directory", fake_directory)

    resp = test_client.post(
        "/api/distribution/uploads/plan",
        headers=_auth_headers(admin),
        json={
            "source_type": "social_card_videos",
            "source_job_id": job.id,
            "project_id": 1,
            "theme_id": 11,
            "scheduled_date": "2026-06-26",
            "per_account_count": 1,
        },
    )

    assert resp.status_code == HTTPStatus.OK, resp.text
    plan = resp.json()
    assert plan["upload_type"] == "video"
    assert plan["item_count"] == 1
    item = plan["batches"][0]["items"][0]
    markdown = item["markdown_content"]
    assert "https://pettech.example.test/api/distribution/assets/social-card-video" in markdown
    assert "video/slideshow.mp4" not in markdown
    assert item["metadata"]["media_type"] == "video"
    assert item["metadata"]["video_url"].startswith(
        "https://pettech.example.test/api/distribution/assets/social-card-video"
    )
    assert item["metadata"]["upload_context"]["distribution_type"] == "video"

    signature = distribution_service.sign_asset("social-card-video", job.id, "post_01")
    video_resp = test_client.get(
        f"/api/distribution/assets/social-card-video/{job.id}/post_01?sig={signature}"
    )
    assert video_resp.status_code == HTTPStatus.OK, video_resp.text
    assert video_resp.headers["content-type"].startswith("video/mp4")
    assert video_resp.content.startswith(b"fake mp4")


def test_upload_history_skips_duplicates_and_ignore_history_reuploads(
    test_client, test_db_session, distribution_runtime: Path, monkeypatch: pytest.MonkeyPatch
):
    admin = _create_admin(test_db_session, "distribution_upload_admin")
    job = _create_daily_writer_job(test_db_session, distribution_runtime, admin)

    async def fake_directory():
        return _remote_directory()

    async def fake_upload_batches(plan):
        return [
            {
                "account": batch["account"],
                "created_count": len(batch["items"]),
                "response": [
                    {"id": 9000 + index, "title": item["title"]}
                    for index, item in enumerate(batch["items"], start=1)
                ],
            }
            for batch in plan["batches"]
        ]

    monkeypatch.setattr(distribution_service, "fetch_remote_directory", fake_directory)
    monkeypatch.setattr("src.server.distribution.service.core.upload_batches", fake_upload_batches)

    payload = {
        "source_type": "daily_writer",
        "source_job_id": job.id,
        "project_id": 1,
        "theme_id": 11,
        "scheduled_date": "2026-06-26",
        "per_account_count": 2,
    }
    upload_resp = test_client.post("/api/distribution/uploads", headers=_auth_headers(admin), json=payload)
    assert upload_resp.status_code == HTTPStatus.CREATED, upload_resp.text
    assert upload_resp.json()["job"]["status"] == "completed"

    skipped_resp = test_client.post(
        "/api/distribution/uploads/plan",
        headers=_auth_headers(admin),
        json=payload,
    )
    assert skipped_resp.status_code == HTTPStatus.OK, skipped_resp.text
    skipped_plan = skipped_resp.json()
    assert skipped_plan["item_count"] == 0
    assert skipped_plan["skipped"][0]["reason"] == "已上传过，默认跳过"

    reupload_resp = test_client.post(
        "/api/distribution/uploads/plan",
        headers=_auth_headers(admin),
        json={**payload, "ignore_history": True},
    )
    assert reupload_resp.status_code == HTTPStatus.OK, reupload_resp.text
    assert reupload_resp.json()["item_count"] == 2


def test_signed_asset_endpoint_accepts_valid_signature_and_rejects_invalid(
    test_client, test_db_session, distribution_runtime: Path
):
    admin = _create_admin(test_db_session, "distribution_asset_admin")
    job = _create_daily_writer_job(test_db_session, distribution_runtime, admin)
    signature = distribution_service.sign_asset("daily-writer-artwork", job.id, "cover_01")

    ok_resp = test_client.get(
        f"/api/distribution/assets/daily-writer-artwork/{job.id}/cover_01?sig={signature}"
    )
    assert ok_resp.status_code == HTTPStatus.OK, ok_resp.text
    assert ok_resp.headers["content-type"].startswith("image/")

    bad_resp = test_client.get(
        f"/api/distribution/assets/daily-writer-artwork/{job.id}/cover_01?sig=bad"
    )
    assert bad_resp.status_code == HTTPStatus.FORBIDDEN
