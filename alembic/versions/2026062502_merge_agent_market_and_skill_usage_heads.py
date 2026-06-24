"""merge agent market and skill usage heads

Revision ID: 2026062502
Revises: 2026062410, 2026062501
Create Date: 2026-06-25

"""
from typing import Sequence, Union


revision: str = "2026062502"
down_revision: Union[str, Sequence[str], None] = ("2026062410", "2026062501")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Merge migration branches."""


def downgrade() -> None:
    """Downgrade merge migration."""

