# -*- coding: utf-8 -*-
"""Interactive movie persistence models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class InteractiveMovieProject(Base):
    __tablename__ = "interactive_movie_projects"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    canvas_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    selected_object_type: Mapped[str] = mapped_column(String(20), nullable=False, default="scene")
    selected_object_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    published_release_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class InteractiveMovieScene(Base):
    __tablename__ = "interactive_movie_scenes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    synopsis: Mapped[str] = mapped_column(Text, nullable=False, default="")
    visual_description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    video_prompt: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_subject: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_action: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_scene: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_camera: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_timeline: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_style: Mapped[str] = mapped_column(Text, nullable=False, default="")
    prompt_constraints: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_kind: Mapped[str] = mapped_column(String(20), nullable=False, default="placeholder")
    media_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_object_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_storage_uri: Mapped[str] = mapped_column(Text, nullable=False, default="")
    poster_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    video_node_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    cover_image_node_id: Mapped[str] = mapped_column(String(80), nullable=False, default="")
    media_status: Mapped[str] = mapped_column(String(20), nullable=False, default="mock")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class InteractiveMovieAssetNode(Base):
    __tablename__ = "interactive_movie_asset_nodes"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    position_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    position_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_url: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_object_key: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_storage_uri: Mapped[str] = mapped_column(Text, nullable=False, default="")
    media_content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    media_size: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    media_status: Mapped[str] = mapped_column(String(20), nullable=False, default="empty")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)


class InteractiveMovieScriptLine(Base):
    __tablename__ = "interactive_movie_script_lines"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    scene_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    speaker: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InteractiveMovieChoice(Base):
    __tablename__ = "interactive_movie_choices"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    from_scene_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    to_scene_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    trigger: Mapped[str] = mapped_column(String(40), nullable=False, default="after_scene")
    offset_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    offset_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InteractiveMovieNodeLink(Base):
    __tablename__ = "interactive_movie_node_links"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    from_node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    from_node_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    from_handle: Mapped[str] = mapped_column(String(12), nullable=False, default="right")
    to_node_type: Mapped[str] = mapped_column(String(20), nullable=False)
    to_node_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    to_handle: Mapped[str] = mapped_column(String(12), nullable=False, default="left")
    offset_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    offset_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class InteractiveMovieViewport(Base):
    __tablename__ = "interactive_movie_viewports"

    project_id: Mapped[str] = mapped_column(String(80), primary_key=True)
    x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    zoom: Mapped[float] = mapped_column(Float, nullable=False, default=1)


class InteractiveMovieRelease(Base):
    __tablename__ = "interactive_movie_releases"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    project_id: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    document_json: Mapped[str] = mapped_column(Text, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
