# -*- coding: utf-8 -*-
from __future__ import annotations

from http import HTTPStatus
from typing import Any

import pytest

from src.server.auth import service as auth_service
from src.server.auth.models import User
from src.server.config import global_config
from src.server.interactive_movie import service as movie_service
from src.server.interactive_movie.models import InteractiveMovieRelease


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
    monkeypatch.setattr(global_config, "interactive_movie_storage_backend", "s3")
    monkeypatch.setattr(global_config, "interactive_movie_s3_endpoint_url", "https://cos.example.com")
    monkeypatch.setattr(global_config, "interactive_movie_s3_region_name", "ap-guangzhou")
    monkeypatch.setattr(global_config, "interactive_movie_s3_bucket", "movie-bucket")
    monkeypatch.setattr(global_config, "interactive_movie_s3_access_key_id", "secret-id")
    monkeypatch.setattr(global_config, "interactive_movie_s3_secret_access_key", "secret-key")
    monkeypatch.setattr(global_config, "interactive_movie_s3_prefix", "movie-assets")
    monkeypatch.setattr(global_config, "interactive_movie_s3_public_base_url", "https://cdn.example.com")
    monkeypatch.setattr(global_config, "interactive_movie_max_video_upload_mb", 10)


def test_upload_image_asset_to_local_storage(
    test_client,
    test_db_session,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
):
    monkeypatch.setattr(global_config, "interactive_movie_storage_backend", "local")
    monkeypatch.setattr(global_config, "interactive_movie_local_asset_dir", tmp_path / "movie-assets")
    monkeypatch.setattr(global_config, "interactive_movie_local_asset_base_url", "/api/interactive-movie/assets/local")
    monkeypatch.setattr(global_config, "interactive_movie_max_image_upload_mb", 10)
    user = _create_user(test_db_session, "interactive_movie_local_image")

    resp = test_client.post(
        "/api/interactive-movie/assets/images",
        headers=_auth_headers(user),
        files={"file": ("cover.png", b"image-data", "image/png")},
    )

    assert resp.status_code == HTTPStatus.CREATED, resp.text
    payload = resp.json()
    assert payload["filename"] == "cover.png"
    assert payload["content_type"] == "image/png"
    assert payload["object_key"].startswith("images/")
    assert payload["storage_uri"].startswith("local://images/")
    assert payload["url"].startswith("/api/interactive-movie/assets/local/images/")
    assert (tmp_path / "movie-assets" / payload["object_key"]).read_bytes() == b"image-data"

    asset_resp = test_client.get(payload["url"])
    assert asset_resp.status_code == HTTPStatus.OK
    assert asset_resp.content == b"image-data"


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
    assert payload["url"].startswith("https://cdn.example.com/movie-bucket/movie-assets/videos/")
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
    assert created["document"]["assetNodes"][0]["type"] == "text"
    assert created["document"]["nodeLinks"][0]["from"]["id"] == "scene-a"

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
            "asset_nodes": {
                "upsert": [
                    {
                        "id": "asset-text-a",
                        "title": "文本新版",
                        "text": "## 新文本",
                    }
                ],
                "delete": [],
            },
            "node_links": {
                "upsert": [
                    {
                        "id": "link-a",
                        "fromNodeType": "scene",
                        "fromNodeId": "scene-a",
                        "fromHandle": "right",
                        "toNodeType": "text",
                        "toNodeId": "asset-text-a",
                        "toHandle": "left",
                    }
                ],
                "delete": [],
            },
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
    assert patched["document"]["assetNodes"][0]["title"] == "文本新版"
    assert patched["document"]["assetNodes"][0]["text"] == "## 新文本"
    assert patched["document"]["nodeLinks"][0]["to"]["type"] == "text"
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
            "asset_nodes": {"upsert": [], "delete": []},
            "node_links": {"upsert": [], "delete": []},
            "script_lines": {"upsert": [], "delete": []},
            "viewport": {},
            "selected_object": {},
        },
    )
    assert conflict_resp.status_code == HTTPStatus.CONFLICT
    assert conflict_resp.json()["detail"]["reason"] == "version_conflict"


def test_project_rename_updates_title_version_and_hash(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_rename_owner")
    headers = _auth_headers(user)
    document = _project_document("movie-rename-a")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created = create_resp.json()

    rename_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-rename-a/title",
        headers=headers,
        json={"title": "重命名互动电影"},
    )
    assert rename_resp.status_code == HTTPStatus.OK, rename_resp.text
    renamed = rename_resp.json()
    assert renamed["title"] == "重命名互动电影"
    assert renamed["document"]["title"] == "重命名互动电影"
    assert renamed["version"] == created["version"] + 1
    assert renamed["content_hash"] != created["content_hash"]


