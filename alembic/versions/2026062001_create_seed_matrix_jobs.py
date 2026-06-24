"""create seed matrix jobs

Revision ID: 2026062001
Revises: 2026061902
Create Date: 2026-06-20

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026062001"
down_revision: Union[str, Sequence[str], None] = "2026061902"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("seed_matrix_jobs"):
        op.create_table(
            "seed_matrix_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("source_aiwiki_job_id", sa.String(length=64), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("params_json", sa.Text(), nullable=False),
            sa.Column("result_csv_path", sa.Text(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["source_aiwiki_job_id"], ["aiwiki_jobs.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_matrix_jobs_owner_user_id ON seed_matrix_jobs (owner_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_matrix_jobs_source_aiwiki_job_id ON seed_matrix_jobs (source_aiwiki_job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_matrix_jobs_status ON seed_matrix_jobs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_seed_matrix_jobs_created_at ON seed_matrix_jobs (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_seed_matrix_jobs_created_at", table_name="seed_matrix_jobs")
    op.drop_index("ix_seed_matrix_jobs_status", table_name="seed_matrix_jobs")
    op.drop_index("ix_seed_matrix_jobs_source_aiwiki_job_id", table_name="seed_matrix_jobs")
    op.drop_index("ix_seed_matrix_jobs_owner_user_id", table_name="seed_matrix_jobs")
    op.drop_table("seed_matrix_jobs")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())
