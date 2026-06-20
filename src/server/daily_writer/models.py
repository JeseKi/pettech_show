# -*- coding: utf-8 -*-
"""Persistent daily writer job records."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


class DailyWriterJob(Base):
    __tablename__ = "daily_writer_jobs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_seed_matrix_job_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("seed_matrix_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_aiwiki_job_id: Mapped[str] = mapped_column(
        String(64),
        ForeignKey("aiwiki_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    seed_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    message: Mapped[str | None] = mapped_column(Text, default=None)
    workdir: Mapped[str] = mapped_column(Text, nullable=False)
    row_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    params_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    article_path: Mapped[str | None] = mapped_column(Text, default=None)
    metadata_path: Mapped[str | None] = mapped_column(Text, default=None)
    summary_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

