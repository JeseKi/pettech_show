"""create capability jobs

Revision ID: 2026062301
Revises: 2026062002
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026062301"
down_revision: Union[str, Sequence[str], None] = "2026062002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("capability_jobs"):
        op.create_table(
            "capability_jobs",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("capability_key", sa.String(length=80), nullable=False),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("workdir", sa.Text(), nullable=False),
            sa.Column("input_json", sa.Text(), nullable=False),
            sa.Column("result_markdown_path", sa.Text(), nullable=True),
            sa.Column("result_json_path", sa.Text(), nullable=True),
            sa.Column("summary_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_capability_jobs_owner_user_id ON capability_jobs (owner_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_capability_jobs_capability_key ON capability_jobs (capability_key)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_capability_jobs_status ON capability_jobs (status)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_capability_jobs_created_at ON capability_jobs (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_capability_jobs_created_at", table_name="capability_jobs")
    op.drop_index("ix_capability_jobs_status", table_name="capability_jobs")
    op.drop_index("ix_capability_jobs_capability_key", table_name="capability_jobs")
    op.drop_index("ix_capability_jobs_owner_user_id", table_name="capability_jobs")
    op.drop_table("capability_jobs")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())
