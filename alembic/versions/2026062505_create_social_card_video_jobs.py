"""create social card video jobs

Revision ID: 2026062505
Revises: 2026062504
Create Date: 2026-06-25

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062505"
down_revision: Union[str, Sequence[str], None] = "2026062504"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("social_card_video_jobs"):
        op.create_table(
            "social_card_video_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_social_card_job_id", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("params_json", sa.Text(), nullable=False),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["source_social_card_job_id"],
                ["social_card_jobs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing(
        "ix_social_card_video_jobs_owner_user_id",
        "social_card_video_jobs",
        ["owner_user_id"],
    )
    _create_index_if_missing(
        "ix_social_card_video_jobs_source_social_card_job_id",
        "social_card_video_jobs",
        ["source_social_card_job_id"],
    )


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("social_card_video_jobs"):
        _drop_index_if_exists(
            "ix_social_card_video_jobs_source_social_card_job_id",
            "social_card_video_jobs",
        )
        _drop_index_if_exists(
            "ix_social_card_video_jobs_owner_user_id",
            "social_card_video_jobs",
        )
        op.drop_table("social_card_video_jobs")


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
