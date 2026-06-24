"""create daily writer jobs

Revision ID: 2026062002
Revises: 2026062001
Create Date: 2026-06-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026062002"
down_revision: Union[str, Sequence[str], None] = "2026062001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("daily_writer_jobs"):
        op.create_table(
            "daily_writer_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_seed_matrix_job_id", sa.String(length=80), nullable=False),
            sa.Column("source_aiwiki_job_id", sa.String(length=64), nullable=False),
            sa.Column("seed_id", sa.String(length=128), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("row_json", sa.Text(), nullable=False),
            sa.Column("params_json", sa.Text(), nullable=False),
            sa.Column("article_path", sa.Text(), nullable=True),
            sa.Column("metadata_path", sa.Text(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(
                ["source_aiwiki_job_id"],
                ["aiwiki_jobs.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(
                ["source_seed_matrix_job_id"],
                ["seed_matrix_jobs.id"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_owner_user_id ON daily_writer_jobs (owner_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_source_seed_matrix_job_id ON daily_writer_jobs (source_seed_matrix_job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_source_aiwiki_job_id ON daily_writer_jobs (source_aiwiki_job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_seed_id ON daily_writer_jobs (seed_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_status ON daily_writer_jobs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_daily_writer_jobs_created_at ON daily_writer_jobs (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_daily_writer_jobs_created_at", table_name="daily_writer_jobs")
    op.drop_index("ix_daily_writer_jobs_status", table_name="daily_writer_jobs")
    op.drop_index("ix_daily_writer_jobs_seed_id", table_name="daily_writer_jobs")
    op.drop_index(
        "ix_daily_writer_jobs_source_aiwiki_job_id",
        table_name="daily_writer_jobs",
    )
    op.drop_index(
        "ix_daily_writer_jobs_source_seed_matrix_job_id",
        table_name="daily_writer_jobs",
    )
    op.drop_index(
        "ix_daily_writer_jobs_owner_user_id",
        table_name="daily_writer_jobs",
    )
    op.drop_table("daily_writer_jobs")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())
