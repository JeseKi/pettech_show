"""create persistent chat sessions

Revision ID: 2026062403
Revises: 2026062402
Create Date: 2026-06-24

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026062403"
down_revision: Union[str, Sequence[str], None] = "2026062402"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if not _table_exists("chat_sessions"):
        op.create_table(
            "chat_sessions",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("title", sa.String(length=100), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_chat_sessions_owner_user_id", "chat_sessions", ["owner_user_id"])
    _create_index_if_missing("ix_chat_sessions_updated_at", "chat_sessions", ["updated_at"])

    if not _table_exists("chat_messages"):
        op.create_table(
            "chat_messages",
            sa.Column("id", sa.String(length=80), nullable=False),
            sa.Column("session_id", sa.String(length=80), nullable=False),
            sa.Column("owner_user_id", sa.Integer(), nullable=False),
            sa.Column("role", sa.String(length=20), nullable=False),
            sa.Column("content", sa.Text(), nullable=False),
            sa.Column("sequence", sa.Integer(), nullable=False),
            sa.Column("model", sa.String(length=100), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["session_id"], ["chat_sessions.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
    _create_index_if_missing("ix_chat_messages_owner_user_id", "chat_messages", ["owner_user_id"])
    _create_index_if_missing("ix_chat_messages_session_id", "chat_messages", ["session_id"])
    _create_index_if_missing("ix_chat_messages_session_sequence", "chat_messages", ["session_id", "sequence"])


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("chat_messages"):
        _drop_index_if_exists("ix_chat_messages_session_sequence", "chat_messages")
        _drop_index_if_exists("ix_chat_messages_session_id", "chat_messages")
        _drop_index_if_exists("ix_chat_messages_owner_user_id", "chat_messages")
        op.drop_table("chat_messages")
    if _table_exists("chat_sessions"):
        _drop_index_if_exists("ix_chat_sessions_updated_at", "chat_sessions")
        _drop_index_if_exists("ix_chat_sessions_owner_user_id", "chat_sessions")
        op.drop_table("chat_sessions")


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
