"""merge migration branches

Revision ID: d9e91acf1948
Revises: 4ade0d0fc05f, 5a6b7c8d9e0f
Create Date: 2026-11-14 21:25:39.417115

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd9e91acf1948'
down_revision: Union[str, None] = ('4ade0d0fc05f', '5a6b7c8d9e0f')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass