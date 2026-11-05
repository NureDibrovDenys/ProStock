"""Merge multiple heads

Revision ID: 3ac0dd1d3e10
Revises: b7c8d9e0f1a2
Create Date: 2026-11-05 19:01:01.895270

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3ac0dd1d3e10'
down_revision: Union[str, None] = 'b7c8d9e0f1a2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass