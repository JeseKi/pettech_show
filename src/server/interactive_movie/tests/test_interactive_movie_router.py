# -*- coding: utf-8 -*-
from __future__ import annotations

from http import HTTPStatus
from typing import Any

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.config import global_config
from src.server.interactive_movie import service as movie_service


def _create_user(test_db_session, username: str) -> User:
    user = User(username=username, email=f"{username}@example.com")
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


@pytest.fixture
def fake_s3_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(global_config, "interactive_movie_s3_endpoint_url", "https://cos.example.com")
    monkeypatch.setattr(global_config, "interactive_movie_s3_region_name", "ap-guangzhou")
    monkeypatch.setattr(global_config, "interactive_movie_s3_bucket", "movie-bucket")
    monkeypatch.setattr(global_config, "interactive_movie_s3_access_key_id", "secret-id")
    monkeypatch.setattr(global_config, "interactive_movie_s3_secret_access_key", "secret-key")
    monkeypatch.setattr(global_config, "interactive_movie_s3_prefix", "movie-assets")
    monkeypatch.setattr(global_config, "interactive_movie_s3_public_base_url", "https://cdn.example.com")
    monkeypatch.setattr(global_config, "interactive_movie_max_video_upload_mb", 10)


def test_upload_scene_video_to_s3(
    test_client,
    test_db_session,
    fake_s3_config,
    monkeypatch: pytest.MonkeyPatch,
):
    fake_client = _FakeS3Client()
    monkeypatch.setattr(movie_service, "_s3_client", lambda _config: fake_client)
    user = _create_user(test_db_session, "interactive_movie_owner")

    resp = test_client.post(
        "/api/interactive-movie/videos",
        headers=_auth_headers(user),
        files={"file": ("scene.mp4", b"video-data", "video/mp4")},
    )

    assert resp.status_code == HTTPStatus.CREATED, resp.text
    payload = resp.json()
    assert payload["filename"] == "scene.mp4"
    assert payload["content_type"] == "video/mp4"
    assert payload["size"] == len(b"video-data")
    assert payload["object_key"].startswith("videos/")
    assert payload["object_key"].endswith(".mp4")
    assert payload["storage_uri"].startswith("s3://movie-bucket/movie-assets/videos/")
    assert payload["url"].startswith("https://cdn.example.com/movie-assets/videos/")
    assert fake_client.put_calls[0]["Bucket"] == "movie-bucket"
    assert fake_client.put_calls[0]["Body"] == b"video-data"
    assert fake_client.put_calls[0]["ContentType"] == "video/mp4"


def test_upload_scene_video_rejects_non_video(
    test_client,
    test_db_session,
    fake_s3_config,
):
    user = _create_user(test_db_session, "interactive_movie_bad_upload")

    resp = test_client.post(
        "/api/interactive-movie/videos",
        headers=_auth_headers(user),
        files={"file": ("notes.txt", b"not a video", "text/plain")},
    )

    assert resp.status_code == HTTPStatus.BAD_REQUEST
    assert resp.json()["detail"] == "只支持上传视频文件"


def test_project_create_sync_and_patch(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_project_owner")
    headers = _auth_headers(user)
    document = _project_document("movie-cloud-a")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created = create_resp.json()
    assert created["version"] == 1
    assert created["content_hash"].startswith("sha256:")
    assert created["document"]["scenes"][0]["title"] == "开场"

    sync_resp = test_client.get(
        "/api/interactive-movie/projects/movie-cloud-a/sync-state",
        headers=headers,
    )
    assert sync_resp.status_code == HTTPStatus.OK, sync_resp.text
    assert sync_resp.json()["content_hash"] == created["content_hash"]

    patch_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-cloud-a",
        headers=headers,
        json={
            "base_version": created["version"],
            "base_hash": created["content_hash"],
            "project": {"title": "云端互动电影"},
            "scenes": {
                "upsert": [
                    {
                        "id": "scene-a",
                        "title": "开场新版",
                        "positionX": 120,
                    }
                ],
                "delete": [],
            },
            "choices": {"upsert": [], "delete": []},
            "script_lines": {
                "upsert": [{"id": "line-a", "sceneId": "scene-a", "text": "新的台词"}],
                "delete": [],
            },
            "viewport": {"zoom": 0.8},
            "selected_object": {"type": "scene", "id": "scene-a"},
        },
    )
    assert patch_resp.status_code == HTTPStatus.OK, patch_resp.text
    patched = patch_resp.json()
    assert patched["title"] == "云端互动电影"
    assert patched["version"] == 2
    assert patched["content_hash"] != created["content_hash"]
    assert patched["document"]["scenes"][0]["title"] == "开场新版"
    assert patched["document"]["scenes"][0]["position"]["x"] == 120
    assert patched["document"]["scenes"][0]["script"]["lines"][0]["text"] == "新的台词"
    assert patched["document"]["viewport"]["zoom"] == 0.8

    conflict_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-cloud-a",
        headers=headers,
        json={
            "base_version": created["version"],
            "base_hash": created["content_hash"],
            "project": {"title": "过期保存"},
            "scenes": {"upsert": [], "delete": []},
            "choices": {"upsert": [], "delete": []},
            "script_lines": {"upsert": [], "delete": []},
            "viewport": {},
            "selected_object": {},
        },
    )
    assert conflict_resp.status_code == HTTPStatus.CONFLICT
    assert conflict_resp.json()["detail"]["reason"] == "version_conflict"


class _FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.put_calls.append(kwargs)

    def generate_presigned_url(self, *_args: Any, **_kwargs: Any) -> str:
        return "https://signed.example.com/video.mp4?signature=test"


def _project_document(project_id: str) -> dict[str, Any]:
    return {
        "id": project_id,
        "title": "云端草稿",
        "updatedAt": "2026-06-24T00:00:00+00:00",
        "selectedObject": {"type": "scene", "id": "scene-a"},
        "viewport": {"x": 10, "y": 20, "zoom": 1},
        "scenes": [
            {
                "id": "scene-a",
                "title": "开场",
                "role": "start",
                "position": {"x": 0, "y": 0},
                "media": {"kind": "placeholder", "status": "mock"},
                "script": {
                    "synopsis": "摘要",
                    "visualDescription": "画面",
                    "videoPrompt": "prompt",
                    "promptParts": {"subject": "主角"},
                    "lines": [{"id": "line-a", "speaker": "角色", "text": "台词"}],
                },
            }
        ],
        "choices": [],
    }
