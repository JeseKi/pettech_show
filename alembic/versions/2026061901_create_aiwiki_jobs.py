"""create aiwiki jobs

Revision ID: 2026061901
Revises: 
Create Date: 2026-06-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026061901"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("aiwiki_jobs"):
        op.create_table(
            "aiwiki_jobs",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("raw_date", sa.String(length=16), nullable=True),
            sa.Column("files_json", sa.Text(), nullable=False),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_jobs_created_at ON aiwiki_jobs (created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_jobs_status ON aiwiki_jobs (status)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_aiwiki_jobs_status", table_name="aiwiki_jobs")
    op.drop_index("ix_aiwiki_jobs_created_at", table_name="aiwiki_jobs")
    op.drop_table("aiwiki_jobs")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())
