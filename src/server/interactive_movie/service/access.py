# -*- coding: utf-8 -*-
"""Shared access checks for interactive movie services."""

from __future__ import annotations

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from src.server.auth.models import User

from ..models import InteractiveMovieProject


def get_owned_project(db: Session, user: User, project_id: str) -> InteractiveMovieProject:
    project = (
        db.query(InteractiveMovieProject)
        .populate_existing()
        .filter(
            InteractiveMovieProject.id == project_id,
            InteractiveMovieProject.owner_user_id == user.id,
        )
        .first()
    )
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="互动电影项目不存在")
    return project
