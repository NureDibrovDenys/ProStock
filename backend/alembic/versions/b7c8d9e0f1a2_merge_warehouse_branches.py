"""Merge warehouse partition and user warehouse branches.

Revision ID: b7c8d9e0f1a2
Revises: 3d9e5a7c1f42, a1b2c3d4e5f6
"""

from typing import Sequence, Union

from alembic import op


revision: str = "b7c8d9e0f1a2"
down_revision: Union[str, Sequence[str], None] = (
    "3d9e5a7c1f42",
    "a1b2c3d4e5f6",
)
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
