"""add aiwiki job owner

Revision ID: 2026061902
Revises: 2026061901
Create Date: 2026-06-19

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "2026061902"
down_revision: Union[str, Sequence[str], None] = "2026061901"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("aiwiki_jobs") as batch_op:
        batch_op.add_column(sa.Column("owner_user_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_aiwiki_jobs_owner_user_id_users",
            "users",
            ["owner_user_id"],
            ["id"],
            ondelete="SET NULL",
        )
    op.create_index(
        "ix_aiwiki_jobs_owner_user_id", "aiwiki_jobs", ["owner_user_id"]
    )

    connection = op.get_bind()
    admin_id = connection.execute(
        sa.text(
            """
            SELECT id
            FROM users
            WHERE username = 'admin' AND role IN ('admin', 'ADMIN')
            ORDER BY id ASC
            LIMIT 1
            """
        )
    ).scalar()
    if admin_id is None:
        admin_id = connection.execute(
            sa.text(
                """
                SELECT id
                FROM users
                WHERE role IN ('admin', 'ADMIN')
                ORDER BY id ASC
                LIMIT 1
                """
            )
        ).scalar()
    if admin_id is not None:
        connection.execute(
            sa.text(
                "UPDATE aiwiki_jobs SET owner_user_id = :admin_id WHERE owner_user_id IS NULL"
            ),
            {"admin_id": admin_id},
        )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index("ix_aiwiki_jobs_owner_user_id", table_name="aiwiki_jobs")
    with op.batch_alter_table("aiwiki_jobs") as batch_op:
        batch_op.drop_constraint(
            "fk_aiwiki_jobs_owner_user_id_users", type_="foreignkey"
        )
        batch_op.drop_column("owner_user_id")
