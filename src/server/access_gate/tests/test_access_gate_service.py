# -*- coding: utf-8 -*-

from pathlib import Path

from src.server.access_gate import service


def test_initialize_access_token_writes_token_file(tmp_path: Path):
    token = service.initialize_access_token(tmp_path)

    assert token
    assert (tmp_path / ".token").read_text(encoding="utf-8").strip() == token


def test_validates_token_from_file(tmp_path: Path):
    (tmp_path / ".token").write_text("expected-token\n", encoding="utf-8")

    assert service.is_valid_token(tmp_path, "expected-token") is True
    assert service.is_valid_token(tmp_path, "wrong-token") is False


def test_public_request_path_allows_player_and_public_movie_api():
    assert service.is_public_request_path("/interactive-movie/play/project-1") is True
    assert service.is_public_request_path("/api/interactive-movie/public/project-1") is True
    assert service.is_public_request_path("/api/interactive-movie/assets/local/a.mp4") is True
    assert service.is_public_request_path("/assets/index.js") is True

    assert service.is_public_request_path("/") is False
    assert service.is_public_request_path("/login") is False
    assert service.is_public_request_path("/api/auth/login") is False
