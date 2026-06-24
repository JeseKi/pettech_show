"""add aiwiki job metadata

Revision ID: 2026062406
Revises: 2026062405
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062406"
down_revision: Union[str, Sequence[str], None] = "2026062405"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    columns = _columns("aiwiki_jobs")
    with op.batch_alter_table("aiwiki_jobs") as batch_op:
        if "title" not in columns:
            batch_op.add_column(sa.Column("title", sa.String(length=255), nullable=True))
        if "description" not in columns:
            batch_op.add_column(sa.Column("description", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    columns = _columns("aiwiki_jobs")
    with op.batch_alter_table("aiwiki_jobs") as batch_op:
        if "description" in columns:
            batch_op.drop_column("description")
        if "title" in columns:
            batch_op.drop_column("title")


def _columns(table_name: str) -> set[str]:
    return {
        row[1]
        for row in op.get_bind().execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    }
