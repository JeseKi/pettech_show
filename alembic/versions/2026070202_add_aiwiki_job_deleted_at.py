"""add soft delete marker to aiwiki jobs

Revision ID: 2026070202
Revises: 2026070201
Create Date: 2026-07-02

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026070202"
down_revision: Union[str, Sequence[str], None] = "2026070201"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("aiwiki_jobs"):
        return
    if not _column_exists("aiwiki_jobs", "deleted_at"):
        with op.batch_alter_table("aiwiki_jobs") as batch_op:
            batch_op.add_column(sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_jobs_deleted_at ON aiwiki_jobs (deleted_at)")


def downgrade() -> None:
    """Downgrade schema."""
    if not _table_exists("aiwiki_jobs"):
        return
    op.execute("DROP INDEX IF EXISTS ix_aiwiki_jobs_deleted_at")
    if _column_exists("aiwiki_jobs", "deleted_at"):
        with op.batch_alter_table("aiwiki_jobs") as batch_op:
            batch_op.drop_column("deleted_at")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(
        column["name"] == column_name
        for column in sa.inspect(op.get_bind()).get_columns(table_name)
    )