def test_create_project_rekeys_ai_generated_script_line_ids(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_ai_line_create")
    headers = _auth_headers(user)
    document = _project_document("movie-ai-line-create")
    document["scenes"][0]["script"]["lines"] = [
        {"id": "line-1", "speaker": "旁白", "text": "第一句"},
        {"id": "line-1", "speaker": "旁白", "text": "第二句"},
        {"id": "line-2", "speaker": "旁白", "text": "第三句"},
    ]

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )

    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    lines = create_resp.json()["document"]["scenes"][0]["script"]["lines"]
    line_ids = [line["id"] for line in lines]
    assert len(line_ids) == len(set(line_ids))
    assert "line-1" not in line_ids
    assert "line-2" not in line_ids
    assert [line["text"] for line in lines] == ["第一句", "第二句", "第三句"]


def test_patch_project_rekeys_colliding_ai_generated_script_line_ids(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_ai_line_patch")
    headers = _auth_headers(user)
    document = _project_document("movie-ai-line-patch")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created = create_resp.json()

    patch_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-ai-line-patch",
        headers=headers,
        json={
            "base_version": created["version"],
            "base_hash": created["content_hash"],
            "project": {},
            "scenes": {"upsert": [], "delete": []},
            "choices": {"upsert": [], "delete": []},
            "asset_nodes": {"upsert": [], "delete": []},
            "node_links": {"upsert": [], "delete": []},
            "script_lines": {
                "upsert": [
                    {
                        "id": "line-1",
                        "sceneId": "scene-a",
                        "speaker": "旁白",
                        "text": "AI 新增台词",
                        "sortOrder": 1,
                    }
                ],
                "delete": [],
            },
            "viewport": {},
            "selected_object": {},
        },
    )

    assert patch_resp.status_code == HTTPStatus.OK, patch_resp.text
    lines = patch_resp.json()["document"]["scenes"][0]["script"]["lines"]
    added = next(line for line in lines if line["text"] == "AI 新增台词")
    assert added["id"] != "line-1"
    assert added["id"].startswith("line-")


