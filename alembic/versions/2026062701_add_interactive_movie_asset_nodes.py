"""add interactive movie asset nodes

Revision ID: 2026062701
Revises: 2026062603
Create Date: 2026-06-27

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062701"
down_revision: Union[str, Sequence[str], None] = "2026062603"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    scene_columns = _columns("interactive_movie_scenes")
    with op.batch_alter_table("interactive_movie_scenes") as batch_op:
        if "video_node_id" not in scene_columns:
            batch_op.add_column(sa.Column("video_node_id", sa.String(length=80), nullable=False, server_default=""))
        if "cover_image_node_id" not in scene_columns:
            batch_op.add_column(sa.Column("cover_image_node_id", sa.String(length=80), nullable=False, server_default=""))

    if not _table_exists("interactive_movie_asset_nodes"):
        op.create_table(
            "interactive_movie_asset_nodes",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("type", sa.String(length=20), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("position_x", sa.Float(), nullable=False),
            sa.Column("position_y", sa.Float(), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("media_url", sa.Text(), nullable=False),
            sa.Column("media_object_key", sa.Text(), nullable=False),
            sa.Column("media_storage_uri", sa.Text(), nullable=False),
            sa.Column("media_content_type", sa.String(length=120), nullable=False),
            sa.Column("media_size", sa.Integer(), nullable=False),
            sa.Column("media_status", sa.String(length=20), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_asset_nodes_project_id ON interactive_movie_asset_nodes (project_id)")


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_interactive_movie_asset_nodes_project_id", table_name="interactive_movie_asset_nodes")
    op.drop_table("interactive_movie_asset_nodes")
    with op.batch_alter_table("interactive_movie_scenes") as batch_op:
        batch_op.drop_column("cover_image_node_id")
        batch_op.drop_column("video_node_id")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}
