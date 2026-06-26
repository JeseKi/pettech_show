"""add editable capability job titles

Revision ID: 2026062603
Revises: 2026062602
Create Date: 2026-06-26

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062603"
down_revision: Union[str, Sequence[str], None] = "2026062602"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if _table_exists("capability_jobs") and not _column_exists("capability_jobs", "title"):
        op.add_column("capability_jobs", sa.Column("title", sa.String(length=255), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("capability_jobs") and _column_exists("capability_jobs", "title"):
        op.drop_column("capability_jobs", "title")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )
