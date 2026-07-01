"""create chat rollout items

Revision ID: 2026070101
Revises: 2026062703
Create Date: 2026-07-01

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2026070101"
down_revision: Union[str, Sequence[str], None] = "2026062703"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "chat_rollout_items" in existing_tables:
        return

    op.create_table(
        "chat_rollout_items",
        sa.Column("id", sa.String(length=80), primary_key=True),
        sa.Column(
            "session_id",
            sa.String(length=80),
            sa.ForeignKey("chat_sessions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "owner_user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("item_type", sa.String(length=40), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_chat_rollout_items_session_id", "chat_rollout_items", ["session_id"])
    op.create_index("ix_chat_rollout_items_owner_user_id", "chat_rollout_items", ["owner_user_id"])
    op.create_index(
        "ix_chat_rollout_items_session_sequence",
        "chat_rollout_items",
        ["session_id", "sequence"],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    existing_tables = set(sa.inspect(op.get_bind()).get_table_names())
    if "chat_rollout_items" not in existing_tables:
        return
    op.drop_index("ix_chat_rollout_items_session_sequence", table_name="chat_rollout_items")
    op.drop_index("ix_chat_rollout_items_owner_user_id", table_name="chat_rollout_items")
    op.drop_index("ix_chat_rollout_items_session_id", table_name="chat_rollout_items")
    op.drop_table("chat_rollout_items")
