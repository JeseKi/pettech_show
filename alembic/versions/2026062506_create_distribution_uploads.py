"""create distribution upload records

Revision ID: 2026062506
Revises: 2026062505
Create Date: 2026-06-25

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062506"
down_revision: Union[str, Sequence[str], None] = "2026062505"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("distribution_upload_jobs"):
        op.create_table(
            "distribution_upload_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("source_job_id", sa.String(length=100), nullable=False),
            sa.Column("upload_type", sa.String(length=40), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("theme_id", sa.Integer(), nullable=False),
            sa.Column("scheduled_date", sa.Date(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("remote_base_url", sa.Text(), nullable=False),
            sa.Column("plan_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )

    if not _table_exists("distribution_upload_items"):
        op.create_table(
            "distribution_upload_items",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("upload_job_id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_type", sa.String(length=40), nullable=False),
            sa.Column("source_job_id", sa.String(length=100), nullable=False),
            sa.Column("source_key", sa.Text(), nullable=False),
            sa.Column("source_label", sa.Text(), nullable=False),
            sa.Column("content_sha256", sa.String(length=64), nullable=False),
            sa.Column("upload_type", sa.String(length=40), nullable=False),
            sa.Column("account_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.Integer(), nullable=False),
            sa.Column("theme_id", sa.Integer(), nullable=False),
            sa.Column("scheduled_date", sa.Date(), nullable=False),
            sa.Column("title", sa.Text(), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("remote_article_id", sa.Integer(), nullable=True),
            sa.Column("response_json", sa.Text(), nullable=True),
            sa.Column("error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(
                ["upload_job_id"],
                ["distribution_upload_jobs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )

    for table, columns in {
        "distribution_upload_jobs": [
            "owner_user_id",
            "source_type",
            "source_job_id",
            "upload_type",
            "project_id",
            "theme_id",
            "scheduled_date",
        ],
        "distribution_upload_items": [
            "upload_job_id",
            "owner_user_id",
            "source_type",
            "source_job_id",
            "upload_type",
            "account_id",
            "project_id",
            "theme_id",
            "scheduled_date",
            "status",
            "remote_article_id",
        ],
    }.items():
        for column in columns:
            _create_index_if_missing(f"ix_{table}_{column}", table, [column])


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("distribution_upload_items"):
        for index in sa.inspect(op.get_bind()).get_indexes("distribution_upload_items"):
            index_name = index.get("name")
            if index_name:
                _drop_index_if_exists(index_name, "distribution_upload_items")
        op.drop_table("distribution_upload_items")
    if _table_exists("distribution_upload_jobs"):
        for index in sa.inspect(op.get_bind()).get_indexes("distribution_upload_jobs"):
            index_name = index.get("name")
            if index_name:
                _drop_index_if_exists(index_name, "distribution_upload_jobs")
        op.drop_table("distribution_upload_jobs")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(
        index["name"] == index_name
        for index in sa.inspect(op.get_bind()).get_indexes(table_name)
    )


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
