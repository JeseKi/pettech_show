"""repair missing aiwiki audit logs table

Revision ID: 2026062405
Revises: 2026062404
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062405"
down_revision: Union[str, Sequence[str], None] = "2026062404"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("aiwiki_audit_logs"):
        op.create_table(
            "aiwiki_audit_logs",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("actor_user_id", sa.Integer(), nullable=False),
            sa.Column("actor_username", sa.String(length=150), nullable=False),
            sa.Column("action", sa.String(length=40), nullable=False),
            sa.Column("job_id", sa.String(length=64), nullable=True),
            sa.Column("target_filename", sa.String(length=255), nullable=False),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("metadata_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_audit_logs_actor_user_id ON aiwiki_audit_logs (actor_user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_audit_logs_action ON aiwiki_audit_logs (action)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_audit_logs_job_id ON aiwiki_audit_logs (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_aiwiki_audit_logs_created_at ON aiwiki_audit_logs (created_at)")


def downgrade() -> None:
    """Downgrade schema."""
    # This is a repair migration for databases that were marked past 2026062402
    # before the aiwiki audit table existed locally. The table belongs to
    # 2026062402, so downgrading this repair revision should not remove it.


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)
