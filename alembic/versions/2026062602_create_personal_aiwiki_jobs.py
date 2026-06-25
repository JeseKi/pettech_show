"""create personal aiwiki jobs

Revision ID: 2026062602
Revises: 2026062601
Create Date: 2026-06-26

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062602"
down_revision: Union[str, Sequence[str], None] = "2026062601"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("personal_aiwiki_jobs"):
        op.create_table(
            "personal_aiwiki_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("operation", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=255), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("workspace_dir", sa.Text(), nullable=False),
            sa.Column("input_text", sa.Text(), nullable=True),
            sa.Column("files_json", sa.Text(), nullable=False),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("answer_markdown", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_aiwiki_jobs_owner_user_id ON personal_aiwiki_jobs (owner_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_aiwiki_jobs_operation ON personal_aiwiki_jobs (operation)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_aiwiki_jobs_status ON personal_aiwiki_jobs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_personal_aiwiki_jobs_created_at ON personal_aiwiki_jobs (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("personal_aiwiki_jobs"):
        op.drop_index("ix_personal_aiwiki_jobs_created_at", table_name="personal_aiwiki_jobs")
        op.drop_index("ix_personal_aiwiki_jobs_status", table_name="personal_aiwiki_jobs")
        op.drop_index("ix_personal_aiwiki_jobs_operation", table_name="personal_aiwiki_jobs")
        op.drop_index("ix_personal_aiwiki_jobs_owner_user_id", table_name="personal_aiwiki_jobs")
        op.drop_table("personal_aiwiki_jobs")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)
