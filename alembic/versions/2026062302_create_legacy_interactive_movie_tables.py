"""create legacy interactive movie tables

Revision ID: 2026062302
Revises: 2026062301
Create Date: 2026-06-23

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062302"
down_revision: Union[str, Sequence[str], None] = "2026062301"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("interactive_movie_projects"):
        op.create_table(
            "interactive_movie_projects",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("title", sa.String(length=160), nullable=False),
            sa.Column("canvas_json", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("interactive_movie_assets"):
        op.create_table(
            "interactive_movie_assets",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("kind", sa.String(length=40), nullable=False),
            sa.Column("filename", sa.String(length=200), nullable=False),
            sa.Column("mime_type", sa.String(length=120), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("storage_path", sa.Text(), nullable=False),
            sa.Column("source", sa.String(length=40), nullable=False),
            sa.Column("external_url", sa.Text(), nullable=True),
            sa.Column("provider", sa.String(length=80), nullable=True),
            sa.Column("metadata_json", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("interactive_movie_generations"):
        op.create_table(
            "interactive_movie_generations",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=True),
            sa.Column("node_id", sa.String(length=120), nullable=False),
            sa.Column("node_type", sa.String(length=40), nullable=False),
            sa.Column("provider", sa.String(length=80), nullable=True),
            sa.Column("provider_task_id", sa.String(length=160), nullable=True),
            sa.Column("status", sa.String(length=20), nullable=False),
            sa.Column("prompt", sa.Text(), nullable=False),
            sa.Column("request_json", sa.Text(), nullable=False),
            sa.Column("result_json", sa.Text(), nullable=True),
            sa.Column("result_asset_id", sa.String(length=80), nullable=True),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("interactive_movie_generations")
    op.drop_table("interactive_movie_assets")
    op.drop_table("interactive_movie_projects")


def _table_exists(table_name: str) -> bool:
    return bool(op.get_bind().execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:name"),
        {"name": table_name},
    ).fetchone())
