"""create user agent installs

Revision ID: 2026062503
Revises: 2026062502
Create Date: 2026-06-25

"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062503"
down_revision: Union[str, Sequence[str], None] = "2026062502"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("user_agents"):
        op.create_table(
            "user_agents",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("agent_id", sa.String(length=80), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["agent_id"], ["agents.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("owner_user_id", "agent_id", name="uq_user_agents_owner_agent"),
        )
    _create_index_if_missing("ix_user_agents_owner_user_id", "user_agents", ["owner_user_id"])
    _create_index_if_missing("ix_user_agents_agent_id", "user_agents", ["agent_id"])


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("user_agents"):
        _drop_index_if_exists("ix_user_agents_agent_id", "user_agents")
        _drop_index_if_exists("ix_user_agents_owner_user_id", "user_agents")
        op.drop_table("user_agents")


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
