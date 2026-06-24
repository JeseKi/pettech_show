"""add interactive movie publish releases

Revision ID: 2026062409
Revises: 2026062408
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062409"
down_revision: Union[str, Sequence[str], None] = "2026062408"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    project_columns = _columns("interactive_movie_projects")
    with op.batch_alter_table("interactive_movie_projects") as batch_op:
        if "is_published" not in project_columns:
            batch_op.add_column(sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.false()))
        if "published_release_id" not in project_columns:
            batch_op.add_column(sa.Column("published_release_id", sa.String(length=80), nullable=False, server_default=""))
        if "published_at" not in project_columns:
            batch_op.add_column(sa.Column("published_at", sa.DateTime(timezone=True), nullable=True))

    if not _table_exists("interactive_movie_releases"):
        op.create_table(
            "interactive_movie_releases",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("project_id", sa.String(length=80), nullable=False),
            sa.Column("version_no", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=200), nullable=False),
            sa.Column("document_json", sa.Text(), nullable=False),
            sa.Column("content_hash", sa.String(length=80), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("project_id", "version_no", name="uq_interactive_movie_releases_project_version"),
        )
    op.execute("CREATE INDEX IF NOT EXISTS ix_interactive_movie_releases_project_id ON interactive_movie_releases (project_id)")


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("interactive_movie_releases"):
        op.drop_index("ix_interactive_movie_releases_project_id", table_name="interactive_movie_releases")
        op.drop_table("interactive_movie_releases")
    project_columns = _columns("interactive_movie_projects")
    with op.batch_alter_table("interactive_movie_projects") as batch_op:
        if "published_at" in project_columns:
            batch_op.drop_column("published_at")
        if "published_release_id" in project_columns:
            batch_op.drop_column("published_release_id")
        if "is_published" in project_columns:
            batch_op.drop_column("is_published")


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
