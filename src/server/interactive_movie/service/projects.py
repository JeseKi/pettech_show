# -*- coding: utf-8 -*-
"""Draft project services for interactive movies."""

from __future__ import annotations

import json
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import InteractiveMovieChoice, InteractiveMovieProject, InteractiveMovieScene, utc_now
from ..schemas import (
    InteractiveMovieProjectCreateIn,
    InteractiveMovieProjectPatchIn,
    InteractiveMovieProjectRenameIn,
)
from .access import get_owned_project
from .documents import compute_content_hash, iso, normalize_document, project_out, snapshot
from .persistence import apply_patch, delete_project_children, replace_project_children
from .publication import delete_project_releases, publication_fields


def list_projects(db: Session, user: User) -> list[dict[str, Any]]:
    projects = (
        db.query(InteractiveMovieProject)
        .filter(InteractiveMovieProject.owner_user_id == user.id)
        .order_by(InteractiveMovieProject.updated_at.desc(), InteractiveMovieProject.created_at.desc())
        .all()
    )
    summaries: list[dict[str, Any]] = []
    for project in projects:
        scene_count = db.query(InteractiveMovieScene).filter(InteractiveMovieScene.project_id == project.id).count()
        choice_count = db.query(InteractiveMovieChoice).filter(InteractiveMovieChoice.project_id == project.id).count()
        summaries.append({
            "id": project.id,
            "title": project.title,
            "version": project.version,
            "content_hash": project.content_hash,
            "updated_at": iso(project.updated_at),
            "scene_count": scene_count,
            "choice_count": choice_count,
            **publication_fields(db, project),
        })
    return summaries


def create_project(db: Session, user: User, payload: InteractiveMovieProjectCreateIn) -> dict[str, Any]:
    document = payload.document
    existing = db.query(InteractiveMovieProject).filter(InteractiveMovieProject.id == document.id).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="项目 ID 已存在")

    now = utc_now()
    document_payload = document.model_dump(by_alias=True)
    document_snapshot = normalize_document(document_payload)
    content_hash = compute_content_hash(document_snapshot)
    selected = document_snapshot.get("selectedObject") or {}
    project = InteractiveMovieProject(
        id=document.id,
        owner_user_id=user.id,
        title=payload.title.strip() or document.title,
        canvas_json=json.dumps(document_snapshot, ensure_ascii=False),
        version=1,
        content_hash=content_hash,
        selected_object_type=str(selected.get("type") or "scene"),
        selected_object_id=str(selected.get("id") or ""),
        created_at=now,
        updated_at=now,
    )
    db.add(project)
    replace_project_children(db, project.id, document_snapshot)
    db.commit()
    return get_project(db, user, project.id)


def get_project(db: Session, user: User, project_id: str) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    return project_out(db, project)


def get_sync_state(db: Session, user: User, project_id: str) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    return {
        "project_id": project.id,
        "version": project.version,
        "content_hash": project.content_hash,
        "updated_at": iso(project.updated_at),
    }


def patch_project(db: Session, user: User, project_id: str, payload: InteractiveMovieProjectPatchIn) -> dict[str, Any]:
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

    apply_patch(db, project, payload)
    document_snapshot = snapshot(db, project)
    project.content_hash = compute_content_hash(document_snapshot)
    project.canvas_json = json.dumps(document_snapshot, ensure_ascii=False)
    project.version += 1
    project.updated_at = utc_now()
    db.commit()
    db.refresh(project)
    return project_out(db, project)


def rename_project(db: Session, user: User, project_id: str, payload: InteractiveMovieProjectRenameIn) -> dict[str, Any]:
    project = get_owned_project(db, user, project_id)
    title = payload.title.strip()
    if not title:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="项目名称不能为空")

    project.title = title[:200]
    project.version += 1
    project.updated_at = utc_now()
    document_snapshot = snapshot(db, project)
    project.content_hash = compute_content_hash(document_snapshot)
    project.canvas_json = json.dumps(document_snapshot, ensure_ascii=False)
    db.commit()
    db.refresh(project)
    return project_out(db, project)


def delete_project(db: Session, user: User, project_id: str) -> None:
    project = get_owned_project(db, user, project_id)
    delete_project_children(db, project.id)
    delete_project_releases(db, project.id)
    db.delete(project)
    db.commit()
