# -*- coding: utf-8 -*-
"""Persistent upload records for Info Distribution integration."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import Date, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from src.server.database import Base


class DistributionUploadJob(Base):
    __tablename__ = "distribution_upload_jobs"

    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner_user_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    upload_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    theme_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scheduled_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="queued")
    message: Mapped[str | None] = mapped_column(Text, default=None)
    remote_base_url: Mapped[str] = mapped_column(Text, nullable=False)
    plan_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    result_json: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), default=None)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )


class DistributionUploadItem(Base):
    __tablename__ = "distribution_upload_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    upload_job_id: Mapped[str] = mapped_column(
        String(80),
        ForeignKey("distribution_upload_jobs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    owner_user_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    source_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    source_job_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(Text, nullable=False)
    source_label: Mapped[str] = mapped_column(Text, nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    upload_type: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    project_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    theme_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    scheduled_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="success", index=True)
    remote_article_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    response_json: Mapped[str | None] = mapped_column(Text, default=None)
    error: Mapped[str | None] = mapped_column(Text, default=None)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
    )

