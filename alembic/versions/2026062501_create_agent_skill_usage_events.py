"""create agent skill usage events

Revision ID: 2026062501
Revises: 2026062409
Create Date: 2026-06-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062501"
down_revision: Union[str, Sequence[str], None] = "2026062409"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("agent_skill_usage_events"):
        op.create_table(
            "agent_skill_usage_events",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("skill_id", sa.String(length=80), nullable=False),
            sa.Column("action", sa.String(length=20), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["skill_id"], ["agent_skills.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_agent_skill_usage_events_owner_user_id", "agent_skill_usage_events", ["owner_user_id"])
    _create_index_if_missing("ix_agent_skill_usage_events_skill_id", "agent_skill_usage_events", ["skill_id"])
    _create_index_if_missing("ix_agent_skill_usage_events_action", "agent_skill_usage_events", ["action"])
    _create_index_if_missing("ix_agent_skill_usage_events_created_at", "agent_skill_usage_events", ["created_at"])

    if _table_exists("user_agent_skills"):
        op.execute(
            """
            INSERT INTO agent_skill_usage_events (owner_user_id, skill_id, action, created_at)
            SELECT owner_user_id, skill_id, 'add', created_at
            FROM user_agent_skills
            WHERE enabled = 1
            """
        )


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("agent_skill_usage_events"):
        _drop_index_if_exists("ix_agent_skill_usage_events_created_at", "agent_skill_usage_events")
        _drop_index_if_exists("ix_agent_skill_usage_events_action", "agent_skill_usage_events")
        _drop_index_if_exists("ix_agent_skill_usage_events_skill_id", "agent_skill_usage_events")
        _drop_index_if_exists("ix_agent_skill_usage_events_owner_user_id", "agent_skill_usage_events")
        op.drop_table("agent_skill_usage_events")


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
