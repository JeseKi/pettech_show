"""repair agent skill taxonomy tables

Revision ID: 2026062408
Revises: 2026062407
Create Date: 2026-06-24

"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import re
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062408"
down_revision: Union[str, Sequence[str], None] = "2026062407"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    connection = op.get_bind()
    now = datetime.now(timezone.utc).isoformat()

    _create_taxonomy_tables_if_missing()
    _repair_agent_skill_columns(connection, now)
    _create_tag_link_table_if_missing()
    _migrate_legacy_tags(connection, now)

    _create_index_if_missing("ix_agent_skill_categories_sort_order", "agent_skill_categories", ["sort_order"])
    _create_index_if_missing("ix_agent_skill_categories_enabled", "agent_skill_categories", ["enabled"])
    _create_index_if_missing("ix_agent_skill_tags_sort_order", "agent_skill_tags", ["sort_order"])
    _create_index_if_missing("ix_agent_skill_tags_enabled", "agent_skill_tags", ["enabled"])
    if _table_exists("agent_skills"):
        _create_index_if_missing("ix_agent_skills_category_id", "agent_skills", ["category_id"])
        _create_index_if_missing("ix_agent_skills_visibility", "agent_skills", ["visibility"])
    if _table_exists("agent_skill_tag_links"):
        _create_index_if_missing("ix_agent_skill_tag_links_skill_id", "agent_skill_tag_links", ["skill_id"])
        _create_index_if_missing("ix_agent_skill_tag_links_tag_id", "agent_skill_tag_links", ["tag_id"])


def downgrade() -> None:
    """Downgrade schema.

    This migration is intentionally repair-oriented and idempotent. On fresh
    databases, revision 2026062407 already owns these tables, so dropping them
    here would make a downgrade to 2026062407 invalid.
    """


def _create_taxonomy_tables_if_missing() -> None:
    if not _table_exists("agent_skill_categories"):
        op.create_table(
            "agent_skill_categories",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    if not _table_exists("agent_skill_tags"):
        op.create_table(
            "agent_skill_tags",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )


def _repair_agent_skill_columns(connection, now: str) -> None:
    if not _table_exists("agent_skills"):
        return

    columns = _columns("agent_skills")
    if "category_id" not in columns:
        op.add_column("agent_skills", sa.Column("category_id", sa.String(length=80), nullable=True))
        columns = _columns("agent_skills")

    if "category" in columns:
        rows = connection.execute(
            sa.text("SELECT DISTINCT category FROM agent_skills WHERE category IS NOT NULL AND category != ''")
        ).fetchall()
        for row in rows:
            raw_category = str(row[0])
            category_id = _safe_slug(raw_category, "legacy-category")
            _insert_category_if_missing(connection, category_id, raw_category, now)
            connection.execute(
                sa.text(
                    "UPDATE agent_skills SET category_id = :category_id "
                    "WHERE category = :raw_category AND category_id IS NULL"
                ),
                {"category_id": category_id, "raw_category": raw_category},
            )

    missing_category_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM agent_skills WHERE category_id IS NULL OR category_id = ''")
    ).scalar()
    if missing_category_count:
        _insert_category_if_missing(connection, "uncategorized", "未分类", now)
        connection.execute(
            sa.text("UPDATE agent_skills SET category_id = 'uncategorized' WHERE category_id IS NULL OR category_id = ''")
        )

    if "visibility" in columns:
        connection.execute(sa.text("UPDATE agent_skills SET visibility = 'public' WHERE visibility = 'all'"))
        connection.execute(sa.text("UPDATE agent_skills SET visibility = 'admin' WHERE visibility = 'owner'"))


def _create_tag_link_table_if_missing() -> None:
    if not _table_exists("agent_skills"):
        return
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


def _migrate_legacy_tags(connection, now: str) -> None:
    if not _table_exists("agent_skills") or not _table_exists("agent_skill_tag_links"):
        return
    columns = _columns("agent_skills")
    if "tags_json" not in columns:
        return

    rows = connection.execute(sa.text("SELECT id, tags_json FROM agent_skills WHERE tags_json IS NOT NULL")).fetchall()
    for skill_id, raw_tags in rows:
        try:
            tags = json.loads(raw_tags or "[]")
        except json.JSONDecodeError:
            tags = []
        if not isinstance(tags, list):
            continue
        for tag_name in tags:
            if not isinstance(tag_name, str) or not tag_name.strip():
                continue
            tag_id = _safe_slug(tag_name, "legacy-tag")
            _insert_tag_if_missing(connection, tag_id, tag_name.strip(), now)
            _insert_tag_link_if_missing(connection, str(skill_id), tag_id)


def _insert_category_if_missing(connection, category_id: str, name: str, now: str) -> None:
    existing = connection.execute(
        sa.text("SELECT 1 FROM agent_skill_categories WHERE id = :id"),
        {"id": category_id},
    ).first()
    if existing:
        return
    next_sort_order = _next_sort_order(connection, "agent_skill_categories")
    connection.execute(
        sa.text(
            "INSERT INTO agent_skill_categories "
            "(id, name, description, sort_order, enabled, created_at, updated_at) "
            "VALUES (:id, :name, '', :sort_order, 1, :created_at, :updated_at)"
        ),
        {
            "id": category_id,
            "name": name,
            "sort_order": next_sort_order,
            "created_at": now,
            "updated_at": now,
        },
    )


def _insert_tag_if_missing(connection, tag_id: str, name: str, now: str) -> None:
    existing = connection.execute(
        sa.text("SELECT 1 FROM agent_skill_tags WHERE id = :id"),
        {"id": tag_id},
    ).first()
    if existing:
        return
    next_sort_order = _next_sort_order(connection, "agent_skill_tags")
    connection.execute(
        sa.text(
            "INSERT INTO agent_skill_tags "
            "(id, name, sort_order, enabled, created_at, updated_at) "
            "VALUES (:id, :name, :sort_order, 1, :created_at, :updated_at)"
        ),
        {
            "id": tag_id,
            "name": name,
            "sort_order": next_sort_order,
            "created_at": now,
            "updated_at": now,
        },
    )


def _insert_tag_link_if_missing(connection, skill_id: str, tag_id: str) -> None:
    existing = connection.execute(
        sa.text("SELECT 1 FROM agent_skill_tag_links WHERE skill_id = :skill_id AND tag_id = :tag_id"),
        {"skill_id": skill_id, "tag_id": tag_id},
    ).first()
    if existing:
        return
    connection.execute(
        sa.text("INSERT INTO agent_skill_tag_links (skill_id, tag_id) VALUES (:skill_id, :tag_id)"),
        {"skill_id": skill_id, "tag_id": tag_id},
    )


def _next_sort_order(connection, table_name: str) -> int:
    current = connection.execute(sa.text(f"SELECT MAX(sort_order) FROM {table_name}")).scalar()
    return int(current or 0) + 10


def _safe_slug(value: str, fallback_prefix: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9_-]+", "-", value.strip()).strip("-_")
    if not slug:
        slug = fallback_prefix
    if not re.match(r"^[A-Za-z0-9]", slug):
        slug = f"{fallback_prefix}-{slug}"
    if len(slug) < 2:
        slug = f"{fallback_prefix}-{slug}"
    return slug[:80]


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _index_exists(table_name: str, index_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(index["name"] == index_name for index in sa.inspect(op.get_bind()).get_indexes(table_name))


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str]) -> None:
    if not _index_exists(table_name, index_name):
        op.create_index(index_name, table_name, columns)
