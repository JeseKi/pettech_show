"""create agent skills

Revision ID: 2026062407
Revises: 2026062406
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062407"
down_revision: Union[str, Sequence[str], None] = "2026062406"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("agent_skill_categories"):
        op.create_table(
            "agent_skill_categories",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_agent_skill_categories_sort_order", "agent_skill_categories", ["sort_order"])
    _create_index_if_missing("ix_agent_skill_categories_enabled", "agent_skill_categories", ["enabled"])

    if not _table_exists("agent_skill_tags"):
        op.create_table(
            "agent_skill_tags",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_agent_skill_tags_sort_order", "agent_skill_tags", ["sort_order"])
    _create_index_if_missing("ix_agent_skill_tags_enabled", "agent_skill_tags", ["enabled"])

    if not _table_exists("agent_skills"):
        op.create_table(
            "agent_skills",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("category_id", sa.String(length=80), nullable=False),
            sa.Column("visibility", sa.String(length=40), nullable=False),
            sa.Column("summary", sa.String(length=240), nullable=False),
            sa.Column("description", sa.Text(), nullable=False),
            sa.Column("skill_dir", sa.Text(), nullable=False),
            sa.Column("skill_path", sa.Text(), nullable=False),
            sa.Column("metadata_path", sa.Text(), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["category_id"], ["agent_skill_categories.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
    _create_index_if_missing("ix_agent_skills_slug", "agent_skills", ["slug"])
    _create_index_if_missing("ix_agent_skills_category_id", "agent_skills", ["category_id"])
    _create_index_if_missing("ix_agent_skills_visibility", "agent_skills", ["visibility"])
    _create_index_if_missing("ix_agent_skills_sort_order", "agent_skills", ["sort_order"])
    _create_index_if_missing("ix_agent_skills_enabled", "agent_skills", ["enabled"])

    if not _table_exists("agent_skill_tag_links"):
        op.create_table(
            "agent_skill_tag_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("skill_id", sa.String(length=80), nullable=False),
            sa.Column("tag_id", sa.String(length=80), nullable=False),
            sa.ForeignKeyConstraint(["skill_id"], ["agent_skills.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tag_id"], ["agent_skill_tags.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("skill_id", "tag_id", name="uq_agent_skill_tag_links_skill_tag"),
        )
    _create_index_if_missing("ix_agent_skill_tag_links_skill_id", "agent_skill_tag_links", ["skill_id"])
    _create_index_if_missing("ix_agent_skill_tag_links_tag_id", "agent_skill_tag_links", ["tag_id"])

    if not _table_exists("user_agent_skills"):
        op.create_table(
            "user_agent_skills",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("skill_id", sa.String(length=80), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["skill_id"], ["agent_skills.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("owner_user_id", "skill_id", name="uq_user_agent_skills_owner_skill"),
        )
    _create_index_if_missing("ix_user_agent_skills_owner_user_id", "user_agent_skills", ["owner_user_id"])
    _create_index_if_missing("ix_user_agent_skills_skill_id", "user_agent_skills", ["skill_id"])


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("user_agent_skills"):
        _drop_index_if_exists("ix_user_agent_skills_skill_id", "user_agent_skills")
        _drop_index_if_exists("ix_user_agent_skills_owner_user_id", "user_agent_skills")
        op.drop_table("user_agent_skills")
    if _table_exists("agent_skill_tag_links"):
        _drop_index_if_exists("ix_agent_skill_tag_links_tag_id", "agent_skill_tag_links")
        _drop_index_if_exists("ix_agent_skill_tag_links_skill_id", "agent_skill_tag_links")
        op.drop_table("agent_skill_tag_links")
    if _table_exists("agent_skills"):
        _drop_index_if_exists("ix_agent_skills_enabled", "agent_skills")
        _drop_index_if_exists("ix_agent_skills_sort_order", "agent_skills")
        _drop_index_if_exists("ix_agent_skills_visibility", "agent_skills")
        _drop_index_if_exists("ix_agent_skills_category_id", "agent_skills")
        _drop_index_if_exists("ix_agent_skills_slug", "agent_skills")
        op.drop_table("agent_skills")
    if _table_exists("agent_skill_tags"):
        _drop_index_if_exists("ix_agent_skill_tags_enabled", "agent_skill_tags")
        _drop_index_if_exists("ix_agent_skill_tags_sort_order", "agent_skill_tags")
        op.drop_table("agent_skill_tags")
    if _table_exists("agent_skill_categories"):
        _drop_index_if_exists("ix_agent_skill_categories_enabled", "agent_skill_categories")
        _drop_index_if_exists("ix_agent_skill_categories_sort_order", "agent_skill_categories")
        op.drop_table("agent_skill_categories")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)


def _drop_index_if_exists(index_name: str, table_name: str) -> None:
    if _index_exists(table_name, index_name):
        op.drop_index(index_name, table_name=table_name)
