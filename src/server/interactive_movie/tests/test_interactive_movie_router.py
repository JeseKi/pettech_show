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


class _FakeS3Client:
    def __init__(self) -> None:
        self.put_calls: list[dict[str, Any]] = []

    def put_object(self, **kwargs: Any) -> None:
        self.put_calls.append(kwargs)

    def generate_presigned_url(self, *_args: Any, **_kwargs: Any) -> str:
        return "https://signed.example.com/video.mp4?signature=test"
