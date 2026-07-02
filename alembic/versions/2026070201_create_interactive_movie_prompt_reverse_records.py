"""create interactive movie prompt reverse records

Revision ID: 2026070201
Revises: 2026070102
Create Date: 2026-07-02

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026070201"
down_revision: Union[str, Sequence[str], None] = "2026070102"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("interactive_movie_prompt_reverse_records"):
        op.create_table(
            "interactive_movie_prompt_reverse_records",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=True),
            sa.Column("filename", sa.String(length=200), nullable=False),
            sa.Column("content_type", sa.String(length=120), nullable=False),
            sa.Column("size", sa.Integer(), nullable=False),
            sa.Column("object_key", sa.Text(), nullable=False),
            sa.Column("storage_uri", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_interactive_movie_prompt_reverse_records_owner_user_id "
        "ON interactive_movie_prompt_reverse_records (owner_user_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_interactive_movie_prompt_reverse_records_project_id "
        "ON interactive_movie_prompt_reverse_records (project_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS ix_interactive_movie_prompt_reverse_records_created_at "
        "ON interactive_movie_prompt_reverse_records (created_at)"
    )


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("interactive_movie_prompt_reverse_records"):
        op.drop_index(
            "ix_interactive_movie_prompt_reverse_records_created_at",
            table_name="interactive_movie_prompt_reverse_records",
        )
        op.drop_index(
            "ix_interactive_movie_prompt_reverse_records_project_id",
            table_name="interactive_movie_prompt_reverse_records",
        )
        op.drop_index(
            "ix_interactive_movie_prompt_reverse_records_owner_user_id",
            table_name="interactive_movie_prompt_reverse_records",
        )
        op.drop_table("interactive_movie_prompt_reverse_records")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)
