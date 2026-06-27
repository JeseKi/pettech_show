"""add interactive movie generic node links

Revision ID: 2026062702
Revises: 2026062701
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062702"
down_revision: Union[str, Sequence[str], None] = "2026062701"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("interactive_movie_node_links"):
        op.create_table(
            "interactive_movie_node_links",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("from_node_type", sa.String(length=20), nullable=False),
            sa.Column("from_node_id", sa.String(length=80), nullable=False),
            sa.Column("from_handle", sa.String(length=12), nullable=False),
            sa.Column("to_node_type", sa.String(length=20), nullable=False),
            sa.Column("to_node_id", sa.String(length=80), nullable=False),
            sa.Column("to_handle", sa.String(length=12), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_node_links_project_id ON interactive_movie_node_links (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_node_links_from_node_id ON interactive_movie_node_links (from_node_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_node_links_to_node_id ON interactive_movie_node_links (to_node_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_interactive_movie_node_links_to_node_id", table_name="interactive_movie_node_links")
    op.drop_index("ix_interactive_movie_node_links_from_node_id", table_name="interactive_movie_node_links")
    op.drop_index("ix_interactive_movie_node_links_project_id", table_name="interactive_movie_node_links")
    op.drop_table("interactive_movie_node_links")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)