def test_public_project_requires_published_release(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_unpublished_owner")
    headers = _auth_headers(user)
    document = _project_document("movie-public-missing")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text

    public_resp = test_client.get("/api/interactive-movie/public/movie-public-missing")

    assert public_resp.status_code == HTTPStatus.NOT_FOUND


def test_publish_release_public_read_switch_close_and_delete(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_publish_owner")
    headers = _auth_headers(user)
    document = _project_document("movie-public-a")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created = create_resp.json()
    assert created["is_published"] is False
    assert created["public_path"] == "/interactive-movie/play/movie-public-a"

    first_publish_resp = test_client.post(
        "/api/interactive-movie/projects/movie-public-a/releases",
        headers=headers,
        json={"base_version": created["version"], "base_hash": created["content_hash"]},
    )
    assert first_publish_resp.status_code == HTTPStatus.CREATED, first_publish_resp.text
    first_publish = first_publish_resp.json()
    first_release = first_publish["release"]
    assert first_release["version_no"] == 1
    assert first_release["is_current"] is True
    assert first_publish["project"]["is_published"] is True
    assert first_publish["project"]["published_version_no"] == 1
    assert first_publish["project"]["public_path"] == "/interactive-movie/play/movie-public-a"

    public_resp = test_client.get("/api/interactive-movie/public/movie-public-a")
    assert public_resp.status_code == HTTPStatus.OK, public_resp.text
    public_payload = public_resp.json()
    assert public_payload["release_id"] == first_release["id"]
    assert public_payload["version_no"] == 1
    assert public_payload["document"]["title"] == "云端草稿"
    assert public_payload["document"]["assetNodes"][1]["type"] == "image"
    assert public_payload["document"]["scenes"][0]["media"]["videoNodeId"] == "asset-video-a"
    assert public_payload["document"]["nodeLinks"][0]["to"]["id"] == "asset-text-a"

    rename_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-public-a/title",
        headers=headers,
        json={"title": "第二版草稿"},
    )
    assert rename_resp.status_code == HTTPStatus.OK, rename_resp.text
    renamed = rename_resp.json()

    second_publish_resp = test_client.post(
        "/api/interactive-movie/projects/movie-public-a/releases",
        headers=headers,
        json={"base_version": renamed["version"], "base_hash": renamed["content_hash"]},
    )
    assert second_publish_resp.status_code == HTTPStatus.CREATED, second_publish_resp.text
    second_publish = second_publish_resp.json()
    second_release = second_publish["release"]
    assert second_release["version_no"] == 2
    assert second_publish["project"]["public_path"] == "/interactive-movie/play/movie-public-a"

    public_second_resp = test_client.get("/api/interactive-movie/public/movie-public-a")
    assert public_second_resp.status_code == HTTPStatus.OK, public_second_resp.text
    assert public_second_resp.json()["release_id"] == second_release["id"]
    assert public_second_resp.json()["document"]["title"] == "第二版草稿"

    switch_resp = test_client.put(
        "/api/interactive-movie/projects/movie-public-a/published-release",
        headers=headers,
        json={"release_id": first_release["id"]},
    )
    assert switch_resp.status_code == HTTPStatus.OK, switch_resp.text
    switched = switch_resp.json()
    assert switched["published_release_id"] == first_release["id"]
    assert switched["published_version_no"] == 1

    public_switched_resp = test_client.get("/api/interactive-movie/public/movie-public-a")
    assert public_switched_resp.status_code == HTTPStatus.OK, public_switched_resp.text
    assert public_switched_resp.json()["release_id"] == first_release["id"]
    assert public_switched_resp.json()["document"]["title"] == "云端草稿"

    draft_resp = test_client.get("/api/interactive-movie/projects/movie-public-a", headers=headers)
    assert draft_resp.status_code == HTTPStatus.OK, draft_resp.text
    assert draft_resp.json()["document"]["title"] == "第二版草稿"

    releases_resp = test_client.get("/api/interactive-movie/projects/movie-public-a/releases", headers=headers)
    assert releases_resp.status_code == HTTPStatus.OK, releases_resp.text
    releases = releases_resp.json()
    assert [release["version_no"] for release in releases] == [2, 1]
    assert {release["version_no"]: release["is_current"] for release in releases} == {1: True, 2: False}

    close_resp = test_client.delete("/api/interactive-movie/projects/movie-public-a/published-release", headers=headers)
    assert close_resp.status_code == HTTPStatus.OK, close_resp.text
    assert close_resp.json()["is_published"] is False
    assert close_resp.json()["published_release_id"] is None

    public_closed_resp = test_client.get("/api/interactive-movie/public/movie-public-a")
    assert public_closed_resp.status_code == HTTPStatus.NOT_FOUND

    releases_after_close_resp = test_client.get("/api/interactive-movie/projects/movie-public-a/releases", headers=headers)
    assert releases_after_close_resp.status_code == HTTPStatus.OK, releases_after_close_resp.text
    assert len(releases_after_close_resp.json()) == 2

    delete_resp = test_client.delete("/api/interactive-movie/projects/movie-public-a", headers=headers)
    assert delete_resp.status_code == HTTPStatus.NO_CONTENT, delete_resp.text
    assert test_db_session.query(InteractiveMovieRelease).filter(InteractiveMovieRelease.project_id == "movie-public-a").count() == 0
    assert test_client.get("/api/interactive-movie/public/movie-public-a").status_code == HTTPStatus.NOT_FOUND


def test_publish_rejects_stale_project_version(test_client, test_db_session):
    user = _create_user(test_db_session, "interactive_movie_publish_conflict")
    headers = _auth_headers(user)
    document = _project_document("movie-public-conflict")

    create_resp = test_client.post(
        "/api/interactive-movie/projects",
        headers=headers,
        json={"title": document["title"], "document": document},
    )
    assert create_resp.status_code == HTTPStatus.CREATED, create_resp.text
    created = create_resp.json()

    rename_resp = test_client.patch(
        "/api/interactive-movie/projects/movie-public-conflict/title",
        headers=headers,
        json={"title": "已有新版"},
    )
    assert rename_resp.status_code == HTTPStatus.OK, rename_resp.text

    stale_publish_resp = test_client.post(
        "/api/interactive-movie/projects/movie-public-conflict/releases",
        headers=headers,
        json={"base_version": created["version"], "base_hash": created["content_hash"]},
    )

    assert stale_publish_resp.status_code == HTTPStatus.CONFLICT
    assert stale_publish_resp.json()["detail"]["reason"] == "version_conflict"


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
                "media": {
                    "kind": "video",
                    "status": "ready",
                    "videoNodeId": "asset-video-a",
                    "coverImageNodeId": "asset-image-a",
                },
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
        "nodeLinks": [
            {
                "id": "link-a",
                "from": {"type": "scene", "id": "scene-a", "handle": "right"},
                "to": {"type": "text", "id": "asset-text-a", "handle": "left"},
            }
        ],
        "assetNodes": [
            {
                "id": "asset-text-a",
                "type": "text",
                "title": "文本素材",
                "position": {"x": 320, "y": 0},
                "text": "# 标题\n\n正文",
                "media": {"status": "empty"},
            },
            {
                "id": "asset-image-a",
                "type": "image",
                "title": "封面图",
                "position": {"x": 640, "y": 0},
                "media": {
                    "url": "https://cdn.example.com/cover.png",
                    "objectKey": "images/cover.png",
                    "storageUri": "s3://bucket/images/cover.png",
                    "contentType": "image/png",
                    "size": 10,
                    "status": "ready",
                },
            },
            {
                "id": "asset-video-a",
                "type": "video",
                "title": "画面视频",
                "position": {"x": 960, "y": 0},
                "media": {
                    "url": "https://cdn.example.com/video.mp4",
                    "objectKey": "videos/video.mp4",
                    "storageUri": "s3://bucket/videos/video.mp4",
                    "contentType": "video/mp4",
                    "size": 20,
                    "status": "ready",
                },
            },
        ],
    }
