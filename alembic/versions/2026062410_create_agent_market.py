"""create agent market

Revision ID: 2026062410
Revises: 2026062409
Create Date: 2026-06-24

"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062410"
down_revision: Union[str, Sequence[str], None] = "2026062409"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

DEFAULT_AGENT_ID = "zhongying-advertising"
DEFAULT_AGENT_REVISION_ID = "apr-zhongying-advertising-v1"
DEFAULT_PROMPT = (
    "你是中影广告的互动影游创作助手，擅长把用户想法整理成"
    "剧本、分镜、角色、选择节点和可进入工作空间执行的下一步。"
)


def upgrade() -> None:
    """Upgrade schema."""
    _create_market_tables()
    _add_chat_session_agent_columns()
    _seed_default_agent()


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("chat_sessions"):
        columns = _columns("chat_sessions")
        with op.batch_alter_table("chat_sessions") as batch_op:
            if "agent_revision_id" in columns:
                batch_op.drop_column("agent_revision_id")
            if "agent_id" in columns:
                batch_op.drop_column("agent_id")

    if _table_exists("agent_tag_links"):
        _drop_index_if_exists("ix_agent_tag_links_tag_id", "agent_tag_links")
        _drop_index_if_exists("ix_agent_tag_links_agent_id", "agent_tag_links")
        op.drop_table("agent_tag_links")
    if _table_exists("agent_prompt_revisions"):
        _drop_index_if_exists("ix_agent_prompt_revisions_active", "agent_prompt_revisions")
        _drop_index_if_exists("ix_agent_prompt_revisions_agent_id", "agent_prompt_revisions")
        op.drop_table("agent_prompt_revisions")
    if _table_exists("agents"):
        _drop_index_if_exists("ix_agents_is_default", "agents")
        _drop_index_if_exists("ix_agents_enabled", "agents")
        _drop_index_if_exists("ix_agents_sort_order", "agents")
        _drop_index_if_exists("ix_agents_current_revision_id", "agents")
        _drop_index_if_exists("ix_agents_visibility", "agents")
        _drop_index_if_exists("ix_agents_category_id", "agents")
        _drop_index_if_exists("ix_agents_slug", "agents")
        op.drop_table("agents")
    if _table_exists("agent_tags"):
        _drop_index_if_exists("ix_agent_tags_enabled", "agent_tags")
        _drop_index_if_exists("ix_agent_tags_sort_order", "agent_tags")
        op.drop_table("agent_tags")
    if _table_exists("agent_categories"):
        _drop_index_if_exists("ix_agent_categories_enabled", "agent_categories")
        _drop_index_if_exists("ix_agent_categories_sort_order", "agent_categories")
        _drop_index_if_exists("ix_agent_categories_visibility", "agent_categories")
        op.drop_table("agent_categories")


def _create_market_tables() -> None:
    if not _table_exists("agent_categories"):
        op.create_table(
            "agent_categories",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("visibility", sa.String(length=40), nullable=False, server_default="public"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_agent_categories_visibility", "agent_categories", ["visibility"])
    _create_index_if_missing("ix_agent_categories_sort_order", "agent_categories", ["sort_order"])
    _create_index_if_missing("ix_agent_categories_enabled", "agent_categories", ["enabled"])

    if not _table_exists("agent_tags"):
        op.create_table(
            "agent_tags",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("name", sa.String(length=120), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_agent_tags_sort_order", "agent_tags", ["sort_order"])
    _create_index_if_missing("ix_agent_tags_enabled", "agent_tags", ["enabled"])

    if not _table_exists("agents"):
        op.create_table(
            "agents",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("slug", sa.String(length=80), nullable=False),
            sa.Column("title", sa.String(length=120), nullable=False),
            sa.Column("category_id", sa.String(length=80), nullable=False),
            sa.Column("visibility", sa.String(length=40), nullable=False, server_default="public"),
            sa.Column("summary", sa.String(length=240), nullable=False),
            sa.Column("description", sa.Text(), nullable=False, server_default=""),
            sa.Column("current_revision_id", sa.String(length=80), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("protected", sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["category_id"], ["agent_categories.id"], ondelete="RESTRICT"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("slug"),
        )
    _create_index_if_missing("ix_agents_slug", "agents", ["slug"])
    _create_index_if_missing("ix_agents_category_id", "agents", ["category_id"])
    _create_index_if_missing("ix_agents_visibility", "agents", ["visibility"])
    _create_index_if_missing("ix_agents_current_revision_id", "agents", ["current_revision_id"])
    _create_index_if_missing("ix_agents_sort_order", "agents", ["sort_order"])
    _create_index_if_missing("ix_agents_enabled", "agents", ["enabled"])
    _create_index_if_missing("ix_agents_is_default", "agents", ["is_default"])

    if not _table_exists("agent_prompt_revisions"):
        op.create_table(
            "agent_prompt_revisions",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("agent_id", sa.String(length=80), nullable=False),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.Column("system_prompt", sa.Text(), nullable=False),
            sa.Column("change_note", sa.Text(), nullable=False, server_default=""),
            sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_by_user_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id", "version", name="uq_agent_prompt_revisions_agent_version"),
        )
    _create_index_if_missing("ix_agent_prompt_revisions_agent_id", "agent_prompt_revisions", ["agent_id"])
    _create_index_if_missing("ix_agent_prompt_revisions_active", "agent_prompt_revisions", ["active"])

    if not _table_exists("agent_tag_links"):
        op.create_table(
            "agent_tag_links",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("agent_id", sa.String(length=80), nullable=False),
            sa.Column("tag_id", sa.String(length=80), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["tag_id"], ["agent_tags.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("agent_id", "tag_id", name="uq_agent_tag_links_agent_tag"),
        )
    _create_index_if_missing("ix_agent_tag_links_agent_id", "agent_tag_links", ["agent_id"])
    _create_index_if_missing("ix_agent_tag_links_tag_id", "agent_tag_links", ["tag_id"])


def _add_chat_session_agent_columns() -> None:
    if not _table_exists("chat_sessions"):
        return
    columns = _columns("chat_sessions")
    with op.batch_alter_table("chat_sessions") as batch_op:
        if "agent_id" not in columns:
            batch_op.add_column(
                sa.Column(
                    "agent_id",
                    sa.String(length=80),
                    nullable=False,
                    server_default=DEFAULT_AGENT_ID,
                )
            )
        if "agent_revision_id" not in columns:
            batch_op.add_column(
                sa.Column(
                    "agent_revision_id",
                    sa.String(length=80),
                    nullable=False,
                    server_default=DEFAULT_AGENT_REVISION_ID,
                )
            )


def _seed_default_agent() -> None:
    connection = op.get_bind()
    now = datetime.now(timezone.utc).isoformat()
    _insert_if_missing(
        connection,
        "agent_categories",
        "staff-agents",
        sa.text(
            "INSERT INTO agent_categories "
            "(id, name, description, visibility, sort_order, enabled, created_at, updated_at) "
            "VALUES (:id, '员工智能体', '适合宠物企业一线员工、运营和内容团队使用的智能体。', "
            "'public', 10, 1, :created_at, :updated_at)"
        ),
        now,
    )
    _insert_if_missing(
        connection,
        "agent_categories",
        "owner-agents",
        sa.text(
            "INSERT INTO agent_categories "
            "(id, name, description, visibility, sort_order, enabled, created_at, updated_at) "
            "VALUES (:id, '老板智能体', '仅老板和管理员可见的经营、管理、决策类智能体。', "
            "'admin', 20, 1, :created_at, :updated_at)"
        ),
        now,
    )
    _insert_if_missing(
        connection,
        "agent_tags",
        "content-creation",
        sa.text(
            "INSERT INTO agent_tags (id, name, sort_order, enabled, created_at, updated_at) "
            "VALUES (:id, '内容创作', 10, 1, :created_at, :updated_at)"
        ),
        now,
    )
    _insert_if_missing(
        connection,
        "agents",
        DEFAULT_AGENT_ID,
        sa.text(
            "INSERT INTO agents "
            "(id, slug, title, category_id, visibility, summary, description, current_revision_id, "
            "sort_order, enabled, is_default, protected, created_at, updated_at) "
            "VALUES (:id, :id, '中影广告智能体', 'staff-agents', 'public', "
            "'互动影游、宠物企业内容和中影广告工作流的默认智能体。', "
            "'擅长把用户想法整理成剧本、分镜、角色、选择节点和可执行的下一步。', "
            ":revision_id, 10, 1, 1, 1, :created_at, :updated_at)"
        ),
        now,
        extra={"revision_id": DEFAULT_AGENT_REVISION_ID},
    )
    existing_revision = connection.execute(
        sa.text("SELECT 1 FROM agent_prompt_revisions WHERE id = :id"),
        {"id": DEFAULT_AGENT_REVISION_ID},
    ).first()
    if not existing_revision:
        connection.execute(
            sa.text(
                "INSERT INTO agent_prompt_revisions "
                "(id, agent_id, version, system_prompt, change_note, active, created_by_user_id, created_at) "
                "VALUES (:id, :agent_id, 1, :system_prompt, '系统默认版本', 1, NULL, :created_at)"
            ),
            {
                "id": DEFAULT_AGENT_REVISION_ID,
                "agent_id": DEFAULT_AGENT_ID,
                "system_prompt": DEFAULT_PROMPT,
                "created_at": now,
            },
        )
    existing_link = connection.execute(
        sa.text("SELECT 1 FROM agent_tag_links WHERE agent_id = :agent_id AND tag_id = :tag_id"),
        {"agent_id": DEFAULT_AGENT_ID, "tag_id": "content-creation"},
    ).first()
    if not existing_link:
        connection.execute(
            sa.text("INSERT INTO agent_tag_links (agent_id, tag_id) VALUES (:agent_id, :tag_id)"),
            {"agent_id": DEFAULT_AGENT_ID, "tag_id": "content-creation"},
        )


def _insert_if_missing(connection, table_name: str, row_id: str, statement, now: str, extra: dict[str, object] | None = None) -> None:
    existing = connection.execute(
        sa.text(f"SELECT 1 FROM {table_name} WHERE id = :id"),
        {"id": row_id},
    ).first()
    if existing:
        return
    params: dict[str, object] = {"id": row_id, "created_at": now, "updated_at": now}
    if extra:
        params.update(extra)
    connection.execute(statement, params)


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _columns(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {column["name"] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


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
