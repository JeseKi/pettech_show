# -*- coding: utf-8 -*-
"""Release and public-read services for interactive movies."""

from __future__ import annotations

import json
from typing import Any
from uuid import uuid4

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import InteractiveMovieProject, InteractiveMovieRelease, utc_now
from ..schemas import InteractiveMoviePublishIn, InteractiveMovieSetPublishedReleaseIn
from .access import get_owned_project
from .documents import iso, project_out, snapshot
from .publication import get_project_release, release_out, set_project_publication


def list_releases(db: Session, user: User, project_id: str) -> list[dict[str, Any]]:
    project = get_owned_project(db, user, project_id)
    releases = (
        db.query(InteractiveMovieRelease)
        .filter(InteractiveMovieRelease.project_id == project.id)
        .order_by(InteractiveMovieRelease.version_no.desc(), InteractiveMovieRelease.created_at.desc())
        .all()
    )
    return [release_out(release, project.published_release_id) for release in releases]


def publish_project(
    db: Session,
    user: User,
    project_id: str,
    payload: InteractiveMoviePublishIn,
) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    if project.version != payload.base_version or project.content_hash != payload.base_hash:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "reason": "version_conflict",
                "remote_version": project.version,
                "remote_hash": project.content_hash,
            },
        )

    latest_version = (
        db.query(InteractiveMovieRelease.version_no)
        .filter(InteractiveMovieRelease.project_id == project.id)
        .order_by(InteractiveMovieRelease.version_no.desc())
        .first()
    )
    version_no = int(latest_version[0]) + 1 if latest_version else 1
    now = utc_now()
    document_snapshot = snapshot(db, project)
    release = InteractiveMovieRelease(
        id=f"release-{uuid4().hex}",
        project_id=project.id,
        version_no=version_no,
        title=project.title,
        document_json=json.dumps(document_snapshot, ensure_ascii=False),
        content_hash=project.content_hash,
        created_at=now,
    )
    db.add(release)
    set_project_publication(project, release.id, now)
    db.commit()
    db.refresh(project)
    db.refresh(release)
    return {
        "project": project_out(db, project),
        "release": release_out(release, project.published_release_id),
    }


def set_published_release(
    db: Session,
    user: User,
    project_id: str,
    payload: InteractiveMovieSetPublishedReleaseIn,
) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    release = get_project_release(db, project.id, payload.release_id)
    set_project_publication(project, release.id, utc_now())
    db.commit()
    db.refresh(project)
    return project_out(db, project)


def close_publication(db: Session, user: User, project_id: str) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    project.is_published = False
    project.published_release_id = ""
    project.published_at = None
    project.version += 1
    project.updated_at = utc_now()
    db.commit()
    db.refresh(project)
    return project_out(db, project)


def get_public_project(db: Session, project_id: str) -> dict[str, Any]:
    project = (
        db.query(InteractiveMovieProject)
        .populate_existing()
        .filter(InteractiveMovieProject.id == project_id)
        .first()
    )
    if not project or not project.is_published or not project.published_release_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="互动电影未发表")

    release = (
        db.query(InteractiveMovieRelease)
        .filter(
            InteractiveMovieRelease.project_id == project.id,
            InteractiveMovieRelease.id == project.published_release_id,
        )
        .first()
    )
    if not release:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="互动电影未发表")

    try:
        document = json.loads(release.document_json)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="互动电影未发表") from exc
    return {
        "id": project.id,
        "title": release.title,
        "release_id": release.id,
        "version_no": release.version_no,
        "content_hash": release.content_hash,
        "published_at": iso(project.published_at or release.created_at),
        "document": document,
    }
