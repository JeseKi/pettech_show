"""add interactive movie route offsets

Revision ID: 2026062703
Revises: 2026062702
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062703"
down_revision: Union[str, Sequence[str], None] = "2026062702"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    choice_columns = _columns("interactive_movie_choices")
    with op.batch_alter_table("interactive_movie_choices") as batch_op:
        if "offset_x" not in choice_columns:
            batch_op.add_column(sa.Column("offset_x", sa.Float(), nullable=False, server_default="0"))

    link_columns = _columns("interactive_movie_node_links")
    with op.batch_alter_table("interactive_movie_node_links") as batch_op:
        if "offset_x" not in link_columns:
            batch_op.add_column(sa.Column("offset_x", sa.Float(), nullable=False, server_default="0"))
        if "offset_y" not in link_columns:
            batch_op.add_column(sa.Column("offset_y", sa.Float(), nullable=False, server_default="0"))


def downgrade() -> None:
    """Downgrade schema."""
    link_columns = _columns("interactive_movie_node_links")
    with op.batch_alter_table("interactive_movie_node_links") as batch_op:
        if "offset_y" in link_columns:
            batch_op.drop_column("offset_y")
        if "offset_x" in link_columns:
            batch_op.drop_column("offset_x")

    choice_columns = _columns("interactive_movie_choices")
    with op.batch_alter_table("interactive_movie_choices") as batch_op:
        if "offset_x" in choice_columns:
            batch_op.drop_column("offset_x")


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
