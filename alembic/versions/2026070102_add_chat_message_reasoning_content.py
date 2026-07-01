"""add chat message reasoning content

Revision ID: 2026070102
Revises: 2026070101
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026070102"
down_revision: Union[str, Sequence[str], None] = "2026070101"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    if _table_exists("chat_messages") and not _column_exists("chat_messages", "reasoning_content"):
        op.add_column("chat_messages", sa.Column("reasoning_content", sa.Text(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    if _table_exists("chat_messages") and _column_exists("chat_messages", "reasoning_content"):
        op.drop_column("chat_messages", "reasoning_content")


def _table_exists(table_name: str) -> bool:
    return sa.inspect(op.get_bind()).has_table(table_name)


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return any(column["name"] == column_name for column in sa.inspect(op.get_bind()).get_columns(table_name))
