"""upgrade interactive movie structured project storage

Revision ID: 2026062401
Revises: 2026062302
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062401"
down_revision: Union[str, Sequence[str], None] = "2026062302"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    project_columns = _columns("interactive_movie_projects")
    with op.batch_alter_table("interactive_movie_projects") as batch_op:
        if "version" not in project_columns:
            batch_op.add_column(sa.Column("version", sa.Integer(), nullable=False, server_default="1"))
        if "content_hash" not in project_columns:
            batch_op.add_column(sa.Column("content_hash", sa.String(length=80), nullable=False, server_default="sha256:legacy"))
        if "selected_object_type" not in project_columns:
            batch_op.add_column(sa.Column("selected_object_type", sa.String(length=20), nullable=False, server_default="scene"))
        if "selected_object_id" not in project_columns:
            batch_op.add_column(sa.Column("selected_object_id", sa.String(length=80), nullable=False, server_default=""))
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_projects_owner_user_id ON interactive_movie_projects (owner_user_id)")

    if not _table_exists("interactive_movie_scenes"):
        op.create_table(
            "interactive_movie_scenes",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("position_x", sa.Float(), nullable=False),
            sa.Column("position_y", sa.Float(), nullable=False),
            sa.Column("synopsis", sa.Text(), nullable=False),
            sa.Column("visual_description", sa.Text(), nullable=False),
            sa.Column("video_prompt", sa.Text(), nullable=False),
            sa.Column("prompt_subject", sa.Text(), nullable=False),
            sa.Column("prompt_action", sa.Text(), nullable=False),
            sa.Column("prompt_scene", sa.Text(), nullable=False),
            sa.Column("prompt_camera", sa.Text(), nullable=False),
            sa.Column("prompt_timeline", sa.Text(), nullable=False),
            sa.Column("prompt_style", sa.Text(), nullable=False),
            sa.Column("prompt_constraints", sa.Text(), nullable=False),
            sa.Column("media_kind", sa.String(length=20), nullable=False),
            sa.Column("media_url", sa.Text(), nullable=False),
            sa.Column("media_object_key", sa.Text(), nullable=False),
            sa.Column("media_storage_uri", sa.Text(), nullable=False),
            sa.Column("poster_url", sa.Text(), nullable=False),
            sa.Column("media_status", sa.String(length=20), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_scenes_project_id ON interactive_movie_scenes (project_id)")

    if not _table_exists("interactive_movie_script_lines"):
        op.create_table(
            "interactive_movie_script_lines",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("scene_id", sa.String(length=80), nullable=False),
            sa.Column("speaker", sa.String(length=120), nullable=False),
            sa.Column("text", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_script_lines_scene_id ON interactive_movie_script_lines (scene_id)")

    if not _table_exists("interactive_movie_choices"):
        op.create_table(
            "interactive_movie_choices",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("from_scene_id", sa.String(length=80), nullable=False),
            sa.Column("to_scene_id", sa.String(length=80), nullable=False),
            sa.Column("label", sa.String(length=200), nullable=False),
            sa.Column("trigger", sa.String(length=40), nullable=False),
            sa.Column("offset_y", sa.Float(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_choices_project_id ON interactive_movie_choices (project_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_choices_from_scene_id ON interactive_movie_choices (from_scene_id)")
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_choices_to_scene_id ON interactive_movie_choices (to_scene_id)")

    if not _table_exists("interactive_movie_viewports"):
        op.create_table(
            "interactive_movie_viewports",
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("x", sa.Float(), nullable=False),
            sa.Column("y", sa.Float(), nullable=False),
            sa.Column("zoom", sa.Float(), nullable=False),
            sa.PrimaryKeyConstraint("project_id"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("interactive_movie_viewports")
    op.drop_index("ix_interactive_movie_choices_to_scene_id", table_name="interactive_movie_choices")
    op.drop_index("ix_interactive_movie_choices_from_scene_id", table_name="interactive_movie_choices")
    op.drop_index("ix_interactive_movie_choices_project_id", table_name="interactive_movie_choices")
    op.drop_table("interactive_movie_choices")
    op.drop_index("ix_interactive_movie_script_lines_scene_id", table_name="interactive_movie_script_lines")
    op.drop_table("interactive_movie_script_lines")
    op.drop_index("ix_interactive_movie_scenes_project_id", table_name="interactive_movie_scenes")
    op.drop_table("interactive_movie_scenes")
    op.drop_index("ix_interactive_movie_projects_owner_user_id", table_name="interactive_movie_projects")
    with op.batch_alter_table("interactive_movie_projects") as batch_op:
        batch_op.drop_column("selected_object_id")
        batch_op.drop_column("selected_object_type")
        batch_op.drop_column("content_hash")
        batch_op.drop_column("version")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())


def _columns(table_name: str) -> set[str]:
    return {
        row[1]
        for row in op.get_bind().execute(sa.text(f"PRAGMA table_info({table_name})")).fetchall()
    }
