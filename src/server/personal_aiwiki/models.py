# -*- coding: utf-8 -*-
"""Personal AI Wiki job models."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


class PersonalAiwikiJob(Base):
    __tablename__ = "personal_aiwiki_jobs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    operation: Mapped[str] = mapped_column(String(20), nullable=False, default="ingest", index=True)
    title: Mapped[str | None] = mapped_column(String(255), default=None)
    description: Mapped[str | None] = mapped_column(Text, default=None)
    message: Mapped[str | None] = mapped_column(Text, default=None)
    workdir: Mapped[str] = mapped_column(Text, nullable=False)
    workspace_dir: Mapped[str] = mapped_column(Text, nullable=False)
    input_text: Mapped[str | None] = mapped_column(Text, default=None)
    files_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    summary_json: Mapped[str | None] = mapped_column(Text, default=None)
    answer_markdown: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), default=None
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
