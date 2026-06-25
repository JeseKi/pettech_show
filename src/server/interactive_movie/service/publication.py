# -*- coding: utf-8 -*-
"""Publication helpers for interactive movie releases."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from ..models import InteractiveMovieProject, InteractiveMovieRelease


def delete_project_releases(db: Session, project_id: str) -> None:
    db.query(InteractiveMovieRelease).filter(
        InteractiveMovieRelease.project_id == project_id
    ).delete(synchronize_session=False)


def set_project_publication(
    project: InteractiveMovieProject,
    release_id: str,
    published_at: datetime,
) -> None:
    project.is_published = True
    project.published_release_id = release_id
    project.published_at = published_at
    project.version += 1
    project.updated_at = published_at


def publication_fields(db: Session, project: InteractiveMovieProject) -> dict[str, Any]:
    release = None
    if project.published_release_id:
        release = (
            db.query(InteractiveMovieRelease)
            .filter(
                InteractiveMovieRelease.project_id == project.id,
                InteractiveMovieRelease.id == project.published_release_id,
            )
            .first()
        )
    if not project.is_published or release is None:
        return {
            "is_published": False,
            "published_release_id": None,
            "published_version_no": None,
            "published_at": None,
            "public_path": public_path(project.id),
        }
    from .documents import iso

    return {
        "is_published": True,
        "published_release_id": release.id,
        "published_version_no": release.version_no,
        "published_at": iso(project.published_at) if project.published_at else None,
        "public_path": public_path(project.id),
    }


def release_out(release: InteractiveMovieRelease, current_release_id: str = "") -> dict[str, Any]:
    from .documents import iso

    return {
        "id": release.id,
        "project_id": release.project_id,
        "version_no": release.version_no,
        "title": release.title,
        "content_hash": release.content_hash,
        "created_at": iso(release.created_at),
        "is_current": release.id == current_release_id,
    }


def get_project_release(db: Session, project_id: str, release_id: str) -> InteractiveMovieRelease:
    release = (
        db.query(InteractiveMovieRelease)
        .filter(
            InteractiveMovieRelease.project_id == project_id,
            InteractiveMovieRelease.id == release_id,
        )
        .first()
    )
    if not release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="正式版不存在")
    return release


def public_path(project_id: str) -> str:
    return f"/interactive-movie/play/{project_id}"
