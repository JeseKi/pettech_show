"""normalize interactive movie media public urls

Revision ID: 2026062404
Revises: 2026062403
Create Date: 2026-06-24

"""
from __future__ import annotations

import json
from typing import Any, Sequence, Union
from urllib.parse import quote, unquote, urlsplit, urlunsplit

from alembic import op
import sqlalchemy as sa


revision: str = "2026062404"
down_revision: Union[str, Sequence[str], None] = "2026062403"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade data."""
    bind = op.get_bind()
    if _table_exists(bind, "interactive_movie_scenes"):
        _normalize_scene_media_urls(bind)
    if _table_exists(bind, "interactive_movie_projects"):
        _normalize_project_canvas_media_urls(bind)


def downgrade() -> None:
    """Downgrade data."""
    # Data normalization is intentionally not reversed.


def _normalize_scene_media_urls(bind: sa.engine.Connection) -> None:
    rows = bind.execute(sa.text(
        """
        SELECT id, media_url, media_storage_uri
        FROM interactive_movie_scenes
        WHERE media_url != '' AND media_storage_uri LIKE 's3://%'
        """
    )).mappings().all()
    for row in rows:
        normalized_url = _normalize_media_url(row["media_url"], row["media_storage_uri"])
        if not normalized_url:
            continue
        bind.execute(
            sa.text("UPDATE interactive_movie_scenes SET media_url = :media_url WHERE id = :id"),
            {"media_url": normalized_url, "id": row["id"]},
        )


def _normalize_project_canvas_media_urls(bind: sa.engine.Connection) -> None:
    rows = bind.execute(sa.text(
        """
        SELECT id, canvas_json
        FROM interactive_movie_projects
        WHERE canvas_json != ''
        """
    )).mappings().all()
    for row in rows:
        try:
            document = json.loads(row["canvas_json"])
        except (TypeError, json.JSONDecodeError):
            continue
        if not isinstance(document, dict):
            continue
        if not _normalize_document_media_urls(document):
            continue
        bind.execute(
            sa.text("UPDATE interactive_movie_projects SET canvas_json = :canvas_json WHERE id = :id"),
            {"canvas_json": json.dumps(document, ensure_ascii=False), "id": row["id"]},
        )


def _normalize_document_media_urls(document: dict[str, Any]) -> bool:
    changed = False
    for scene in document.get("scenes") or []:
        if not isinstance(scene, dict):
            continue
        media = scene.get("media")
        if not isinstance(media, dict):
            continue
        media_url = media.get("url")
        storage_uri = media.get("storageUri") or media.get("storage_uri")
        if not isinstance(media_url, str) or not isinstance(storage_uri, str):
            continue
        normalized_url = _normalize_media_url(media_url, storage_uri)
        if normalized_url:
            media["url"] = normalized_url
            changed = True
    return changed


def _normalize_media_url(media_url: str, storage_uri: str) -> str | None:
    parsed_storage = _parse_storage_uri(storage_uri)
    if not parsed_storage:
        return None
    bucket, full_key = parsed_storage
    parsed_url = urlsplit(media_url)
    if parsed_url.scheme not in {"http", "https"} or not parsed_url.netloc:
        return None

    key_segments = [segment for segment in full_key.split("/") if segment]
    path_segments = [unquote(segment) for segment in parsed_url.path.split("/") if segment]
    if not key_segments or len(path_segments) < len(key_segments):
        return None
    if path_segments[-len(key_segments):] != key_segments:
        return None

    prefix_segments = path_segments[:-len(key_segments)]
    if prefix_segments and prefix_segments[-1] == bucket:
        return None

    normalized_segments = [*prefix_segments, bucket, *key_segments]
    normalized_path = "/" + "/".join(quote(segment, safe="") for segment in normalized_segments)
    return urlunsplit((parsed_url.scheme, parsed_url.netloc, normalized_path, parsed_url.query, parsed_url.fragment))


def _parse_storage_uri(storage_uri: str) -> tuple[str, str] | None:
    if not storage_uri.startswith("s3://"):
        return None
    without_scheme = storage_uri[len("s3://"):]
    bucket, separator, full_key = without_scheme.partition("/")
    if not bucket or not separator or not full_key:
        return None
    return bucket, full_key


def _table_exists(bind: sa.engine.Connection, table_name: str) -> bool:
    return sa.inspect(bind).has_table(table_name)
