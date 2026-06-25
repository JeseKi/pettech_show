"""add editable generation job titles

Revision ID: 2026062601
Revises: 2026062506
Create Date: 2026-06-26

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062601"
down_revision: Union[str, Sequence[str], None] = "2026062506"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


TITLE_TABLES = (
    "seed_matrix_jobs",
    "daily_writer_jobs",
    "social_card_jobs",
    "social_card_video_jobs",
)


def upgrade() -> None:
    """Upgrade schema."""
    for table_name in TITLE_TABLES:
        if _table_exists(table_name) and not _column_exists(table_name, "title"):
            op.add_column(table_name, sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for table_name in reversed(TITLE_TABLES):
        if _table_exists(table_name) and _column_exists(table_name, "title"):
            op.drop_column(table_name, "title")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )
